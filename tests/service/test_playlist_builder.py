from random import Random

from phish_setlist_maker.generator.core import SetSegment
from phish_setlist_maker.service.catalog import SongCatalog, SongCatalogEntry, normalize_title
from phish_setlist_maker.service.models import PlaylistArtifacts, SongDisplay
from phish_setlist_maker.service.playlist_builder import build_playlist_artifacts


class StubSession:
    """Minimal DB session stub used in builder tests."""

    def __getattr__(self, item):
        raise AssertionError(f"Unexpected DB access: {item}")


def _catalog_with(title: str) -> SongCatalog:
    normalized = normalize_title(title)
    entry = SongCatalogEntry(
        slug=normalized,
        title=title,
        original=True,
        artist=None,
        alias=None,
    )
    return SongCatalog(by_title={normalized: entry}, by_slug={normalized: entry})


def test_build_playlist_artifacts_uses_track_selector(mocker):
    catalog = _catalog_with("Song Foo")
    display = SongDisplay(title="Song Foo", mp3_url="http://example.com/foo.mp3", duration_seconds=300)
    selector = mocker.Mock(return_value=display)

    artifacts = build_playlist_artifacts(
        db_session=StubSession(),
        segments=[SetSegment(label="Set 1", songs=["Song Foo"])],
        encore=None,
        catalog=catalog,
        rng=Random(0),
        include_m3u=False,
        strict=False,
        feature_store=None,
        same_show_segues=False,
        generated_setlist=None,
        jamminess=None,
        set_lengths=None,
        max_segues_per_set=2,
        track_selector=selector,
    )

    assert isinstance(artifacts, PlaylistArtifacts)
    assert artifacts.sections == [("Set 1", [display])]
    selector.assert_called_once()


def test_build_playlist_artifacts_records_missing_titles():
    catalog = SongCatalog(by_title={}, by_slug={})

    artifacts = build_playlist_artifacts(
        db_session=StubSession(),
        segments=[SetSegment(label="Set 1", songs=["Unknown Jam"])],
        encore=None,
        catalog=catalog,
        rng=Random(0),
        include_m3u=False,
        strict=False,
        feature_store=None,
        same_show_segues=False,
        generated_setlist=None,
        jamminess=None,
        set_lengths=None,
        max_segues_per_set=2,
        track_selector=lambda *args, **kwargs: None,
    )

    assert artifacts.missing_tracks == ["Unknown Jam"]
    assert artifacts.sections[0][1][0].title == "Unknown Jam"


def test_build_playlist_artifacts_assembles_sections_before_rendering_m3u(mocker):
    catalog = _catalog_with("Song Foo")
    bar = SongCatalogEntry(
        slug="song bar",
        title="Song Bar",
        original=True,
        artist=None,
        alias=None,
    )
    catalog.by_title[normalize_title(bar.title)] = bar
    catalog.by_slug[bar.slug] = bar
    foo_display = SongDisplay(
        title="Song Foo",
        mp3_url="https://example.com/foo.mp3",
        duration_seconds=300,
        show_date="1995-06-16",
    )
    bar_display = SongDisplay(
        title="Song Bar",
        mp3_url="https://example.com/bar.mp3",
        duration_seconds=240,
        show_date="1997-11-17",
    )
    selector = mocker.Mock(side_effect=[foo_display, bar_display])

    artifacts = build_playlist_artifacts(
        db_session=StubSession(),
        segments=[SetSegment(label="Set 1", songs=["Song Foo"])],
        encore=SetSegment(label="Encore", songs=["Song Bar"]),
        catalog=catalog,
        rng=Random(0),
        include_m3u=True,
        strict=False,
        track_selector=selector,
    )

    assert artifacts.sections == [
        ("Set 1", [foo_display]),
        ("Encore", [bar_display]),
    ]
    assert artifacts.m3u_text == "\n".join(
        [
            "#EXTM3U",
            "#EXTINF:300,Song Foo [1995-06-16]",
            "https://example.com/foo.mp3",
            "#EXTINF:240,Song Bar [1997-11-17]",
            "https://example.com/bar.mp3",
        ]
    )
