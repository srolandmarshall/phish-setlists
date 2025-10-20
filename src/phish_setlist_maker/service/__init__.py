"""Service-layer helpers for exposing the generator via APIs."""

from .generation import (
    GenerationRequest,
    GenerationResult,
    HTMLArtifact,
    PlaylistArtifacts,
    PlaylistServiceError,
    SegmentDetails,
    SongDisplay,
    generate_show,
    resolve_era,
)

__all__ = [
    "GenerationRequest",
    "GenerationResult",
    "HTMLArtifact",
    "PlaylistArtifacts",
    "PlaylistServiceError",
    "SegmentDetails",
    "SongDisplay",
    "generate_show",
    "resolve_era",
]
