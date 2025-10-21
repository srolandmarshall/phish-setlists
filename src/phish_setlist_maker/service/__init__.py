"""Service-layer helpers for exposing the generator via APIs."""

from .generation import GenerationRequest, generate_show, resolve_era
from .errors import PlaylistServiceError
from .models import GenerationResult, HTMLArtifact, PlaylistArtifacts, SegmentDetails, SongDisplay

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
