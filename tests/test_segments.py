"""Tests for segment helper functions."""

from __future__ import annotations

from phish_setlist_maker.generator.core import SetSegment
from phish_setlist_maker.service.models import SongDisplay
from phish_setlist_maker.service.segments import expand_tracks, segment_duration_seconds


def test_expand_tracks_uses_lookup_and_creates_placeholders():
    lookup = {
        "maze": SongDisplay(title="Maze", mp3_url="https://example.com/maze.mp3", duration_seconds=480),
    }
    segment = SetSegment(label="Set 1", songs=["Maze -> Sample in a Jar"])

    expanded = expand_tracks(segment.songs, lookup)

    assert expanded[0].title == "Maze"
    assert expanded[0].mp3_url.endswith("maze.mp3")
    assert expanded[1].title == "Sample in a Jar"
    assert expanded[1].mp3_url is None


def test_segment_duration_seconds_sums_known_track_lengths():
    lookup = {
        "maze": SongDisplay(title="Maze", duration_seconds=480),
        "sampleinajar": SongDisplay(title="Sample in a Jar", duration_seconds=300),
    }
    segment = SetSegment(label="Set 1", songs=["Maze -> Sample in a Jar"])

    total = segment_duration_seconds(segment, lookup)

    assert total == 780
