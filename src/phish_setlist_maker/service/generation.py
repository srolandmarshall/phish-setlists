"""High-level orchestration for setlist generation and media artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import logging
import re
from random import Random, SystemRandom
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from ..constants import ERA_DEFINITIONS
from ..generator import GeneratedSetlist, SetlistGenerator, random_set_lengths
from ..generator.core import GenerationMetadata, SetSegment
from ..models import Show, SongTrack, Track, Venue
from .catalog import (
    SongCatalog,
    SongCatalogEntry,
    build_song_catalog,
    determine_origin_from_entry,
    normalize_title,
    split_song_titles,
)
from .errors import PlaylistServiceError
from .models import GenerationResult, PlaylistArtifacts, SegmentDetails, SongDisplay
from .tracks import CandidateTrack, query_tracks_for_song, resolve_track_metadata
from .segments import expand_tracks, segment_duration_seconds

logger = logging.getLogger("uvicorn.error")

_CAP_NOTE_PATTERN = re.compile(
    r"^(Capped (?P<label>.+?) at (?P<count>\d+) songs) \(~(?P<duration>[^)]+)\)(?P<suffix>.*)$"
)


def _format_seconds(seconds: int) -> str:
    minutes, remainder = divmod(max(seconds, 0), 60)
    return f"{minutes}:{remainder:02d}"


def _update_duration_notes_with_actuals(
    metadata: GenerationMetadata,
    segments: Sequence[SegmentDetails],
    encore: Optional[SegmentDetails],
) -> None:
    actual_durations: Dict[str, int] = {
        segment.label: segment.duration_seconds
        for segment in segments
        if segment.duration_seconds is not None
    }
    if encore and encore.duration_seconds is not None:
        actual_durations[encore.label] = encore.duration_seconds

    if not actual_durations or not metadata.notes:
        return

    updated: List[str] = []
    for note in metadata.notes:
        match = _CAP_NOTE_PATTERN.match(note)
        if not match:
            updated.append(note)
            continue

        label = match.group("label")
        count = match.group("count")
        suffix = match.group("suffix")

        actual_seconds = actual_durations.get(label)
        if actual_seconds is None:
            updated.append(note)
            continue

        formatted = _format_seconds(actual_seconds)
        updated.append(f"Capped {label} at {count} songs (~{formatted}){suffix}")

    metadata.notes[:] = updated


@dataclass(frozen=True)
class GenerationRequest:
    """Inputs used to produce a generated setlist."""

    reference_date: Optional[date] = None
    era: Optional[str] = None
    year: Optional[int] = None
    num_sets: int = 2
    include_encore: bool = True
    set_lengths: Optional[Dict[str, int]] = None
    allow_previous_show: bool = True
    seed: Optional[int] = None
    include_playlist: bool = False
    prefetch_track_metadata: bool = True
    fail_on_playlist_error: bool = False
    use_ml_features: bool = True
    ml_placement_weight: float = 0.3
    ml_transition_bonus: float = 0.1
    jamminess: Optional[float] = None  # 0.0 = tight, 0.5 = balanced, 1.0 = max jam
    same_show_segues: bool = False  # Ensure segues from same show performance


def infer_default_era(year: Optional[int]) -> Optional[str]:
    if year is None:
        return "4.0"

    selected: Optional[str] = None
    for label, definition in sorted(ERA_DEFINITIONS.items(), key=lambda item: item[1].start):
        if year >= definition.start.year:
            selected = label

    if selected is None:
        selected = min(ERA_DEFINITIONS.items(), key=lambda item: item[1].start)[0]

    return selected


def resolve_era(year: Optional[int], requested_era: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Determine the effective era, adjusting when the year predates the request."""

    if requested_era:
        definition = ERA_DEFINITIONS[requested_era]
        if year is not None and year < definition.start.year:
            inferred = infer_default_era(year)
            if inferred != requested_era:
                note = f"Adjusted era to {inferred} because year {year} predates era {requested_era}."
                return inferred, note
        return requested_era, None

    inferred = infer_default_era(year)
    return inferred, None


