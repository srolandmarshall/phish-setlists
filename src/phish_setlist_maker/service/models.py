"""Shared dataclasses for service layer helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    track_id: Optional[int] = None
    rare_segue_next_tracks: Optional[List[int]] = None  # PHASE 4.2: track_ids of rare segue continuations
    mandatory_next_tracks: Optional[List[int]] = None  # Track IDs for mandatory pattern continuations (or empty list for random)
    mandatory_pattern_songs: Optional[List[str]] = None  # Song titles for mandatory pattern (e.g., ["I Am Hydrogen", "Weekapaug Groove"])
    # Segue metadata for API response
    is_segue: bool = False
    segue_type: Optional[str] = None  # "rare" or "lottery_ticket"
    segue_pattern: Optional[str] = None
    segue_position: Optional[int] = None
    segue_group_id: Optional[str] = None
    historical_occurrences: Optional[int] = None
    rarity_score: Optional[float] = None
    likes_count: Optional[int] = None

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
    segue_notes: List[str] = field(default_factory=list)  # NEW: Notes about segues (mandatory, lottery tickets)


@dataclass(slots=True)
class GenerationResult:
    """Full output of the generator, including optional media artifacts."""

    seed: int
    generated_at: datetime
    generated: GeneratedSetlist
    segments: List[SegmentDetails]
    encore: Optional[SegmentDetails]
    playlist: Optional[PlaylistArtifacts]
