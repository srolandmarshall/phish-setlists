from random import Random
from types import SimpleNamespace

from phish_setlist_maker.generator.core import SetSegment
from phish_setlist_maker.service.catalog import SongCatalog, SongCatalogEntry, normalize_title
from phish_setlist_maker.service.models import PlaylistArtifacts, SongDisplay
from phish_setlist_maker.service.playlist_builder import build_playlist_artifacts
from phish_setlist_maker.service.playlist_builder import _build_sections
from phish_setlist_maker.service.playlist_duration import (
    calculate_songs_to_skip,
    estimate_duration_compensation,
)
from phish_setlist_maker.service.playlist_queries import _load_song_duration_stats


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


def test_build_sections_deduplicates_within_each_section(mocker):
    catalog = _catalog_with("Song Foo")
    for title in ("Song Bar", "Common Song"):
        entry = SongCatalogEntry(
            slug=normalize_title(title),
            title=title,
            original=True,
            artist=None,
            alias=None,
        )
        catalog.by_title[normalize_title(title)] = entry
        catalog.by_slug[entry.slug] = entry

    first = SongDisplay(title="Song Foo", track_id=1, rare_segue_next_tracks=[77])
    second = SongDisplay(title="Song Bar", track_id=2, rare_segue_next_tracks=[77])
    track_row = SimpleNamespace(
        track_id=77,
        track_slug="common-song",
        duration=300,
        likes_count=5,
        metadata_cache=None,
        song_id=123,
        song_title="Common Song",
        song_slug="common-song",
    )

    class SessionStub:
        def execute(self, _statement):
            return SimpleNamespace(all=lambda: [track_row])

    resolve_metadata = mocker.patch(
        "phish_setlist_maker.service.playlist_sections.resolve_track_metadata",
        return_value=("https://example.com/common.mp3", 300, "1998-07-17"),
    )

    sections = _build_sections(
        SessionStub(),
        [
            SetSegment(label="Set 1", songs=["Song Foo", "Song Foo"]),
            SetSegment(label="Set 2", songs=["Song Bar"]),
        ],
        None,
        catalog=catalog,
        track_cache={
            normalize_title("Song Foo"): first,
            normalize_title("Song Bar"): second,
        },
        songs_to_skip=set(),
        mandatory_injected_songs=set(),
        feature_store=object(),
        rng=Random(0),
    )

    assert [row.track_id for _, rows in sections for row in rows] == [1, 77, 1, 2, 77]
    assert resolve_metadata.call_count == 1


def test_build_sections_batches_continuation_metadata_for_playlist(mocker):
    source_displays = [
        SongDisplay(title=f"Song {index}", track_id=index, rare_segue_next_tracks=[100 + index])
        for index in range(20)
    ]
    rows = [
        SimpleNamespace(
            track_id=100 + index,
            track_slug=f"continuation-{index}",
            duration=300,
            likes_count=5,
            metadata_cache=None,
            song_id=1000 + index,
            song_title=f"Continuation {index}",
            song_slug=f"continuation-{index}",
        )
        for index in range(20)
    ]

    class CountingSession:
        query_count = 0

        def execute(self, _statement):
            self.query_count += 1
            return SimpleNamespace(all=lambda: rows)

    session = CountingSession()
    mocker.patch(
        "phish_setlist_maker.service.playlist_sections.resolve_track_metadata",
        side_effect=lambda _session, candidate, **_kwargs: (
            f"https://example.com/{candidate.track_id}.mp3",
            candidate.duration,
            "1998-07-17",
        ),
    )

    sections = _build_sections(
        session,
        [SetSegment(label="Set 1", songs=[display.title for display in source_displays])],
        None,
        catalog=SongCatalog(by_title={}, by_slug={}),
        track_cache={normalize_title(display.title): display for display in source_displays},
        songs_to_skip=set(),
        mandatory_injected_songs=set(),
        feature_store=object(),
        rng=Random(0),
    )

    assert session.query_count == 1
    assert [row.track_id for row in sections[0][1]] == [
        track_id
        for index in range(20)
        for track_id in (index, 100 + index)
    ]


def test_duration_compensation_respects_target_band():
    assert estimate_duration_compensation(900, 300, 1000) == 50
    assert estimate_duration_compensation(800, 200, 1000) == 0


def test_duration_compensation_skips_lowest_liked_songs_first():
    catalog = _catalog_with("Song A")
    for title in ("Song B", "Trigger"):
        entry = SongCatalogEntry(
            slug=normalize_title(title),
            title=title,
            original=True,
            artist=None,
            alias=None,
        )
        catalog.by_title[normalize_title(title)] = entry
    stats = {
        "songa": SimpleNamespace(avg_duration=300, avg_likes=5),
        "songb": SimpleNamespace(avg_duration=300, avg_likes=10),
        "trigger": SimpleNamespace(avg_duration=300, avg_likes=0),
    }

    skipped = calculate_songs_to_skip(
        "Set 1",
        ["Song A", "Song B", "Trigger"],
        "Trigger",
        400,
        catalog=catalog,
        song_duration_stats=stats,
    )

    assert skipped == [("Set 1", "Song A"), ("Set 1", "Song B")]


def test_song_duration_stats_load_in_one_query_for_all_requested_songs():
    requested_slugs = [f"song-{index}" for index in range(20)]
    rows = [SimpleNamespace(song_slug=slug) for slug in requested_slugs]

    class CountingSession:
        query_count = 0

        def execute(self, _statement):
            self.query_count += 1
            return SimpleNamespace(all=lambda: rows)

    session = CountingSession()
    stats = _load_song_duration_stats(session, [*requested_slugs, requested_slugs[0]])

    assert session.query_count == 1
    assert set(stats) == set(requested_slugs)
