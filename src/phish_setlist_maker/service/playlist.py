"""Shared helpers for presenting playlist sections."""

from __future__ import annotations

from typing import List, Optional, Sequence, TYPE_CHECKING

from ..generator.html import PlaylistLink, PlaylistSection

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .generation import SegmentDetails


def _format_total(seconds: Optional[int]) -> Optional[str]:
    if seconds is None or seconds <= 0:
        return None
    minutes, secs = divmod(seconds, 60)
    return f"[{minutes}:{secs:02d}]"


def _format_title(base: str, seconds: Optional[int]) -> str:
    suffix = _format_total(seconds)
    return f"{base} {suffix}" if suffix else base


def build_playlist_sections(
    segments: Sequence["SegmentDetails"],
    encore: Optional["SegmentDetails"],
    *,
    include_audio_links: bool,
) -> List[PlaylistSection]:
    """Convert generated segments into HTML-friendly playlist sections."""

    sections: List[PlaylistSection] = []
    for segment in segments:
        links = [
            PlaylistLink(
                title=song.title,
                mp3_url=song.mp3_url if include_audio_links else None,
                duration=song.duration_label,
                origin=song.origin,
                track_id=song.track_id,
            )
            for song in segment.tracks
        ]
        sections.append(
            PlaylistSection(title=_format_title(segment.label, segment.duration_seconds), tracks=links)
        )

    if encore:
        encore_links = [
            PlaylistLink(
                title=song.title,
                mp3_url=song.mp3_url if include_audio_links else None,
                duration=song.duration_label,
                origin=song.origin,
                track_id=song.track_id,
            )
            for song in encore.tracks
        ]
        sections.append(
            PlaylistSection(title=_format_title(encore.label, encore.duration_seconds), tracks=encore_links)
        )

    return sections
