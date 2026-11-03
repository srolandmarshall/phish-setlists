"""Playlist section assembly and M3U rendering."""

from __future__ import annotations

import logging
from random import Random
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from ..generator.core import SetSegment
from ..models import Song, SongTrack, Track
from .catalog import SongCatalog, determine_origin_from_entry, normalize_title, split_song_titles
from .models import SongDisplay
from .playlist_queries import _load_track_song_metadata
from .tracks import CandidateTrack, resolve_track_metadata

logger = logging.getLogger("uvicorn.error")


def _placed_rare_continuation(
    db_session: Session,
    track_id: int,
    source: SongDisplay,
    position: int,
    *,
    catalog: SongCatalog,
    rng: Random,
    continuation_records: Dict[int, object],
    continuation_displays: Dict[int, SongDisplay],
    attempted_continuation_ids: Set[int],
) -> Optional[SongDisplay]:
    """Reuse or resolve one continuation, then apply source-specific segue details."""
    canonical = continuation_displays.get(track_id)
    if canonical is None:
        if track_id in attempted_continuation_ids:
            return None
        metadata = continuation_records.get(track_id)
        if metadata is None or metadata.song_id is None:
            return None

        candidate = CandidateTrack(
            track_id=track_id,
            slug=metadata.track_slug,
            duration=metadata.duration,
            show_date=None,
            likes_count=metadata.likes_count or 0,
            metadata_cache=metadata.metadata_cache,
        )
        attempted_continuation_ids.add(track_id)
        mp3_url, remote_duration, remote_show_date = resolve_track_metadata(
            db_session, candidate, song_slug=metadata.song_slug, rng=rng, strict=False
        )
        if not mp3_url:
            return None

        duration = candidate.duration if candidate.duration else remote_duration
        if duration and duration > 6000:
            duration //= 1000
        entry = catalog.by_title.get(normalize_title(metadata.song_title))
        canonical = SongDisplay(
            title=metadata.song_title,
            mp3_url=mp3_url,
            duration_seconds=duration,
            origin=determine_origin_from_entry(entry) if entry else None,
            show_date=remote_show_date or "unknown",
            track_id=track_id,
        )
        continuation_displays[track_id] = canonical

    # The performance/media fields are canonical per track. Segue details belong
    # to the source that introduced the continuation in this section.
    origin = canonical.origin
    if origin is None:
        entry = catalog.by_title.get(normalize_title(canonical.title))
        origin = determine_origin_from_entry(entry) if entry else None
    return SongDisplay(
        title=canonical.title,
        mp3_url=canonical.mp3_url,
        duration_seconds=canonical.duration_seconds,
        origin=origin,
        show_date=canonical.show_date,
        track_id=track_id,
        is_segue=True,
        segue_type="lottery_ticket",
        segue_pattern=source.segue_pattern,
        segue_position=position,
        segue_group_id=source.segue_group_id,
        historical_occurrences=source.historical_occurrences,
        rarity_score=source.rarity_score,
        likes_count=source.likes_count,
    )


def _build_section_rows(
    db_session: Session,
    songs: Sequence[str],
    *,
    label: str,
    catalog: SongCatalog,
    track_cache: Dict[str, Optional[SongDisplay]],
    songs_to_skip: Set[Tuple[str, str]],
    mandatory_injected_songs: Set[Tuple[str, str]],
    feature_store,
    rng: Random,
    continuation_records: Dict[int, object],
    continuation_displays: Dict[int, SongDisplay],
    attempted_continuation_ids: Set[int],
) -> List[SongDisplay]:
    rows: List[SongDisplay] = []
    injected_track_ids: Set[int] = set()
    for raw_song in songs:
        for title in split_song_titles(raw_song):
            if (label, title) in songs_to_skip or (label, title) in mandatory_injected_songs:
                continue

            display = track_cache.get(normalize_title(title))
            if display is None:
                entry = catalog.by_title.get(normalize_title(title))
                origin = determine_origin_from_entry(entry) if entry else None
                rows.append(SongDisplay(title=title, origin=origin))
                continue

            rows.append(display)
            if display.rare_segue_next_tracks and feature_store:
                for track_id in display.rare_segue_next_tracks:
                    if track_id in injected_track_ids:
                        continue
                    continuation = _placed_rare_continuation(
                        db_session,
                        track_id,
                        display,
                        len(rows) + 1,
                        catalog=catalog,
                        rng=rng,
                        continuation_records=continuation_records,
                        continuation_displays=continuation_displays,
                        attempted_continuation_ids=attempted_continuation_ids,
                    )
                    if continuation is not None:
                        rows.append(continuation)
                        injected_track_ids.add(track_id)

            if display.mandatory_pattern_songs and feature_store:
                for index, pattern_song in enumerate(display.mandatory_pattern_songs):
                    if display.mandatory_next_tracks and index < len(display.mandatory_next_tracks):
                        track_id = display.mandatory_next_tracks[index]
                    else:
                        cached = track_cache.get(normalize_title(pattern_song))
                        if cached is None or cached.track_id is None:
                            logger.warning("Mandatory continuation track not in cache: %s", pattern_song)
                            continue
                        track_id = cached.track_id

                    if track_id in injected_track_ids:
                        continue
                    continuation = track_cache.get(normalize_title(pattern_song))
                    if continuation is not None:
                        rows.append(continuation)
                        injected_track_ids.add(track_id)
    return rows


