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
from .playlist_builder import build_playlist_artifacts
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
            if segues_per_segment is not None and segment_label:
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
                if segues_per_segment is not None and segment_label:
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
        if segues_per_segment is not None and segment_label:
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
                    if segues_per_segment is not None and segment_label:
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
    return build_playlist_artifacts(
        db_session=db_session,
        segments=segments,
        encore=encore,
        catalog=catalog,
        rng=rng,
        include_m3u=include_m3u,
        strict=strict,
        feature_store=feature_store,
        same_show_segues=same_show_segues,
        generated_setlist=generated_setlist,
        jamminess=jamminess,
        set_lengths=set_lengths,
        max_segues_per_set=max_segues_per_set,
        track_selector=_select_track_display,
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
        max_segues_per_set=request.max_segues_per_set,
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

        # PERFORMANCE: Prefetch track metadata in parallel before sequential processing
        # Collect all songs that will need tracks
        all_songs = []
        for segment in generated.sets:
            all_songs.extend(segment.songs)
        if generated.encore:
            all_songs.extend(generated.encore.songs)

        # Get one candidate track per song for prefetching
        from .tracks import query_tracks_for_song, batch_prefetch_track_metadata
        prefetch_candidates = []
        for song_title in all_songs:
            normalized = normalize_title(song_title)
            entry = catalog.by_title.get(normalized)
            if entry:
                # Get the top candidate (by likes_count) for this song
                candidates = query_tracks_for_song(session, entry.slug, limit=1)
                if candidates:
                    prefetch_candidates.append((candidates[0], entry.slug))

        # Batch prefetch metadata for all tracks in parallel (rate-limited)
        if prefetch_candidates:
            logger.info("Prefetching metadata for %d tracks before generation", len(prefetch_candidates))
            batch_prefetch_track_metadata(
                session,
                prefetch_candidates,
                max_workers=5,  # 5 concurrent requests to be nice to phish.in
                delay_between_requests=0.2,  # 200ms = max 5 req/sec
            )

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
