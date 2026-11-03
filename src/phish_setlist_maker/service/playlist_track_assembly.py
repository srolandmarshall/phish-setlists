"""Track selection and segue injection for playlist artifacts."""

from __future__ import annotations

import logging
from random import Random
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from ..generator.core import SetSegment
from .catalog import SongCatalog, determine_origin_from_entry, normalize_title, split_song_titles
from .errors import PlaylistServiceError
from .models import PlaylistArtifacts, SongDisplay
from .playlist_duration import calculate_songs_to_skip, estimate_duration_compensation
from .playlist_queries import _load_song_duration_stats, _load_track_song_metadata
from .playlist_sections import _build_sections, _render_m3u, _process_segment_tracks
from .tracks import CandidateTrack, query_tracks_for_song, resolve_track_metadata

logger = logging.getLogger("uvicorn.error")


def build_playlist_artifacts(
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
    track_selector: Callable = None,
) -> PlaylistArtifacts:
    if track_selector is None:
        raise ValueError("track_selector callable is required.")

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

    song_duration_stats: Dict[str, object] = {}
    if set_lengths:
        requested_slugs = []
        for segment in [*segments, *([encore] if encore else [])]:
            for raw_song in segment.songs:
                for title in split_song_titles(raw_song):
                    entry = catalog.by_title.get(normalize_title(title))
                    if entry:
                        requested_slugs.append(entry.slug)
        song_duration_stats = _load_song_duration_stats(db_session, requested_slugs)

    continuation_records: Dict[int, object] = {}
    continuation_lookup_ids: Set[int] = set()
    attempted_continuation_ids: Set[int] = set()

    def load_continuation_records(track_ids: Sequence[int]) -> None:
        missing_ids = [track_id for track_id in dict.fromkeys(track_ids) if track_id not in continuation_records]
        continuation_records.update(_load_track_song_metadata(db_session, missing_ids))
        continuation_lookup_ids.update(missing_ids)

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
                display = track_selector(
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
            load_continuation_records(display.rare_segue_next_tracks)
            for next_track_id in display.rare_segue_next_tracks:
                # Avoid injecting same track twice
                if next_track_id in injected_segue_tracks:
                    continue
                injected_segue_tracks.add(next_track_id)
                
                metadata = continuation_records.get(next_track_id)
                if not metadata or metadata.song_id is None:
                    continue
                
                # Create CandidateTrack for the segue continuation
                candidate = CandidateTrack(
                    track_id=next_track_id,
                    slug=metadata.track_slug,
                    duration=metadata.duration,
                    show_date=None,
                    likes_count=metadata.likes_count or 0,
                    metadata_cache=metadata.metadata_cache,
                )
                
                # Resolve metadata
                attempted_continuation_ids.add(next_track_id)
                mp3_url, remote_duration, remote_show_date = resolve_track_metadata(
                    db_session,
                    candidate,
                    song_slug=metadata.song_slug,
                    rng=rng,
                    strict=False,
                )
                
                if mp3_url:
                    duration_seconds = candidate.duration if candidate.duration else remote_duration
                    if duration_seconds and duration_seconds > 6000:
                        duration_seconds = duration_seconds // 1000

                    logger.info("🎰 INJECTING RARE SEGUE: %s (track_id=%s)", metadata.song_title, next_track_id)

                    # Add lottery ticket note
                    show_date_str = remote_show_date or "unknown date"
                    lottery_note = f"🎰 Lottery ticket! Rare {display.title} → {metadata.song_title} from {show_date_str}"
                    if lottery_note not in segue_notes:
                        segue_notes.append(lottery_note)

                    # Add to playlist
                    if include_m3u:
                        duration_sec = duration_seconds if duration_seconds is not None else -1
                        playlist_lines.append(f"#EXTINF:{duration_sec},{metadata.song_title} [{show_date_str}] (rare segue)")
                        playlist_lines.append(mp3_url)

                    # CRITICAL: Add the injected track to track_cache so it appears in the response!
                    # Create a SongDisplay for the continuation track
                    continuation_display = SongDisplay(
                        title=metadata.song_title,
                        mp3_url=mp3_url,
                        duration_seconds=duration_seconds,
                        origin=None,  # Could determine from catalog if needed
                        show_date=show_date_str,
                        track_id=next_track_id,
                        is_segue=True,
                        segue_type="lottery_ticket",
                        segue_pattern=f"{display.title} -> {metadata.song_title}",
                        segue_position=2,  # This is the continuation track
                        segue_group_id=display.segue_group_id,  # Use same group_id as source
                        historical_occurrences=display.historical_occurrences,
                        rarity_score=display.rarity_score,
                        likes_count=candidate.likes_count,
                    )

                    # Add to cache so it appears in response tracks
                    cache_key = normalize_title(metadata.song_title)
                    track_cache[cache_key] = continuation_display

        # MANDATORY SEGUE INJECTION: Check if this track has mandatory pattern continuations
        if display.mandatory_pattern_songs and segment_label:
            logger.info("🔗 Mandatory pattern injection for %s: %s", song_title, " -> ".join(display.mandatory_pattern_songs))
            load_continuation_records(display.mandatory_next_tracks or [])

            for i, pattern_song in enumerate(display.mandatory_pattern_songs):
                # Mark this song as injected so we don't process it again from the songs array
                mandatory_injected_songs.add((segment_label, pattern_song))
                # Check if we already have a specific track_id for this song
                if display.mandatory_next_tracks and i < len(display.mandatory_next_tracks):
                    # Use the specific track from the same show
                    next_track_id = display.mandatory_next_tracks[i]
                else:
                    # Need to select a random track for this song
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

                metadata = continuation_records.get(next_track_id)
                if metadata is None:
                    load_continuation_records([next_track_id])
                    metadata = continuation_records.get(next_track_id)
                if not metadata or metadata.song_id is None:
                    continue

                # Create CandidateTrack
                candidate = CandidateTrack(
                    track_id=next_track_id,
                    slug=metadata.track_slug,
                    duration=metadata.duration,
                    show_date=None,
                    likes_count=metadata.likes_count or 0,
                    metadata_cache=metadata.metadata_cache,
                )

                # Resolve metadata
                attempted_continuation_ids.add(next_track_id)
                mp3_url, remote_duration, remote_show_date = resolve_track_metadata(
                    db_session, candidate, song_slug=metadata.song_slug, rng=rng, strict=False
                )

                if mp3_url:
                    duration_seconds = candidate.duration if candidate.duration else remote_duration
                    if duration_seconds and duration_seconds > 6000:
                        duration_seconds = duration_seconds // 1000
                    show_date_str = remote_show_date or "unknown"

                    logger.info("🔗 Injecting mandatory continuation: %s (track_id=%s)", metadata.song_title, next_track_id)

                    # Add to playlist
                    if include_m3u:
                        duration_sec = duration_seconds if duration_seconds is not None else -1
                        playlist_lines.append(f"#EXTINF:{duration_sec},{metadata.song_title} [{show_date_str}] (mandatory segue)")
                        playlist_lines.append(mp3_url)

                    # Add to track_cache
                    cache_key = normalize_title(metadata.song_title)
                    origin_key = normalize_title(metadata.song_title)
                    origin_entry = catalog.by_title.get(origin_key)
                    origin = determine_origin_from_entry(origin_entry) if origin_entry else None

                    continuation_display = SongDisplay(
                        title=metadata.song_title,
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
            for next_track_id in display.rare_segue_next_tracks:
                metadata = continuation_records.get(next_track_id)
                if metadata and metadata.duration:
                    duration = metadata.duration
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
            if display.mandatory_next_tracks:
                for next_track_id in display.mandatory_next_tracks:
                    metadata = continuation_records.get(next_track_id)
                    if metadata and metadata.duration:
                        duration = metadata.duration
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
        overage = 0
        if total_added_duration > 0 and current_segment_songs and segment_label and set_lengths:
            target_duration = set_lengths.get(segment_label)
            if target_duration:
                current_duration = 0
                for song in current_segment_songs:
                    normalized = normalize_title(song)
                    entry = catalog.by_title.get(normalized)
                    if entry:
                        stats = song_duration_stats.get(entry.slug)
                        avg_dur = stats.avg_duration if stats else None
                        if avg_dur:
                            if avg_dur > 6000:
                                avg_dur = avg_dur / 1000
                            current_duration += int(avg_dur)

                projected_total = current_duration + total_added_duration
                max_threshold = target_duration * 1.15  # 15% over target
                overage = estimate_duration_compensation(
                    current_duration, total_added_duration, target_duration
                )
                if overage:
                    logger.info(
                        "📊 Set %s: projected=%ds, target=%ds, max_threshold=%ds (15%% over), overage=%ds - will compensate",
                        segment_label,
                        projected_total,
                        target_duration,
                        int(max_threshold),
                        int(overage),
                    )
                else:
                    logger.info(
                        "📊 Set %s: projected=%ds, target=%ds, max_threshold=%ds (15%% over) - no compensation needed",
                        segment_label,
                        projected_total,
                        target_duration,
                        int(max_threshold),
                    )

        if overage > 0:
            to_skip = calculate_songs_to_skip(
                segment_label,
                current_segment_songs,
                song_title,  # Don't include the trigger song itself
                overage,  # Remove songs equal to the overage, not the lottery duration
                catalog=catalog,
                song_duration_stats=song_duration_stats,
            )
            songs_to_skip.update(to_skip)
            if to_skip:
                logger.info(
                    "  Will skip %d songs to compensate for overage (%ds): %s",
                    len(to_skip),
                    int(overage),
                    ", ".join(f"{label}/{title}" for label, title in to_skip)
                )

    _process_segment_tracks(segments, encore, append_track_with_injection)

    sections = _build_sections(
        db_session,
        segments,
        encore,
        catalog=catalog,
        track_cache=track_cache,
        songs_to_skip=songs_to_skip,
        mandatory_injected_songs=mandatory_injected_songs,
        feature_store=feature_store,
        rng=rng,
        continuation_records=continuation_records,
        continuation_lookup_ids=continuation_lookup_ids,
        attempted_continuation_ids=attempted_continuation_ids,
    )

    m3u_text = _render_m3u(sections, include_m3u)

    missing_titles = list(missing.keys())
    return PlaylistArtifacts(
        sections=sections,
        first_track_url=first_track_url,
        m3u_text=m3u_text,
        missing_tracks=missing_titles,
        segue_notes=segue_notes,
    )