def _select_track_display(
    db_session: Session,
    *,
    song_title: str,
    entry: SongCatalogEntry,
    rng: Random,
    strict: bool,
    missing: Dict[str, int],
    is_set_ender: bool = False,
    canonical_set: Optional[str] = None,
    feature_store = None,  # Optional FeatureStore for lottery logic
    same_show_segues: bool = False,
    generated_setlist = None,  # GeneratedSetlist for tracking
    segue_context: Optional[Dict[str, int]] = None,  # NEW: Map song_title -> predetermined track_id
) -> Optional[SongDisplay]:
    # NEW: Check if this song has a predetermined track_id from a segue context
    # This ensures songs in mandatory segues use tracks from the same actual performance
    if segue_context and song_title in segue_context:
        predetermined_track_id = segue_context[song_title]
        logger.info(
            "Using predetermined track_id=%s for %s from segue context",
            predetermined_track_id,
            song_title
        )

        # Query this specific track
        from ..models import Track, SongTrack
        track_row = db_session.query(
            Track.id, Track.slug, Track.duration, Track.likes_count,
            Track.metadata_cache, Track.show_id, Track.set, Track.position
        ).filter(Track.id == predetermined_track_id).first()

        if not track_row:
            logger.warning(
                "Predetermined track_id=%s not found for %s, falling back to random selection",
                predetermined_track_id,
                song_title
            )
        else:
            # Get show_date for this track
            from ..models import Show
            show = db_session.query(Show).filter(Show.id == track_row.show_id).first()
            show_date = show.date if show else None

            # Create CandidateTrack for this specific track
            from .tracks import CandidateTrack
            selection = CandidateTrack(
                track_id=predetermined_track_id,
                slug=track_row.slug,
                duration=track_row.duration,
                show_date=show_date,
                likes_count=track_row.likes_count or 0,
                metadata_cache=track_row.metadata_cache,
            )

            # Skip to the metadata resolution and display creation
            # (rest of function will handle this)
            candidates = [selection]

    # Try to use set-ending tracks if this song is a set closer
    if not (segue_context and song_title in segue_context):
        if is_set_ender and canonical_set:
            from .tracks import query_set_ending_tracks_for_song
            candidates = query_set_ending_tracks_for_song(db_session, entry.slug, canonical_set)
            if not candidates:
                # Fall back to regular tracks if no set-ending tracks found
                candidates = query_tracks_for_song(db_session, entry.slug)
        else:
            candidates = query_tracks_for_song(db_session, entry.slug)
    
    if not candidates:
        missing[song_title] = missing.get(song_title, 0) + 1
        if strict:
            raise PlaylistServiceError(f"No track recordings available for '{song_title}'.")
        return None

    # NEW: Same-show segue logic
    # If same_show_segues is enabled and this song is part of a mandatory segue,
    # we need to pick a complete segue group and use specific track IDs from that group.
    # This ensures songs follow the ACTUAL segue path from that performance.
    if same_show_segues and feature_store and generated_setlist and segue_context is not None:
        # Only proceed if we haven't already picked a track for this song via segue_context
        if song_title not in segue_context:
            mandatory_segues = feature_store.get_mandatory_segues(song_title)
            if mandatory_segues:
                # Get all songs in the current set to find which segue pattern we're building
                current_set_songs = []
                for segment in generated_setlist.sets:
                    current_set_songs.extend(segment.songs)
                if generated_setlist.encore:
                    current_set_songs.extend(generated_setlist.encore.songs)

                # Identify the complete segue pattern from the current set
                # Example: if current_set_songs contains ["Tweezer", "Mike's Song", "I Am Hydrogen", "Weekapaug Groove"]
                # and song_title is "Mike's Song", we want to find ["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"]

                # Find this song's position and look ahead for the rest of the pattern
                if song_title in current_set_songs:
                    # Build the complete segue chain by following mandatory_segues
                    # Example: Mike's Song -> I Am Hydrogen (pair 1) + I Am Hydrogen -> Weekapaug Groove (pair 2)
                    #          = Mike's Song -> I Am Hydrogen -> Weekapaug Groove (complete chain)
                    segue_chain = [song_title]
                    visited = {song_title}

                    # Follow the chain by looking for songs that appear after this one
                    while True:
                        last_song = segue_chain[-1]
                        found_next = False

                        for segue in feature_store.get_mandatory_segues(last_song):
                            songs_in_segue = segue.get('songs', [])
                            if len(songs_in_segue) >= 2 and songs_in_segue[0] == last_song:
                                next_song = songs_in_segue[1]
                                if next_song not in visited:
                                    segue_chain.append(next_song)
                                    visited.add(next_song)
                                    found_next = True
                                    break

                        if not found_next:
                            break

                    # segue_chain now contains the complete pattern (e.g., ["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"])
                    segue_songs = segue_chain

                    if len(segue_songs) > 1:
                        # Pick a complete segue group for this pattern
                        segue_group = feature_store.pick_segue_group_for_songs(segue_songs, rng)
                        if segue_group:
                            # Extract track IDs from this specific group
                            group_tracks = segue_group.get('tracks', [])
                            group_songs = segue_group.get('songs', [])

                            # Populate segue_context with all songs in this group
                            for i, song in enumerate(group_songs):
                                if i < len(group_tracks):
                                    segue_context[song] = group_tracks[i]
                                    logger.info(
                                        "Segue context: %s -> track_id %s (from segue group %s)",
                                        song,
                                        group_tracks[i],
                                        segue_group.get('segue_id')
                                    )

                            # Now use the predetermined track_id for the current song
                            if song_title in segue_context:
                                predetermined_track_id = segue_context[song_title]
                                # Find the candidate with this track_id
                                filtered_candidates = [c for c in candidates if c.track_id == predetermined_track_id]
                                if filtered_candidates:
                                    candidates = filtered_candidates
                                    logger.info(
                                        "Selected track_id=%s for %s from complete segue group",
                                        predetermined_track_id,
                                        song_title
                                    )

    # PHASE 4.2: Lottery ticket logic
    # Check if any candidates have rare segues, and prioritize them (weighted by lottery_weight)
    # IMPORTANT: Only boost lottery tracks when same_show_segues is enabled
    if feature_store and same_show_segues:
        candidates_with_lottery = []
        for candidate in candidates:
            rare_segues = feature_store.get_rare_segues_from_track(candidate.track_id)
            if rare_segues:
                # This track has rare segue(s) - boost its selection probability
                # Weight by lottery_weight from segue metadata
                max_lottery_weight = max(segue.get('lottery_weight', 1) for segue in rare_segues)
                candidates_with_lottery.append((candidate, max_lottery_weight))
            else:
                # Normal track, weight = 1
                candidates_with_lottery.append((candidate, 1))
        
        # Weighted random selection
        total_weight = sum(weight for _, weight in candidates_with_lottery)
        if total_weight > 0:
            rand_val = rng.random() * total_weight
            cumulative = 0.0
            for candidate, weight in candidates_with_lottery:
                cumulative += weight
                if rand_val <= cumulative:
                    selection = candidate
                    break
            else:
                selection = candidates_with_lottery[-1][0]
        else:
            selection = rng.choice(candidates)
    else:
        selection = rng.choice(candidates)

    logger.info(
        "Selected local track candidate for %s track_id=%s slug=%s",
        song_title,
        selection.track_id,
        selection.slug,
    )
    
    # PHASE 4.2: Check if selected track has rare segues (with lottery probability)
    rare_segue_next_tracks = None
    is_segue = False
    segue_type = None
    segue_pattern = None
    segue_position = None
    segue_group_id = None
    historical_occurrences = None
    rarity_score = None
    likes_count_segue = None

    # IMPORTANT: Lottery tickets only work with same_show_segues enabled
    # Otherwise continuation tracks would be from different shows, breaking authenticity
    if feature_store and same_show_segues:
        rare_segues = feature_store.get_rare_segues_from_track(selection.track_id)
        if rare_segues:
            # Lottery ticket: only inject rare segues 5% of the time
            # This keeps them truly rare and special
            lottery_chance = 0.05
            if rng.random() < lottery_chance:
                # Pick one of the rare segues at random
                selected_segue = rng.choice(rare_segues)

                # Extract next track IDs from rare segue patterns
                rare_segue_next_tracks = []
                tracks_in_pattern = selected_segue.get('tracks', [])
                # Find this track's position and get subsequent tracks
                if selection.track_id in tracks_in_pattern:
                    idx = tracks_in_pattern.index(selection.track_id)
                    # Add all following tracks in the segue
                    rare_segue_next_tracks.extend(tracks_in_pattern[idx+1:])

                if rare_segue_next_tracks:
                    # Populate segue metadata for API response
                    is_segue = True
                    segue_type = "lottery_ticket"
                    segue_pattern = selected_segue.get('pattern')
                    segue_position = idx + 1  # Position in the pattern (1-indexed)
                    segue_group_id = selected_segue.get('segue_id')
                    historical_occurrences = selected_segue.get('historical_occurrences')
                    rarity_score = selected_segue.get('rarity_score')
                    likes_count_segue = selected_segue.get('likes_count')

                    logger.info(
                        "🎰 LOTTERY TICKET! Track %s has rare segue to tracks: %s",
                        selection.track_id,
                        rare_segue_next_tracks
                    )

    mp3_url, remote_duration, remote_show_date = resolve_track_metadata(
        db_session,
        selection,
        song_slug=entry.slug,
        rng=rng,
        strict=strict,
    )
    if not mp3_url:
        missing[song_title] = missing.get(song_title, 0) + 1
        if strict:
            raise PlaylistServiceError(f"Track '{song_title}' lacks an accessible audio URL.")
        return None

    duration_seconds: Optional[int] = None
    if isinstance(selection.duration, int) and selection.duration > 0:
        duration_raw = selection.duration
        if duration_raw > 6000:
            duration_seconds = duration_raw // 1000
        else:
            duration_seconds = duration_raw
    if duration_seconds is None and isinstance(remote_duration, int) and remote_duration > 0:
        duration_seconds = remote_duration

    show_date = selection.show_date.isoformat() if selection.show_date else remote_show_date

    origin_text = determine_origin_from_entry(entry)

    return SongDisplay(
        title=song_title,
        mp3_url=mp3_url,
        duration_seconds=duration_seconds,
        origin=origin_text,
        show_date=show_date,
        track_id=selection.track_id,
        rare_segue_next_tracks=rare_segue_next_tracks,
        is_segue=is_segue,
        segue_type=segue_type,
        segue_pattern=segue_pattern,
        segue_position=segue_position,
        segue_group_id=segue_group_id,
        historical_occurrences=historical_occurrences,
        rarity_score=rarity_score,
        likes_count=likes_count_segue,
    )


