"""Tests for shared playlist section formatting."""

from __future__ import annotations

import pytest

from phish_setlist_maker.generator.html import PlaylistLink, PlaylistSection
from phish_setlist_maker.service import SegmentDetails, SongDisplay


def _segment(label: str, title: str, *, duration: int | None, mp3: str | None) -> SegmentDetails:
    song = SongDisplay(
        title=title,
        mp3_url=mp3,
        duration_seconds=duration,
        origin="Phish original",
    )
    duration_seconds = duration if duration is not None else None
    return SegmentDetails(
        label=label,
        songs=[title],
        tracks=[song],
        duration_seconds=duration_seconds,
    )


def test_build_playlist_sections_includes_durations_and_audio_links():
    from phish_setlist_maker.service.playlist import build_playlist_sections

    segments = [
        _segment("Set 1", "Maze", duration=480, mp3="https://example.com/maze.mp3"),
    ]
    encore = _segment("Encore", "Tweezer Reprise", duration=300, mp3="https://example.com/reprise.mp3")

    sections = build_playlist_sections(
        segments,
        encore,
        include_audio_links=True,
    )

    assert isinstance(sections[0], PlaylistSection)
    assert sections[0].title == "Set 1 [8:00]"
    assert sections[0].tracks == [
        PlaylistLink(
            title="Maze",
            mp3_url="https://example.com/maze.mp3",
            duration="8:00",
            origin="Phish original",
        )
    ]

    assert sections[-1].title == "Encore [5:00]"
    assert sections[-1].tracks[0].mp3_url == "https://example.com/reprise.mp3"


def test_build_playlist_sections_strips_audio_links_when_disabled():
    from phish_setlist_maker.service.playlist import build_playlist_sections

    segments = [
        _segment("Set 1", "Maze", duration=480, mp3="https://example.com/maze.mp3"),
    ]

    sections = build_playlist_sections(
        segments,
        None,
        include_audio_links=False,
    )

    assert sections[0].title == "Set 1 [8:00]"
    link = sections[0].tracks[0]
    assert link.mp3_url is None
    assert link.duration == "8:00"
