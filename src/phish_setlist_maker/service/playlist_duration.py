"""Duration estimates and compensation policy for injected segue tracks."""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from .catalog import SongCatalog, normalize_title

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
