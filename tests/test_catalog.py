"""Tests for catalog normalization helpers."""

from __future__ import annotations

import pytest

from phish_setlist_maker.models import Song
from phish_setlist_maker.service.catalog import (
    SongCatalogEntry,
    build_song_catalog,
    determine_origin_from_entry,
    normalize_title,
    split_song_titles,
)


def test_normalize_title_strips_punctuation():
    assert normalize_title("Harry Hood!") == "harryhood"
    assert normalize_title("Mike's Song") == "mikessong"


def test_split_song_titles_handles_sequences():
    titles = list(split_song_titles("Mike's Song -> I Am Hydrogen > Weekapaug Groove"))
    assert titles == ["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"]


def test_build_song_catalog_registers_aliases(db_session):
    songs = [
        Song(
            title="Mike's Song",
            slug="mikes-song",
            tracks_count=0,
            original=True,
            alias="Mike's",
            artist="Phish",
        ),
        Song(
            title="2001",
            slug="also-sprach-zarathustra",
            tracks_count=0,
            original=False,
            alias="Also Sprach Zarathustra;2001 Theme",
            artist="Deodato",
        ),
    ]
    db_session.add_all(songs)
    db_session.commit()

    catalog = build_song_catalog(db_session)

    assert catalog.by_slug["mikes-song"].title == "Mike's Song"
    assert "also-sprach-zarathustra" not in catalog.by_title  # slug is separate
    assert catalog.by_title["mikessong"].slug == "mikes-song"
    assert catalog.by_title["2001"].slug == "also-sprach-zarathustra"
    assert catalog.by_title["alsosprachzarathustra"].slug == "also-sprach-zarathustra"


@pytest.mark.parametrize(
    "entry,expected",
    [
        (SongCatalogEntry(slug="slug", title="Original", original=True, artist="Phish", alias=None), "Phish original"),
        (
            SongCatalogEntry(slug="cover", title="Cover", original=False, artist="Jimi Hendrix", alias=None),
            "Originally by Jimi Hendrix",
        ),
        (
            SongCatalogEntry(slug="alias", title="Alias Song", original=False, artist=None, alias="Gamehendge"),
            "Alias: Gamehendge",
        ),
        (
            SongCatalogEntry(slug="unknown", title="Unknown", original=False, artist=None, alias=None),
            None,
        ),
    ],
)
def test_determine_origin_from_entry(entry, expected):
    assert determine_origin_from_entry(entry) == expected
