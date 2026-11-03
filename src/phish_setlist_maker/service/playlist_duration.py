"""Duration estimates and compensation policy for injected segue tracks."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .catalog import SongCatalog, normalize_title
from .models import SongDisplay

logger = logging.getLogger("uvicorn.error")


def estimate_duration_compensation(
    current_duration: int, added_duration: int, target_duration: int
) -> float:
    """Return seconds to compensate while keeping a set above its 95% floor."""
    projected_total = current_duration + added_duration
    max_threshold = target_duration * 1.15
    min_threshold = target_duration * 0.95
    if projected_total <= max_threshold:
        return 0
    return max(0.0, min(projected_total - max_threshold, projected_total - min_threshold))


def calculate_songs_to_skip(
    segment_label: str,
    current_segment_songs: List[str],
    current_song_title: str,
    duration_to_compensate: int,
    *,
    catalog: SongCatalog,
    song_duration_stats: Dict[str, object],
) -> List[Tuple[str, str]]:
    """Choose the least-liked songs whose average duration covers the overage."""
    song_stats = []
    for song_title in current_segment_songs:
        if song_title == current_song_title:
            continue

        entry = catalog.by_title.get(normalize_title(song_title))
        if not entry:
            continue

        stats = song_duration_stats.get(entry.slug)
        if stats and stats.avg_duration:
            avg_duration = stats.avg_duration
            if avg_duration > 6000:
                avg_duration /= 1000
            song_stats.append(
                {
                    "title": song_title,
                    "avg_duration": int(avg_duration),
                    "avg_likes": int(stats.avg_likes or 0),
                }
            )

    if not song_stats:
        return []

    song_stats.sort(key=lambda item: item["avg_likes"])
    to_skip: List[Tuple[str, str]] = []
    compensated_duration = 0
    for stat in song_stats:
        if compensated_duration >= duration_to_compensate:
            break
        to_skip.append((segment_label, stat["title"]))
        compensated_duration += stat["avg_duration"]
        logger.info(
            "  Marking %s/%s for removal (likes: %d, duration: %ds, total compensated: %ds/%ds)",
            segment_label,
            stat["title"],
            stat["avg_likes"],
            stat["avg_duration"],
            compensated_duration,
            duration_to_compensate,
        )
    return to_skip


def compensate_for_continuations(
    segment_label: Optional[str],
    current_segment_songs: Optional[List[str]],
    current_song_title: str,
    display: Optional[SongDisplay],
    set_lengths: Optional[Dict[str, int]],
    *,
    catalog: SongCatalog,
    song_duration_stats: Dict[str, object],
    continuation_records: Dict[int, object],
) -> List[Tuple[str, str]]:
    """Select songs to remove when injected continuations overfill a segment."""
    if not display or not segment_label or not current_segment_songs or not set_lengths:
        return []
    target_duration = set_lengths.get(segment_label)
    if not target_duration:
        return []

    added_duration = 0
    if display.rare_segue_next_tracks:
        for track_id in display.rare_segue_next_tracks:
            metadata = continuation_records.get(track_id)
            if metadata and metadata.duration:
                duration = metadata.duration
                added_duration += duration // 1000 if duration > 6000 else duration
        logger.info(
            "🎰 Lottery ticket triggered for %s with %d continuation tracks (total duration: %ds)",
            current_song_title,
            len(display.rare_segue_next_tracks),
            added_duration,
        )

    if display.mandatory_pattern_songs:
        if display.mandatory_next_tracks:
            for track_id in display.mandatory_next_tracks:
                metadata = continuation_records.get(track_id)
                if metadata and metadata.duration:
                    duration = metadata.duration
                    added_duration += duration // 1000 if duration > 6000 else duration
        else:
            added_duration += len(display.mandatory_pattern_songs) * 420
        logger.info(
            "🔗 Mandatory pattern triggered for %s with %d continuation songs (estimated duration: %ds)",
            current_song_title,
            len(display.mandatory_pattern_songs),
            added_duration,
        )

    if added_duration <= 0:
        return []

    current_duration = 0
    for title in current_segment_songs:
        entry = catalog.by_title.get(normalize_title(title))
        stats = song_duration_stats.get(entry.slug) if entry else None
        avg_duration = stats.avg_duration if stats else None
        if avg_duration:
            avg_duration = avg_duration / 1000 if avg_duration > 6000 else avg_duration
            current_duration += int(avg_duration)

    projected_total = current_duration + added_duration
    max_threshold = target_duration * 1.15
    overage = estimate_duration_compensation(current_duration, added_duration, target_duration)
    if overage <= 0:
        logger.info(
            "📊 Set %s: projected=%ds, target=%ds, max_threshold=%ds (15%% over) - no compensation needed",
            segment_label,
            projected_total,
            target_duration,
            int(max_threshold),
        )
        return []

    logger.info(
        "📊 Set %s: projected=%ds, target=%ds, max_threshold=%ds (15%% over), overage=%ds - will compensate",
        segment_label,
        projected_total,
        target_duration,
        int(max_threshold),
        int(overage),
    )
    skipped = calculate_songs_to_skip(
        segment_label,
        current_segment_songs,
        current_song_title,
        overage,
        catalog=catalog,
        song_duration_stats=song_duration_stats,
    )
    if skipped:
        logger.info(
            "  Will skip %d songs to compensate for overage (%ds): %s",
            len(skipped),
            int(overage),
            ", ".join(f"{label}/{title}" for label, title in skipped),
        )
    return skipped
