from random import Random
from types import SimpleNamespace

from phish_setlist_maker.service.catalog import SongCatalog, SongCatalogEntry, normalize_title
from phish_setlist_maker.service.models import SongDisplay
from phish_setlist_maker.service.playlist_segue_injection import SegueInjection


class SessionStub:
    def __init__(self, metadata):
        self.metadata = metadata
        self.query_count = 0

    def execute(self, _statement):
        self.query_count += 1
        return SimpleNamespace(all=lambda: [self.metadata])


def _metadata():
    return SimpleNamespace(
        track_id=77,
        track_slug="common-song",
        duration=300,
        likes_count=5,
        metadata_cache=None,
        song_id=8,
        song_title="Common Song",
        song_slug="common-song",
    )


def _catalog():
    title = "Common Song"
    normalized = normalize_title(title)
    entry = SongCatalogEntry(
        slug="common-song",
        title=title,
        original=True,
        artist=None,
        alias=None,
    )
    return SongCatalog(by_title={normalized: entry}, by_slug={entry.slug: entry})


def test_rare_continuation_resolves_once_and_keeps_playlist_wide_dedupe(mocker):
    session = SessionStub(_metadata())
    injection = SegueInjection(session, _catalog(), Random(0), feature_store=object())
    resolve = mocker.patch(
        "phish_setlist_maker.service.playlist_segue_injection.resolve_track_metadata",
        return_value=("https://example.com/common.mp3", 300, "1998-07-17"),
    )
    first = SongDisplay(
        title="Song Foo",
        track_id=1,
        rare_segue_next_tracks=[77],
        segue_pattern="Song Foo -> Common Song",
        segue_group_id="first-group",
    )
    second = SongDisplay(
        title="Song Bar",
        track_id=2,
        rare_segue_next_tracks=[77],
        segue_pattern="Song Bar -> Common Song",
        segue_group_id="second-group",
    )

    injection.inject_rare(first)
    injection.inject_rare(second)

    assert resolve.call_count == 1
    assert session.query_count == 1
    continuation = injection.track_cache[normalize_title("Common Song")]
    assert continuation.track_id == 77
    assert continuation.segue_pattern == "Song Foo -> Common Song"
    assert len(injection.notes) == 1


def test_mandatory_continuation_uses_same_batched_metadata_boundary(mocker):
    session = SessionStub(_metadata())
    injection = SegueInjection(session, _catalog(), Random(0), feature_store=None)
    mocker.patch(
        "phish_setlist_maker.service.playlist_segue_injection.resolve_track_metadata",
        return_value=("https://example.com/common.mp3", 300, "1998-07-17"),
    )
    source = SongDisplay(
        title="Song Foo",
        mandatory_pattern_songs=["Common Song"],
        mandatory_next_tracks=[77],
    )

    injection.inject_mandatory(source, "Song Foo", "Set 1")

    continuation = injection.track_cache[normalize_title("Common Song")]
    assert continuation.track_id == 77
    assert continuation.segue_type == "mandatory"
    assert injection.mandatory_injected_songs == {("Set 1", "Common Song")}