def prepare_playlist_artifacts(
    db_session: Session,
    segments: Sequence[SetSegment],
    encore: Optional[SetSegment],
    *,
    catalog: SongCatalog,
    rng: Random,
    include_m3u: bool,
    strict: bool,
    feature_store = None,  # PHASE 4.2: For lottery logic
    same_show_segues: bool = False,
    generated_setlist = None,  # GeneratedSetlist for tracking segues
) -> PlaylistArtifacts:
    track_cache: Dict[str, Optional[SongDisplay]] = {}
    missing: Dict[str, int] = {}
    playlist_lines: List[str] = ["#EXTM3U"] if include_m3u else []
    first_track_url: Optional[str] = None
    injected_segue_tracks: Set[int] = set()  # PHASE 4.2: Track IDs already injected
    segue_notes: List[str] = []  # NEW: Collect notes about segues
    segue_context: Dict[str, int] = {}  # NEW: Maps song_title -> predetermined track_id for same-show segues

    def append_track(song_title: str, is_set_ender: bool = False, canonical_set: Optional[str] = None) -> None:
        nonlocal first_track_url

        normalized = normalize_title(song_title)
        if normalized in track_cache:
            display = track_cache[normalized]
        else:
            entry = catalog.by_title.get(normalized)
            if entry is None:
                missing[song_title] = missing.get(song_title, 0) + 1
                track_cache[normalized] = None
                if strict:
                    raise PlaylistServiceError(f"No song metadata available for '{song_title}'.")
                display = None
            else:
                display = _select_track_display(
                    db_session,
                    song_title=song_title,
                    entry=entry,
                    rng=rng,
                    strict=strict,
                    missing=missing,
                    is_set_ender=is_set_ender,
                    canonical_set=canonical_set,
                    feature_store=feature_store,  # PHASE 4.2
                    same_show_segues=same_show_segues,
                    generated_setlist=generated_setlist,
                    segue_context=segue_context,  # NEW: Pass segue context
                )
                track_cache[normalized] = display

        if not display or not display.mp3_url:
            if include_m3u:
                playlist_lines.append(f"#EXTINF:-1,{song_title} (unavailable)")
                playlist_lines.append(f"# Missing: {song_title}")
            return

        duration_sec = display.duration_seconds if display.duration_seconds is not None else -1
        show_date = display.show_date or "unknown date"

        if include_m3u:
            playlist_lines.append(f"#EXTINF:{duration_sec},{song_title} [{show_date}]")
            playlist_lines.append(display.mp3_url)

        if first_track_url is None:
            first_track_url = display.mp3_url
        
        # PHASE 4.2: Check if this track has rare segue continuations (lottery ticket!)
        if display.rare_segue_next_tracks and feature_store:
            for next_track_id in display.rare_segue_next_tracks:
                # Avoid injecting same track twice
                if next_track_id in injected_segue_tracks:
                    continue
                injected_segue_tracks.add(next_track_id)
                
                # Fetch track metadata directly by track_id
                from ..models import Track, SongTrack, Song
                # Only load columns we need (avoid missing audio_file_data/waveform_png_data)
                track_row = db_session.query(
                    Track.id, Track.slug, Track.duration, Track.likes_count, 
                    Track.metadata_cache, Track.show_id, Track.set, Track.position
                ).filter(Track.id == next_track_id).first()
                if not track_row:
                    continue
                
                # Get song title from track
                song_track = db_session.query(SongTrack).filter(SongTrack.track_id == next_track_id).first()
                if not song_track:
                    continue
                song = db_session.query(Song).filter(Song.id == song_track.song_id).first()
                if not song:
                    continue
                
                # Create CandidateTrack for the segue continuation
                from .tracks import CandidateTrack, resolve_track_metadata
                candidate = CandidateTrack(
                    track_id=next_track_id,
                    slug=track_row.slug,
                    duration=track_row.duration,
                    show_date=None,
                    likes_count=track_row.likes_count or 0,
                    metadata_cache=track_row.metadata_cache,
                )
                
                # Resolve metadata
                mp3_url, remote_duration, remote_show_date = resolve_track_metadata(
                    db_session,
                    candidate,
                    song_slug=song.slug,
                    rng=rng,
                    strict=False,
                )
                
                if mp3_url:
                    duration_seconds = candidate.duration if candidate.duration else remote_duration
                    if duration_seconds and duration_seconds > 6000:
                        duration_seconds = duration_seconds // 1000

                    logger.info("🎰 INJECTING RARE SEGUE: %s (track_id=%s)", song.title, next_track_id)

                    # Add lottery ticket note
                    show_date_str = remote_show_date or "unknown date"
                    lottery_note = f"🎰 Lottery ticket! Rare {display.title} → {song.title} from {show_date_str}"
                    if lottery_note not in segue_notes:
                        segue_notes.append(lottery_note)

                    # Add to playlist
                    if include_m3u:
                        duration_sec = duration_seconds if duration_seconds is not None else -1
                        playlist_lines.append(f"#EXTINF:{duration_sec},{song.title} [{show_date_str}] (rare segue)")
                        playlist_lines.append(mp3_url)

                    # CRITICAL: Add the injected track to track_cache so it appears in the response!
                    # Create a SongDisplay for the continuation track
                    continuation_display = SongDisplay(
                        title=song.title,
                        mp3_url=mp3_url,
                        duration_seconds=duration_seconds,
                        origin=None,  # Could determine from catalog if needed
                        show_date=show_date_str,
                        track_id=next_track_id,
                        is_segue=True,
                        segue_type="lottery_ticket",
                        segue_pattern=f"{display.title} -> {song.title}",
                        segue_position=2,  # This is the continuation track
                        segue_group_id=display.segue_group_id,  # Use same group_id as source
                        historical_occurrences=display.historical_occurrences,
                        rarity_score=display.rarity_score,
                        likes_count=candidate.likes_count,
                    )

                    # Add to cache so it appears in response tracks
                    cache_key = normalize_title(song.title)
                    track_cache[cache_key] = continuation_display

    def append_track_with_injection(song_title: str, is_set_ender: bool = False, canonical_set: Optional[str] = None) -> None:
        append_track(song_title, is_set_ender, canonical_set)

    for segment in segments:
        from ..generator.historical import normalize_set_label
        canonical = normalize_set_label(segment.label) if segment.label else None
        for idx, raw_song in enumerate(segment.songs):
            is_last = (idx == len(segment.songs) - 1)
            for title in split_song_titles(raw_song):
                append_track_with_injection(title, is_set_ender=is_last, canonical_set=canonical)

    if encore:
        for idx, raw_song in enumerate(encore.songs):
            is_last = (idx == len(encore.songs) - 1)
            for title in split_song_titles(raw_song):
                append_track_with_injection(title, is_set_ender=is_last, canonical_set="encore")

    sections: List[Tuple[str, List[SongDisplay]]] = []
    for segment in segments:
        rows: List[SongDisplay] = []
        for raw_song in segment.songs:
            for title in split_song_titles(raw_song):
                key = normalize_title(title)
                display = track_cache.get(key)
                if display:
                    rows.append(display)

                    # If this track has rare segue continuations, add them to the section
                    if display.rare_segue_next_tracks and feature_store:
                        from ..models import Track, SongTrack, Song
                        for next_track_id in display.rare_segue_next_tracks:
                            # Check if already added to THIS section's rows
                            if any(r.track_id == next_track_id for r in rows):
                                continue

                            track_row = db_session.query(
                                Track.id, Track.slug, Track.duration, Track.likes_count,
                                Track.metadata_cache, Track.show_id, Track.set, Track.position
                            ).filter(Track.id == next_track_id).first()
                            if not track_row:
                                continue

                            song_track = db_session.query(SongTrack).filter(SongTrack.track_id == next_track_id).first()
                            if not song_track:
                                continue
                            song = db_session.query(Song).filter(Song.id == song_track.song_id).first()
                            if not song:
                                continue

                            from .tracks import CandidateTrack, resolve_track_metadata
                            candidate = CandidateTrack(
                                track_id=next_track_id,
                                slug=track_row.slug,
                                duration=track_row.duration,
                                show_date=None,
                                likes_count=track_row.likes_count or 0,
                                metadata_cache=track_row.metadata_cache,
                            )

                            mp3_url, remote_duration, remote_show_date = resolve_track_metadata(
                                db_session, candidate, song_slug=song.slug, rng=rng, strict=False
                            )

                            if mp3_url:
                                duration_seconds = candidate.duration if candidate.duration else remote_duration
                                if duration_seconds and duration_seconds > 6000:
                                    duration_seconds = duration_seconds // 1000
                                show_date_str = remote_show_date or "unknown"

                                continuation_display = SongDisplay(
                                    title=song.title,
                                    mp3_url=mp3_url,
                                    duration_seconds=duration_seconds,
                                    origin=determine_origin_from_entry(None),
                                    show_date=show_date_str,
                                    track_id=next_track_id,
                                    is_segue=True,
                                    segue_type="lottery_ticket",
                                    segue_pattern=display.segue_pattern,
                                    segue_position=2 if len(rows) == 1 else len(rows) + 1,
                                    segue_group_id=display.segue_group_id,
                                    historical_occurrences=display.historical_occurrences,
                                    rarity_score=display.rarity_score,
                                    likes_count=display.likes_count,
                                )
                                rows.append(continuation_display)
                else:
                    entry = catalog.by_title.get(key)
                    origin = determine_origin_from_entry(entry) if entry else None
                    rows.append(SongDisplay(title=title, origin=origin))
        sections.append((segment.label, rows))

    if encore:
        encore_rows: List[SongDisplay] = []
        for raw_song in encore.songs:
            for title in split_song_titles(raw_song):
                key = normalize_title(title)
                display = track_cache.get(key)
                if display:
                    encore_rows.append(display)

                    # If this track has rare segue continuations, add them to the encore
                    if display.rare_segue_next_tracks and feature_store:
                        from ..models import Track, SongTrack, Song
                        for next_track_id in display.rare_segue_next_tracks:
                            # Check if already added to encore rows
                            if any(r.track_id == next_track_id for r in encore_rows):
                                continue

                            track_row = db_session.query(
                                Track.id, Track.slug, Track.duration, Track.likes_count,
                                Track.metadata_cache, Track.show_id, Track.set, Track.position
                            ).filter(Track.id == next_track_id).first()
                            if not track_row:
                                continue

                            song_track = db_session.query(SongTrack).filter(SongTrack.track_id == next_track_id).first()
                            if not song_track:
                                continue
                            song = db_session.query(Song).filter(Song.id == song_track.song_id).first()
                            if not song:
                                continue

                            from .tracks import CandidateTrack, resolve_track_metadata
                            candidate = CandidateTrack(
                                track_id=next_track_id,
                                slug=track_row.slug,
                                duration=track_row.duration,
                                show_date=None,
                                likes_count=track_row.likes_count or 0,
                                metadata_cache=track_row.metadata_cache,
                            )

                            mp3_url, remote_duration, remote_show_date = resolve_track_metadata(
                                db_session, candidate, song_slug=song.slug, rng=rng, strict=False
                            )

                            if mp3_url:
                                duration_seconds = candidate.duration if candidate.duration else remote_duration
                                if duration_seconds and duration_seconds > 6000:
                                    duration_seconds = duration_seconds // 1000
                                show_date_str = remote_show_date or "unknown"

                                continuation_display = SongDisplay(
                                    title=song.title,
                                    mp3_url=mp3_url,
                                    duration_seconds=duration_seconds,
                                    origin=determine_origin_from_entry(None),
                                    show_date=show_date_str,
                                    track_id=next_track_id,
                                    is_segue=True,
                                    segue_type="lottery_ticket",
                                    segue_pattern=display.segue_pattern,
                                    segue_position=len(encore_rows) + 1,
                                    segue_group_id=display.segue_group_id,
                                    historical_occurrences=display.historical_occurrences,
                                    rarity_score=display.rarity_score,
                                    likes_count=display.likes_count,
                                )
                                encore_rows.append(continuation_display)
                else:
                    entry = catalog.by_title.get(key)
                    origin = determine_origin_from_entry(entry) if entry else None
                    encore_rows.append(SongDisplay(title=title, origin=origin))
        sections.append((encore.label, encore_rows))

    m3u_text = "\n".join(playlist_lines) if include_m3u else None
    missing_titles = list(missing.keys())
    return PlaylistArtifacts(
        sections=sections,
        first_track_url=first_track_url,
        m3u_text=m3u_text,
        missing_tracks=missing_titles,
        segue_notes=segue_notes,
    )


