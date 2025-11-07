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
    max_segues_per_set: int = 2  # Maximum segue patterns (mandatory + lottery) per set


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
    jamminess: Optional[float] = None,  # NEW: 0.0-1.0 scale for lottery ticket probability
    segues_per_segment: Optional[Dict[str, int]] = None,  # NEW: Track segue patterns per segment
    max_segues_per_set: int = 2,  # NEW: Maximum segue patterns per set
    segment_label: Optional[str] = None,  # NEW: Segment label for tracking
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

    # NEW: Check for mandatory segue patterns and determine what to inject
    mandatory_next_tracks: Optional[List[int]] = None
    mandatory_pattern_songs: Optional[List[str]] = None

    if feature_store:
        mandatory_segues = feature_store.get_mandatory_segues(song_title)
        if mandatory_segues:
            # Check if we've already reached the segue limit for this segment
            if segues_per_segment and segment_label:
                current_count = segues_per_segment.get(segment_label, 0)
                if current_count >= max_segues_per_set:
                    logger.info(
                        "⏭️  Skipping mandatory segue for %s - already at limit (%d/%d) for %s",
                        song_title, current_count, max_segues_per_set, segment_label
                    )
                    mandatory_segues = []  # Clear to skip processing below

        if mandatory_segues:
            # This song has mandatory patterns (e.g., Mike's Song)
            # Build the expected continuation pattern
            # Find the complete chain by following mandatory segues
            pattern_chain = [song_title]
            visited = {song_title}
            current_song = song_title

            while True:
                found_next = False
                for segue in feature_store.get_mandatory_segues(current_song):
                    songs_in_segue = segue.get('songs', [])
                    if len(songs_in_segue) >= 2 and songs_in_segue[0] == current_song:
                        next_song = songs_in_segue[1]
                        if next_song not in visited:
                            pattern_chain.append(next_song)
                            visited.add(next_song)
                            current_song = next_song
                            found_next = True
                            break
                if not found_next:
                    break

            # pattern_chain now contains the expected songs (e.g., ["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"])
            if len(pattern_chain) > 1:
                continuation_songs = pattern_chain[1:]  # Everything after the current song

                # Increment the segue counter for this segment
                if segues_per_segment and segment_label:
                    segues_per_segment[segment_label] = segues_per_segment.get(segment_label, 0) + 1
                    logger.info(
                        "✅ Injecting mandatory segue for %s (count: %d/%d for %s)",
                        song_title, segues_per_segment[segment_label], max_segues_per_set, segment_label
                    )

                # Check what actually followed this track in its show
                if same_show_segues:
                    following_tracks = feature_store.get_following_tracks_from_show(db_session, selection.track_id, max_tracks=len(continuation_songs))

                    # Check if the following tracks match the expected pattern
                    tracks_match_pattern = True
                    if len(following_tracks) >= len(continuation_songs):
                        for i, expected_song in enumerate(continuation_songs):
                            actual_title = following_tracks[i]['title']
                            # Normalize comparison (remove > symbols for matching)
                            actual_title_normalized = actual_title.replace(' >', '').replace('>', '').strip()
                            if actual_title_normalized != expected_song:
                                tracks_match_pattern = False
                                break
                    else:
                        tracks_match_pattern = False

                    if tracks_match_pattern:
                        # Use the actual tracks from that show
                        mandatory_next_tracks = [t['track_id'] for t in following_tracks[:len(continuation_songs)]]
                        mandatory_pattern_songs = continuation_songs
                        logger.info(
                            "Following mandatory pattern from show for %s: %s",
                            song_title,
                            " -> ".join(pattern_chain)
                        )
                    else:
                        # Tracks don't match pattern - inject random tracks
                        mandatory_next_tracks = []  # Will be populated with random tracks later
                        mandatory_pattern_songs = continuation_songs
                        logger.info(
                            "Track doesn't follow expected pattern - will inject random tracks for: %s",
                            " -> ".join(continuation_songs)
                        )
                else:
                    # same_show_segues=false - always inject random tracks
                    mandatory_next_tracks = []  # Will be populated with random tracks later
                    mandatory_pattern_songs = continuation_songs
                    logger.info(
                        "Injecting random tracks for mandatory pattern: %s -> %s",
                        song_title,
                        " -> ".join(continuation_songs)
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
        # Check if we've already reached the segue limit for this segment
        can_inject_lottery = True
        if segues_per_segment and segment_label:
            current_count = segues_per_segment.get(segment_label, 0)
            if current_count >= max_segues_per_set:
                logger.info(
                    "⏭️  Skipping lottery ticket check for %s - already at limit (%d/%d) for %s",
                    song_title, current_count, max_segues_per_set, segment_label
                )
                can_inject_lottery = False

        rare_segues = feature_store.get_rare_segues_from_track(selection.track_id) if can_inject_lottery else []
        if rare_segues:
            # Lottery ticket: probability scales with jamminess (0-10%)
            # jamminess=0.0 → 0%, jamminess=0.5 → 5%, jamminess=1.0 → 10%
            effective_jamminess = jamminess if jamminess is not None else 0.5
            lottery_chance = effective_jamminess * 0.1
            if rng.random() < lottery_chance:
                # Pick one of the rare segues at random
                selected_segue = rng.choice(rare_segues)

                # Extract next track IDs from rare segue patterns
                # Coin flip (50/50) for EACH continuation track to keep chains rare
                rare_segue_next_tracks = []
                tracks_in_pattern = selected_segue.get('tracks', [])
                # Find this track's position and get subsequent tracks
                if selection.track_id in tracks_in_pattern:
                    idx = tracks_in_pattern.index(selection.track_id)
                    # Flip a coin for each following track (50% chance each)
                    # Result: 50% get 1 track, 25% get 2 tracks, 12.5% get 3, etc.
                    for i in range(idx + 1, len(tracks_in_pattern)):
                        if rng.random() < 0.5:  # Coin flip
                            rare_segue_next_tracks.append(tracks_in_pattern[i])
                        else:
                            break  # Stop at first tails

                if rare_segue_next_tracks:
                    # Increment the segue counter for this segment
                    if segues_per_segment and segment_label:
                        segues_per_segment[segment_label] = segues_per_segment.get(segment_label, 0) + 1
                        logger.info(
                            "✅ Injecting lottery ticket for %s (count: %d/%d for %s)",
                            song_title, segues_per_segment[segment_label], max_segues_per_set, segment_label
                        )

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
        mandatory_next_tracks=mandatory_next_tracks,
        mandatory_pattern_songs=mandatory_pattern_songs,
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
    jamminess: Optional[float] = None,  # NEW: 0.0-1.0 scale for lottery ticket probability
    set_lengths: Optional[Dict[str, int]] = None,  # NEW: Target durations for each segment
    max_segues_per_set: int = 2,  # NEW: Maximum segue patterns (mandatory + lottery) per set
) -> PlaylistArtifacts:
    track_cache: Dict[str, Optional[SongDisplay]] = {}
    missing: Dict[str, int] = {}
    playlist_lines: List[str] = ["#EXTM3U"] if include_m3u else []
    first_track_url: Optional[str] = None
    injected_segue_tracks: Set[int] = set()  # PHASE 4.2: Track IDs already injected
    segue_notes: List[str] = []  # NEW: Collect notes about segues
    segue_context: Dict[str, int] = {}  # NEW: Maps song_title -> predetermined track_id for same-show segues
    songs_to_skip: Set[Tuple[str, str]] = set()  # NEW: (segment_label, song_title) tuples to skip for lottery compensation
    mandatory_injected_songs: Set[Tuple[str, str]] = set()  # NEW: (segment_label, song_title) tuples already injected as mandatory continuations
    segues_per_segment: Dict[str, int] = {}  # NEW: Track segue patterns injected per segment

    def append_track(song_title: str, is_set_ender: bool = False, canonical_set: Optional[str] = None, segment_label: Optional[str] = None) -> None:
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
                    jamminess=jamminess,  # NEW: Pass jamminess for lottery probability
                    segues_per_segment=segues_per_segment,  # NEW: Pass segue counter
                    max_segues_per_set=max_segues_per_set,  # NEW: Pass segue limit
                    segment_label=segment_label,  # NEW: Pass segment label
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

        # MANDATORY SEGUE INJECTION: Check if this track has mandatory pattern continuations
        if display.mandatory_pattern_songs and segment_label:
            logger.info("🔗 Mandatory pattern injection for %s: %s", song_title, " -> ".join(display.mandatory_pattern_songs))

            for i, pattern_song in enumerate(display.mandatory_pattern_songs):
                # Mark this song as injected so we don't process it again from the songs array
                mandatory_injected_songs.add((segment_label, pattern_song))
                # Check if we already have a specific track_id for this song
                if display.mandatory_next_tracks and i < len(display.mandatory_next_tracks):
                    # Use the specific track from the same show
                    next_track_id = display.mandatory_next_tracks[i]
                else:
                    # Need to select a random track for this song
                    from ..models import Song, SongTrack
                    normalized = normalize_title(pattern_song)
                    entry = catalog.by_title.get(normalized)
                    if not entry:
                        logger.warning("Could not find catalog entry for mandatory pattern song: %s", pattern_song)
                        continue

                    # Query random track for this song
                    candidates = query_tracks_for_song(db_session, entry.slug)
                    if not candidates:
                        logger.warning("No tracks found for mandatory pattern song: %s", pattern_song)
                        continue

                    random_candidate = rng.choice(candidates)
                    next_track_id = random_candidate.track_id

                # Avoid injecting same track twice
                if next_track_id in injected_segue_tracks:
                    continue
                injected_segue_tracks.add(next_track_id)

                # Fetch track metadata
                from ..models import Track, SongTrack, Song
                track_row = db_session.query(
                    Track.id, Track.slug, Track.duration, Track.likes_count,
                    Track.metadata_cache, Track.show_id, Track.set, Track.position
                ).filter(Track.id == next_track_id).first()
                if not track_row:
                    continue

                song_track = db_session.query(SongTrack).filter(SongTrack.track_id == next_track_id).first()
                if not song_track:
                    continue
                song_obj = db_session.query(Song).filter(Song.id == song_track.song_id).first()
                if not song_obj:
                    continue

                # Create CandidateTrack
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
                    db_session, candidate, song_slug=song_obj.slug, rng=rng, strict=False
                )

                if mp3_url:
                    duration_seconds = candidate.duration if candidate.duration else remote_duration
                    if duration_seconds and duration_seconds > 6000:
                        duration_seconds = duration_seconds // 1000
                    show_date_str = remote_show_date or "unknown"

                    logger.info("🔗 Injecting mandatory continuation: %s (track_id=%s)", song_obj.title, next_track_id)

                    # Add to playlist
                    if include_m3u:
                        duration_sec = duration_seconds if duration_seconds is not None else -1
                        playlist_lines.append(f"#EXTINF:{duration_sec},{song_obj.title} [{show_date_str}] (mandatory segue)")
                        playlist_lines.append(mp3_url)

                    # Add to track_cache
                    cache_key = normalize_title(song_obj.title)
                    origin_key = normalize_title(song_obj.title)
                    origin_entry = catalog.by_title.get(origin_key)
                    origin = determine_origin_from_entry(origin_entry) if origin_entry else None

                    continuation_display = SongDisplay(
                        title=song_obj.title,
                        mp3_url=mp3_url,
                        duration_seconds=duration_seconds,
                        origin=origin,
                        show_date=show_date_str,
                        track_id=next_track_id,
                        is_segue=True,
                        segue_type="mandatory",
                        segue_pattern=f"{song_title} -> {' -> '.join(display.mandatory_pattern_songs)}",
                        segue_position=i + 2,  # Position in the pattern (root song is 1, this is 2+)
                    )
                    track_cache[cache_key] = continuation_display

    def calculate_songs_to_skip(
        segment_label: str,
        current_segment_songs: List[str],
        current_song_title: str,
        duration_to_compensate: int
    ) -> List[Tuple[str, str]]:
        """
        Calculate which songs to skip based on lowest likes and duration compensation.

        Looks at ALL songs in the segment (not just remaining ones) and picks the
        least-liked songs that make up the time difference. This works whether the
        lottery ticket is at the end, middle, or beginning of the set.

        Args:
            duration_to_compensate: The amount of time (in seconds) we need to remove
                                   from the set to bring it within tolerance.

        Returns list of (segment_label, song_title) tuples to skip.
        """
        # Query database for average duration and likes for ALL songs in segment
        from ..models import Song, SongTrack, Track
        from sqlalchemy import func

        song_stats = []
        for song_title in current_segment_songs:
            # Don't include the song that triggered the lottery ticket itself
            if song_title == current_song_title:
                continue

            # Normalize and find in catalog
            normalized = normalize_title(song_title)
            entry = catalog.by_title.get(normalized)
            if not entry:
                continue

            # Query average duration and likes for this song
            stats = db_session.query(
                func.avg(Track.duration).label('avg_duration'),
                func.avg(Track.likes_count).label('avg_likes'),
            ).join(SongTrack).join(Song).filter(
                Song.slug == entry.slug
            ).first()

            if stats and stats.avg_duration:
                avg_duration = stats.avg_duration
                # Convert from milliseconds if needed
                if avg_duration > 6000:
                    avg_duration = avg_duration / 1000
                avg_likes = stats.avg_likes or 0

                song_stats.append({
                    'title': song_title,
                    'avg_duration': int(avg_duration),
                    'avg_likes': int(avg_likes),
                })

        if not song_stats:
            return []

        # Sort by likes (ascending) - lowest likes first
        song_stats.sort(key=lambda x: x['avg_likes'])

        # Greedily select songs until we've compensated for the overage
        to_skip = []
        compensated_duration = 0
        for stat in song_stats:
            if compensated_duration >= duration_to_compensate:
                break
            to_skip.append((segment_label, stat['title']))
            compensated_duration += stat['avg_duration']
            logger.info(
                "  Marking %s/%s for removal (likes: %d, duration: %ds, total compensated: %ds/%ds)",
                segment_label,
                stat['title'],
                stat['avg_likes'],
                stat['avg_duration'],
                compensated_duration,
                duration_to_compensate
            )

        return to_skip

    def append_track_with_injection(
        song_title: str,
        is_set_ender: bool = False,
        canonical_set: Optional[str] = None,
        current_segment_songs: Optional[List[str]] = None,
        current_song_index: int = 0,
        segment_label: Optional[str] = None
    ) -> None:
        # Skip if this song was marked for removal due to lottery compensation IN THIS SEGMENT
        if segment_label and (segment_label, song_title) in songs_to_skip:
            logger.info("⏭️  Skipping %s/%s (lottery compensation)", segment_label, song_title)
            return

        # Skip if this song was already injected as a mandatory continuation
        if segment_label and (segment_label, song_title) in mandatory_injected_songs:
            logger.info("⏭️  Skipping %s/%s (already injected as mandatory continuation)", segment_label, song_title)
            return

        append_track(song_title, is_set_ender, canonical_set, segment_label)

        # After processing, check if we just triggered a lottery ticket or mandatory pattern
        # If so, calculate which songs to skip based on likes and duration
        normalized = normalize_title(song_title)
        display = track_cache.get(normalized)
        total_added_duration = 0

        # Calculate total added duration from lottery tickets
        if display and display.rare_segue_next_tracks:
            from ..models import Track
            for next_track_id in display.rare_segue_next_tracks:
                track_row = db_session.query(Track.duration).filter(Track.id == next_track_id).first()
                if track_row and track_row.duration:
                    duration = track_row.duration
                    if duration > 6000:
                        duration = duration // 1000
                    total_added_duration += duration

            logger.info(
                "🎰 Lottery ticket triggered for %s with %d continuation tracks (total duration: %ds)",
                song_title,
                len(display.rare_segue_next_tracks),
                total_added_duration
            )

        # Calculate total added duration from mandatory patterns
        if display and display.mandatory_pattern_songs:
            from ..models import Track
            if display.mandatory_next_tracks:
                for next_track_id in display.mandatory_next_tracks:
                    track_row = db_session.query(Track.duration).filter(Track.id == next_track_id).first()
                    if track_row and track_row.duration:
                        duration = track_row.duration
                        if duration > 6000:
                            duration = duration // 1000
                        total_added_duration += duration
            else:
                # Estimate duration for random tracks (use average)
                # For now, estimate ~7 minutes per song (420 seconds)
                total_added_duration += len(display.mandatory_pattern_songs) * 420

            logger.info(
                "🔗 Mandatory pattern triggered for %s with %d continuation songs (estimated duration: %ds)",
                song_title,
                len(display.mandatory_pattern_songs),
                total_added_duration
            )

        # Calculate which songs to skip from entire segment (only if we added significant duration)
        # Only compensate if set would be >15% over target duration
        should_compensate = False
        overage = 0
        if total_added_duration > 0 and current_segment_songs and segment_label and set_lengths:
            # Get target duration for this segment
            target_duration = set_lengths.get(segment_label)
            if target_duration:
                # Calculate estimated current segment duration
                from ..models import Track, Song, SongTrack
                from sqlalchemy import func
                current_duration = 0
                for song in current_segment_songs:
                    normalized = normalize_title(song)
                    entry = catalog.by_title.get(normalized)
                    if entry:
                        # Query average duration for this song
                        avg_dur = db_session.query(func.avg(Track.duration)).join(SongTrack).join(Song).filter(
                            Song.slug == entry.slug
                        ).scalar()
                        if avg_dur:
                            if avg_dur > 6000:
                                avg_dur = avg_dur / 1000
                            current_duration += int(avg_dur)

                # Calculate what total would be with added duration
                projected_total = current_duration + total_added_duration
                max_threshold = target_duration * 1.15  # 15% over target
                min_threshold = target_duration * 0.95  # 5% under target

                if projected_total > max_threshold:
                    # We're over the max threshold, need to compensate
                    overage = projected_total - max_threshold

                    # But don't remove so many songs that we go under the min threshold
                    # Calculate maximum we can remove
                    max_can_remove = projected_total - min_threshold
                    overage_to_remove = min(overage, max_can_remove)

                    if overage_to_remove > 0:
                        should_compensate = True
                        overage = overage_to_remove
                        logger.info(
                            "📊 Set %s: projected=%ds, target=%ds, max_threshold=%ds (15%% over), min_threshold=%ds (5%% under), overage=%ds - will compensate",
                            segment_label, projected_total, target_duration, int(max_threshold), int(min_threshold), int(overage)
                        )
                    else:
                        overage = 0
                        logger.info(
                            "📊 Set %s: projected=%ds over max but can't remove without going under min_threshold=%ds - no compensation",
                            segment_label, projected_total, int(min_threshold)
                        )
                else:
                    overage = 0
                    logger.info(
                        "📊 Set %s: projected=%ds, target=%ds, max_threshold=%ds (15%% over) - no compensation needed",
                        segment_label, projected_total, target_duration, int(max_threshold)
                    )

        if should_compensate:
            to_skip = calculate_songs_to_skip(
                segment_label,
                current_segment_songs,
                song_title,  # Don't include the trigger song itself
                overage  # Remove songs equal to the overage, not the lottery duration
            )
            songs_to_skip.update(to_skip)
            if to_skip:
                logger.info(
                    "  Will skip %d songs to compensate for overage (%ds): %s",
                    len(to_skip),
                    int(overage),
                    ", ".join(f"{label}/{title}" for label, title in to_skip)
                )

    for segment in segments:
        from ..generator.historical import normalize_set_label
        canonical = normalize_set_label(segment.label) if segment.label else None

        # Flatten segment songs for indexing
        segment_songs_flat = []
        for raw_song in segment.songs:
            segment_songs_flat.extend(split_song_titles(raw_song))

        song_idx = 0
        for idx, raw_song in enumerate(segment.songs):
            is_last = (idx == len(segment.songs) - 1)
            for title in split_song_titles(raw_song):
                append_track_with_injection(
                    title,
                    is_set_ender=is_last,
                    canonical_set=canonical,
                    current_segment_songs=segment_songs_flat,
                    current_song_index=song_idx,
                    segment_label=segment.label
                )
                song_idx += 1

    if encore:
        # Flatten encore songs for indexing
        encore_songs_flat = []
        for raw_song in encore.songs:
            encore_songs_flat.extend(split_song_titles(raw_song))

        song_idx = 0
        for idx, raw_song in enumerate(encore.songs):
            is_last = (idx == len(encore.songs) - 1)
            for title in split_song_titles(raw_song):
                append_track_with_injection(
                    title,
                    is_set_ender=is_last,
                    canonical_set="encore",
                    current_segment_songs=encore_songs_flat,
                    current_song_index=song_idx,
                    segment_label=encore.label
                )
                song_idx += 1

    sections: List[Tuple[str, List[SongDisplay]]] = []
    for segment in segments:
        rows: List[SongDisplay] = []
        for raw_song in segment.songs:
            for title in split_song_titles(raw_song):
                # Skip songs that were removed to compensate for lottery ticket injections IN THIS SEGMENT
                if (segment.label, title) in songs_to_skip:
                    logger.info("⏭️  Skipping %s/%s in sections building (lottery compensation)", segment.label, title)
                    continue

                # Skip songs that were already injected as mandatory continuations
                if (segment.label, title) in mandatory_injected_songs:
                    logger.info("⏭️  Skipping %s/%s in sections building (already injected as mandatory)", segment.label, title)
                    continue

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

                                # Try to get origin from catalog
                                origin_key = normalize_title(song.title)
                                origin_entry = catalog.by_title.get(origin_key)
                                origin = determine_origin_from_entry(origin_entry) if origin_entry else None

                                continuation_display = SongDisplay(
                                    title=song.title,
                                    mp3_url=mp3_url,
                                    duration_seconds=duration_seconds,
                                    origin=origin,
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

                    # If this track has mandatory pattern continuations, add them to the section
                    if display.mandatory_pattern_songs and feature_store:
                        from ..models import Track, SongTrack, Song
                        for i, pattern_song in enumerate(display.mandatory_pattern_songs):
                            # Get track_id (either from list or need to query)
                            if display.mandatory_next_tracks and i < len(display.mandatory_next_tracks):
                                next_track_id = display.mandatory_next_tracks[i]
                            else:
                                # Already injected in M3U phase, should be in track_cache
                                cache_key = normalize_title(pattern_song)
                                if cache_key in track_cache:
                                    cached_display = track_cache.get(cache_key)
                                    if cached_display and cached_display.track_id:
                                        next_track_id = cached_display.track_id
                                    else:
                                        continue
                                else:
                                    continue

                            # Check if already added to THIS section's rows
                            if any(r.track_id == next_track_id for r in rows):
                                continue

                            # Get from cache or fetch
                            cache_key = normalize_title(pattern_song)
                            if cache_key in track_cache:
                                continuation_display = track_cache.get(cache_key)
                                if continuation_display:
                                    rows.append(continuation_display)
                            else:
                                # Shouldn't happen, but handle it
                                logger.warning("Mandatory continuation track not in cache: %s", pattern_song)

                else:
                    entry = catalog.by_title.get(key)
                    origin = determine_origin_from_entry(entry) if entry else None
                    rows.append(SongDisplay(title=title, origin=origin))
        sections.append((segment.label, rows))

    if encore:
        encore_rows: List[SongDisplay] = []
        for raw_song in encore.songs:
            for title in split_song_titles(raw_song):
                # Skip songs that were removed to compensate for lottery ticket injections IN ENCORE
                if (encore.label, title) in songs_to_skip:
                    logger.info("⏭️  Skipping %s/%s in encore building (lottery compensation)", encore.label, title)
                    continue

                # Skip songs that were already injected as mandatory continuations
                if (encore.label, title) in mandatory_injected_songs:
                    logger.info("⏭️  Skipping %s/%s in encore building (already injected as mandatory)", encore.label, title)
                    continue

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

                                # Try to get origin from catalog
                                origin_key = normalize_title(song.title)
                                origin_entry = catalog.by_title.get(origin_key)
                                origin = determine_origin_from_entry(origin_entry) if origin_entry else None

                                continuation_display = SongDisplay(
                                    title=song.title,
                                    mp3_url=mp3_url,
                                    duration_seconds=duration_seconds,
                                    origin=origin,
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

                    # If this track has mandatory pattern continuations, add them to encore
                    if display.mandatory_pattern_songs and feature_store:
                        from ..models import Track, SongTrack, Song
                        for i, pattern_song in enumerate(display.mandatory_pattern_songs):
                            # Get track_id (either from list or need to query)
                            if display.mandatory_next_tracks and i < len(display.mandatory_next_tracks):
                                next_track_id = display.mandatory_next_tracks[i]
                            else:
                                # Already injected in M3U phase, should be in track_cache
                                cache_key = normalize_title(pattern_song)
                                if cache_key in track_cache:
                                    cached_display = track_cache.get(cache_key)
                                    if cached_display and cached_display.track_id:
                                        next_track_id = cached_display.track_id
                                    else:
                                        continue
                                else:
                                    continue

                            # Check if already added to encore rows
                            if any(r.track_id == next_track_id for r in encore_rows):
                                continue

                            # Get from cache or fetch
                            cache_key = normalize_title(pattern_song)
                            if cache_key in track_cache:
                                continuation_display = track_cache.get(cache_key)
                                if continuation_display:
                                    encore_rows.append(continuation_display)
                            else:
                                # Shouldn't happen, but handle it
                                logger.warning("Mandatory continuation track not in cache: %s", pattern_song)

                else:
                    entry = catalog.by_title.get(key)
                    origin = determine_origin_from_entry(entry) if entry else None
                    encore_rows.append(SongDisplay(title=title, origin=origin))
        sections.append((encore.label, encore_rows))

    # CRITICAL FIX: Rebuild M3U from final sections to ensure sync
    # The issue is that songs marked for skipping were added to M3U before we knew they'd be skipped
    if include_m3u:
        final_m3u_lines = ["#EXTM3U"]
        for section_label, section_tracks in sections:
            for track in section_tracks:
                if track.mp3_url:
                    duration_sec = track.duration_seconds if track.duration_seconds is not None else -1
                    show_date = track.show_date or "unknown date"
                    segue_tag = " (rare segue)" if track.segue_type == "lottery_ticket" else ""
                    final_m3u_lines.append(f"#EXTINF:{duration_sec},{track.title} [{show_date}]{segue_tag}")
                    final_m3u_lines.append(track.mp3_url)
        m3u_text = "\n".join(final_m3u_lines)
    else:
        m3u_text = None

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
            jamminess=request.jamminess,  # NEW: Pass jamminess for lottery probability
            set_lengths=set_lengths,  # NEW: Pass target durations for 15% threshold check
            max_segues_per_set=request.max_segues_per_set,  # NEW: Pass segue limit
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
