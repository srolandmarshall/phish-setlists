
"""Playlist artifact builder extracted from generation service."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple
from random import Random

from sqlalchemy.orm import Session

from ..generator.core import SetSegment
from .catalog import SongCatalog, normalize_title, split_song_titles, determine_origin_from_entry
from .errors import PlaylistServiceError
from .models import PlaylistArtifacts, SongDisplay
from .tracks import query_tracks_for_song

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