def generate_show(session: Session, request: GenerationRequest) -> GenerationResult:
    """Generate a setlist and any requested media artifacts."""

    effective_era, era_adjustment = resolve_era(request.year, request.era)

    seed = request.seed if request.seed is not None else SystemRandom().randint(0, 2**32 - 1)
    rng = Random(seed)
    length_rng = Random(seed)
    
    # Get a random venue for the title
    venue_name = None
    venue_city = None
    try:
        from sqlalchemy import func
        random_venue = session.query(Venue).order_by(func.random()).limit(1).first()
        if random_venue:
            venue_name = random_venue.name
            venue_city = random_venue.city
    except Exception:
        pass

    allow_previous_show = request.allow_previous_show
    current_year = datetime.now().year
    if request.year is not None and request.year < current_year and not request.allow_previous_show:
        allow_previous_show = True

    generator = SetlistGenerator(
        session,
        rng=rng,
        use_ml_features=request.use_ml_features,
        ml_placement_weight=request.ml_placement_weight,
        ml_transition_bonus=request.ml_transition_bonus,
        jamminess=request.jamminess,
        same_show_segues=request.same_show_segues,
    )

    if request.set_lengths:
        set_lengths = dict(request.set_lengths)
    else:
        set_lengths = random_set_lengths(
            session,
            reference_date=request.reference_date,
            era=effective_era,
            year=request.year,
            num_sets=request.num_sets,
            include_encore=request.include_encore,
            rng=length_rng,
        )

    generated = generator.generate(
        reference_date=request.reference_date,
        era=effective_era,
        year=request.year,
        num_sets=request.num_sets,
        include_encore=request.include_encore,
        set_lengths=set_lengths,
        exclude_previous_show=not allow_previous_show,
    )

    metadata = generated.metadata
    if era_adjustment and era_adjustment not in metadata.notes:
        metadata.notes.append(era_adjustment)

    if allow_previous_show and not request.allow_previous_show:
        note = "Allowed previous show songs because the selected year predates the current year."
        if note not in metadata.notes:
            metadata.notes.append(note)

    generated_at = datetime.now(timezone.utc)

    playlist_artifacts: Optional[PlaylistArtifacts] = None
    if request.include_playlist or request.prefetch_track_metadata:
        catalog = build_song_catalog(session)
        playlist_artifacts = prepare_playlist_artifacts(
            session,
            generated.sets,
            generated.encore,
            catalog=catalog,
            rng=rng,
            include_m3u=request.include_playlist,
            strict=request.fail_on_playlist_error,
            feature_store=generator._feature_store if request.use_ml_features else None,  # PHASE 4.2
            same_show_segues=request.same_show_segues,
            generated_setlist=generated,  # For tracking segues in metadata
        )

    track_lookup: Dict[str, SongDisplay] = {}
    if playlist_artifacts:
        for _, songs in playlist_artifacts.sections:
            for song in songs:
                track_lookup[normalize_title(song.title)] = song

    segments_details: List[SegmentDetails] = [
        SegmentDetails(
            label=segment.label,
            songs=list(segment.songs),
            tracks=expand_tracks(segment.songs, track_lookup),
            duration_seconds=segment_duration_seconds(segment, track_lookup),
        )
        for segment in generated.sets
    ]

    encore_details: Optional[SegmentDetails] = None
    if generated.encore:
        encore_details = SegmentDetails(
            label=generated.encore.label,
            songs=list(generated.encore.songs),
            tracks=expand_tracks(generated.encore.songs, track_lookup),
            duration_seconds=segment_duration_seconds(generated.encore, track_lookup),
        )

    _update_duration_notes_with_actuals(metadata, segments_details, encore_details)

    if request.include_playlist and playlist_artifacts:
        for title in playlist_artifacts.missing_tracks:
            note = f"Playlist missing audio for {title} in local archive"
            if note not in metadata.notes:
                metadata.notes.append(note)

        # NEW: Add segue notes to metadata
        for segue_note in playlist_artifacts.segue_notes:
            if segue_note not in metadata.notes:
                metadata.notes.append(segue_note)

        # CRITICAL FIX: Update segments_details.tracks to match playlist_artifacts.sections
        # This ensures injected rare segue tracks appear in the main sets response
        if playlist_artifacts.sections:
            for i, (section_label, section_tracks) in enumerate(playlist_artifacts.sections):
                # Match section to corresponding segment by label
                matching_segment = None
                if section_label == "Encore" and encore_details:
                    encore_details.tracks = list(section_tracks)
                else:
                    for segment in segments_details:
                        if segment.label == section_label:
                            matching_segment = segment
                            break

                    if matching_segment:
                        # Update the tracks list to include injected tracks
                        matching_segment.tracks = list(section_tracks)
                        # Recalculate duration
                        matching_segment.duration_seconds = sum(
                            t.duration_seconds for t in section_tracks if t.duration_seconds
                        )

    return GenerationResult(
        seed=seed,
        generated_at=generated_at,
        generated=generated,
        segments=segments_details,
        encore=encore_details,
        playlist=playlist_artifacts,
    )
