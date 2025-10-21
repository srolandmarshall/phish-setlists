"""Tests for service-layer dataclass helpers."""

from __future__ import annotations

from phish_setlist_maker.service.models import SongDisplay


def test_song_display_duration_label_formats_seconds():
    song = SongDisplay(title="Maze", duration_seconds=485)
    assert song.duration_label == "8:05"

    missing = SongDisplay(title="Silent", duration_seconds=None)
    assert missing.duration_label is None
