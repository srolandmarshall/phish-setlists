"""Helpers for expanding generated segments with track metadata."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ..generator.core import SetSegment
from .catalog import normalize_title, split_song_titles
from .models import SongDisplay


def expand_tracks(raw_songs: Sequence[str], track_lookup: Dict[str, SongDisplay]) -> List[SongDisplay]:
    expanded: List[SongDisplay] = []
    for raw_song in raw_songs:
        for title in split_song_titles(raw_song):
            key = normalize_title(title)
            track = track_lookup.get(key)
            if track:
                expanded.append(track)
            else:
                expanded.append(SongDisplay(title=title))
    return expanded


def segment_duration_seconds(segment: SetSegment, track_lookup: Dict[str, SongDisplay]) -> Optional[int]:
    total = 0
    has_known = False
    for raw_song in segment.songs:
        for title in split_song_titles(raw_song):
            key = normalize_title(title)
            track = track_lookup.get(key)
            if track and track.duration_seconds:
                total += track.duration_seconds
                has_known = True
    return total if has_known else None