def _build_sections(
    db_session: Session,
    segments: Sequence[SetSegment],
    encore: Optional[SetSegment],
    *,
    catalog: SongCatalog,
    track_cache: Dict[str, Optional[SongDisplay]],
    songs_to_skip: Set[Tuple[str, str]],
    mandatory_injected_songs: Set[Tuple[str, str]],
    feature_store,
    rng: Random,
    continuation_records: Optional[Dict[int, object]] = None,
    continuation_lookup_ids: Optional[Set[int]] = None,
    attempted_continuation_ids: Optional[Set[int]] = None,
) -> List[Tuple[str, List[SongDisplay]]]:
    """Assemble set and encore rows, reusing canonical continuation metadata."""
    continuation_displays = {
        display.track_id: display
        for display in track_cache.values()
        if display is not None and display.track_id is not None
    }
    continuation_ids = list(dict.fromkeys(
        track_id
        for display in track_cache.values()
        if display is not None
        for track_id in (display.rare_segue_next_tracks or [])
        if track_id not in continuation_displays
        and (continuation_lookup_ids is None or track_id not in continuation_lookup_ids)
    ))
    if continuation_records is None:
        continuation_records = {}
    if feature_store and continuation_ids:
        continuation_records.update(_load_track_song_metadata(db_session, continuation_ids))
    if attempted_continuation_ids is None:
        attempted_continuation_ids = set()

    sections = [
        (
            segment.label,
            _build_section_rows(
                db_session,
                segment.songs,
                label=segment.label,
                catalog=catalog,
                track_cache=track_cache,
                songs_to_skip=songs_to_skip,
                mandatory_injected_songs=mandatory_injected_songs,
                feature_store=feature_store,
                rng=rng,
                continuation_records=continuation_records,
                continuation_displays=continuation_displays,
                attempted_continuation_ids=attempted_continuation_ids,
            ),
        )
        for segment in segments
    ]
    if encore:
        sections.append(
            (
                encore.label,
                _build_section_rows(
                    db_session,
                    encore.songs,
                    label=encore.label,
                    catalog=catalog,
                    track_cache=track_cache,
                    songs_to_skip=songs_to_skip,
                    mandatory_injected_songs=mandatory_injected_songs,
                    feature_store=feature_store,
                    rng=rng,
                    continuation_records=continuation_records,
                    continuation_displays=continuation_displays,
                    attempted_continuation_ids=attempted_continuation_ids,
                ),
            )
        )
    return sections


def _render_m3u(
    sections: Sequence[Tuple[str, List[SongDisplay]]], include_m3u: bool
) -> Optional[str]:
    """Serialize final section rows into an M3U playlist when requested."""
    if not include_m3u:
        return None

    lines = ["#EXTM3U"]
    emitted_segue_track_ids: Set[int] = set()
    for _section_label, section_tracks in sections:
        for track in section_tracks:
            if not track.mp3_url:
                continue
            if track.is_segue and track.track_id is not None:
                if track.track_id in emitted_segue_track_ids:
                    continue
                emitted_segue_track_ids.add(track.track_id)
            duration_sec = track.duration_seconds if track.duration_seconds is not None else -1
            show_date = track.show_date or "unknown date"
            segue_tag = " (rare segue)" if track.segue_type == "lottery_ticket" else ""
            lines.append(f"#EXTINF:{duration_sec},{track.title} [{show_date}]{segue_tag}")
            lines.append(track.mp3_url)
    return "\n".join(lines)


