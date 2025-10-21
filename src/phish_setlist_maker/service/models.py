"""Shared dataclasses for service layer helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from ..generator import GeneratedSetlist


@dataclass(frozen=True)
class SongDisplay:
    """Presentation-friendly metadata for a single song appearance."""

    title: str
    mp3_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    origin: Optional[str] = None
    show_date: Optional[str] = None

    @property
    def duration_label(self) -> Optional[str]:
        if self.duration_seconds is None or self.duration_seconds < 0:
            return None
        minutes, seconds = divmod(self.duration_seconds, 60)
        return f"{minutes}:{seconds:02d}"


@dataclass(slots=True)
class SegmentDetails:
    """Expanded view of a generated segment (raw titles + flattened songs)."""

    label: str
    songs: List[str]
    tracks: List[SongDisplay]
    duration_seconds: Optional[int] = None


@dataclass(slots=True)
class PlaylistArtifacts:
    """In-memory representation of playlist data and track metadata."""

    sections: List[Tuple[str, List[SongDisplay]]]
    first_track_url: Optional[str]
    m3u_text: Optional[str]
    missing_tracks: List[str]


@dataclass(slots=True)
class HTMLArtifact:
    """Rendered HTML markup plus reference to the stylesheet."""

    markup: str
    stylesheet: str = "phish-setlist.css"


@dataclass(slots=True)
class GenerationResult:
    """Full output of the generator, including optional media artifacts."""

    seed: int
    generated_at: datetime
    generated: GeneratedSetlist
    segments: List[SegmentDetails]
    encore: Optional[SegmentDetails]
    playlist: Optional[PlaylistArtifacts]
    html: Optional[HTMLArtifact]
