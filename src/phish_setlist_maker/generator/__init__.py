"""Setlist generator public interface."""

from .core import GeneratedSetlist, SetSegment, SetlistGenerator
from .historical import (
    EncoreStatistics,
    SegmentPattern,
    SegmentStatistics,
    SetLengthStatistics,
    encore_statistics,
    random_set_lengths,
    segment_statistics,
    set_length_statistics,
)

__all__ = [
    "GeneratedSetlist",
    "SetSegment",
    "SetlistGenerator",
    "EncoreStatistics",
    "SegmentStatistics",
    "SegmentPattern",
    "segment_statistics",
    "encore_statistics",
    "SetLengthStatistics",
    "set_length_statistics",
    "random_set_lengths",
]
