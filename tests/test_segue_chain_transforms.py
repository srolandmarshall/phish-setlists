"""Unit tests for the pure segue-chain transformations and data boundary."""

from types import SimpleNamespace

from phish_setlist_maker.analysis.segue_chains import (
    adjacent_pairs_from_rows,
    complete_chains_from_rows,
    extract_subchains,
)
from phish_setlist_maker.analysis.segue_data import load_ordered_track_rows


def _track(track_id, show_id, set_label, position, song, duration=None, likes=None):
    return SimpleNamespace(
        track_id=track_id,
        show_id=show_id,
        set_label=set_label,
        position=position,
        song=song,
        show_date="2024-07-15",
        duration=duration,
        likes_count=likes,
    )


def test_complete_chains_break_on_gaps_and_show_or_set_changes():
    rows = [
        _track(1, 10, "set1", 1, "Tweezer >", 100, 2),
        _track(2, 10, "set1", 2, "Caspian", 200, 3),
        _track(3, 10, "set1", 4, "Gap", None, None),
        _track(4, 10, "set2", 1, "Other Set", 300, 4),
        _track(5, 11, "set2", 1, "Other Show", 400, 5),
        _track(6, 11, "set2", 2, "Final", 500, 6),
    ]

    chains = complete_chains_from_rows(rows)

    assert [chain["tracks"] for chain in chains] == [[1, 2], [5, 6]]
    assert chains[0]["songs"] == ["Tweezer >", "Caspian"]
    assert chains[0]["durations"] == [100, 200]
    assert chains[0]["likes"] == [2, 3]


def test_subchains_keep_like_and_segue_notation_filters():
    chain = {
        "show_id": 1,
        "show_date": "2024-07-15",
        "set_label": "set2",
        "tracks": [1, 2, 3],
        "songs": ["Tweezer >", "Prince Caspian", "Reba >"],
        "durations": [100, 200, 300],
        "likes": [2, 3, 4],
    }

    subchains = extract_subchains([chain], max_length=2, min_total_likes=5)

    assert [subchain["tracks"] for subchain in subchains] == [[1, 2], [2, 3]]


def test_ordered_track_loader_preserves_the_query_order_clause():
    rows = [_track(1, 1, "set1", 1, "Song")]

    class SessionStub:
        statement = None

        def execute(self, statement):
            self.statement = str(statement)
            return self

        def fetchall(self):
            return rows

    session = SessionStub()

    assert load_ordered_track_rows(session) == rows
    assert 'ORDER BY t.show_id, t."set", t.position' in session.statement


def test_adjacent_pair_normalization_keeps_order_and_zero_fallbacks():
    rows = [
        SimpleNamespace(
            show_id=1,
            show_date="2024-07-15",
            set_label="set2",
            track1_id=1,
            track2_id=2,
            song1="Tweezer >",
            song2="Prince Caspian",
            duration1=None,
            duration2=300,
            likes1=None,
            likes2=5,
        )
    ]

    assert adjacent_pairs_from_rows(rows) == [
        {
            "show_id": 1,
            "show_date": "2024-07-15",
            "set_label": "set2",
            "track1_id": 1,
            "track2_id": 2,
            "song1": "Tweezer >",
            "song2": "Prince Caspian",
            "duration1": 0,
            "duration2": 300,
            "likes1": 0,
            "likes2": 5,
        }
    ]
