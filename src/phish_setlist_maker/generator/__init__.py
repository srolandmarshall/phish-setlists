"""Setlist generator public interface."""

from .core import GeneratedSetlist, SetSegment, SetlistGenerator
from .historical import (
    EncoreStatistics,
    SetLengthStatistics,
    encore_statistics,
    random_set_lengths,
    set_length_statistics,
)

__all__ = [
    "GeneratedSetlist",
    "SetSegment",
    "SetlistGenerator",
    "EncoreStatistics",
    "encore_statistics",
    "SetLengthStatistics",
    "set_length_statistics",
    "random_set_lengths",
]
