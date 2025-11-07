"""Pydantic models for the setlist API."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class VenueModel(BaseModel):
    id: int
    name: str
    city: str
    state: str
    country: str
    slug: str
    shows_count: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    abbrev: Optional[str] = None


class SongModel(BaseModel):
    title: str
    mp3_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    origin: Optional[str] = None
    show_date: Optional[str] = None
    track_id: Optional[int] = None
    
    # Segue metadata (new in v0.2.1)
    is_segue: bool = Field(
        default=False,
        description="Whether this song is part of a segue group"
    )
    segue_type: Optional[Literal["mandatory", "rare", "lottery_ticket"]] = Field(
        default=None,
        description="Type of segue: mandatory (always appear together), rare (<50 occurrences), or lottery_ticket (rare with high likes)"
    )
    segue_pattern: Optional[str] = Field(
        default=None,
        description="Full segue pattern, e.g., 'Mike's Song -> I Am Hydrogen -> Weekapaug Groove'"
    )
    segue_position: Optional[int] = Field(
        default=None,
        description="Position in the segue sequence (1, 2, 3, etc.)"
    )
    segue_group_id: Optional[str] = Field(
        default=None,
        description="Unique ID grouping all songs in this segue together"
    )
    historical_occurrences: Optional[int] = Field(
        default=None,
        description="Number of times this segue has occurred historically"
    )
    rarity_score: Optional[float] = Field(
        default=None,
        description="Rarity score from 0.0-1.0 (lower = rarer). Only for rare/lottery segues"
    )
    likes_count: Optional[int] = Field(
        default=None,
        description="Number of likes from phish.net for this specific track"
    )


class SegmentModel(BaseModel):
    label: str
    songs: list[str]
    tracks: list[SongModel]
    duration_seconds: Optional[int] = None
    duration_label: Optional[str] = None


class MetadataModel(BaseModel):
    reference_date: date
    cutoff_date: date
    era: Optional[str]
    year: Optional[int]
    notes: list[str]


class PlaylistSectionModel(BaseModel):
    title: str
    tracks: list[SongModel]


class PlaylistModel(BaseModel):
    sections: list[PlaylistSectionModel]
    first_track_url: Optional[str] = None
    m3u_text: Optional[str] = None
    missing_tracks: list[str]


class GenerateResponse(BaseModel):
    seed: int
    generated_at: datetime
    metadata: MetadataModel
    sets: list[SegmentModel]
    encore: Optional[SegmentModel]
    playlist: Optional[PlaylistModel]


class GenerateRequestModel(BaseModel):
    reference_date: Optional[date] = None
    era: Optional[Literal["1.0", "2.0", "3.0", "4.0"]] = None
    year: Optional[int] = Field(default_factory=lambda: datetime.now(timezone.utc).year)
    num_sets: int = Field(default=2, ge=2, le=3)
    include_encore: bool = True
    set_lengths: Optional[Dict[str, int]] = None
    allow_previous_show: bool = True
    seed: Optional[int] = None
    include_playlist: bool = True
    use_ml_features: bool = Field(default=True, description="Enable ML-driven feature adjustments")
    ml_placement_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="Weight for ML placement probabilities (0-1)")
    ml_transition_bonus: float = Field(default=0.1, ge=0.0, le=1.0, description="Bonus for ML transition lift scores (0-1)")
    jamminess: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Jam intensity override (0=tight/concise, 0.5=balanced, 1.0=maximum jam). None=dynamic selection.")
    same_show_segues: bool = Field(
        default=False,
        description="Ensure songs in mandatory segues come from the same show performance. Also enables lottery ticket injection (5% chance) for rare historical segues."
    )

    @field_validator("set_lengths")
    @classmethod
    def _validate_set_lengths(cls, value: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]:
        if value is None:
            return None
        allowed = {"set1", "set2", "set3", "encore"}
        normalized: Dict[str, int] = {}
        for key, count in value.items():
            lower = key.lower()
            if lower not in allowed:
                raise ValueError(
                    f"Unsupported set label '{key}'. Allowed labels: {', '.join(sorted(allowed))}."
                )
            normalized[lower] = int(count)
        return normalized


__all__ = [
    "GenerateRequestModel",
    "GenerateResponse",
    "HealthResponse",
    "MetadataModel",
    "PlaylistModel",
    "PlaylistSectionModel",
    "SegmentModel",
    "SongModel",
    "VenueModel",
]
