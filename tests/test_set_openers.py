from random import Random

import pandas as pd

from phish_setlist_maker.analysis.database import build_set_opening_frequencies
from phish_setlist_maker.analysis.feature_store import FeatureStore, SetOpeningFrequency
from phish_setlist_maker.generator.core import GeneratedSetlist, GenerationMetadata, SetSegment
from phish_setlist_maker.generator.openers import apply_historical_set_openers


def test_build_set_opening_frequencies_counts_set_first_songs_by_era():
    tracks = pd.DataFrame(
        [
            (1, "set1", 1, "A", "1.0"),
            (1, "set1", 2, "B", "1.0"),
            (2, "set1", 1, "B", "1.0"),
            (2, "set1", 2, "A", "1.0"),
            (3, "set1", 1, "B", "2.0"),
            (3, "set1", 2, "A", "2.0"),
            (1, "set2", 1, "C", "1.0"),
        ],
        columns=["show_id", "canonical_set", "position", "song_effective_title", "era"],
    )

    frequencies = build_set_opening_frequencies(tracks, allowed_sets=["set1", "set2"])

    a_early = frequencies.query(
        "song_effective_title == 'A' and canonical_set == 'set1' and era == '1.0'"
    ).iloc[0]
    b_all = frequencies.query(
        "song_effective_title == 'B' and canonical_set == 'set1' and era == 'all'"
    ).iloc[0]
    c_all = frequencies.query(
        "song_effective_title == 'C' and canonical_set == 'set2' and era == 'all'"
    ).iloc[0]

    assert (a_early.opening_count, a_early.total_count) == (1, 2)
    assert a_early.opening_probability == 0.5
    assert (b_all.opening_count, b_all.total_count) == (2, 3)
    assert c_all.opening_probability == 1.0


def test_set_openers_fall_back_to_all_eras_when_era_history_is_sparse(tmp_path):
    store = FeatureStore(tmp_path)
    era_rows = [
        SetOpeningFrequency("A", "set1", "1.0", 2, 10, 0.2),
    ]
    all_era = SetOpeningFrequency("B", "set1", "all", 25, 50, 0.5)
    store._set_opening_frequencies = {
        (row.song_name, row.set_label, row.era): row for row in [*era_rows, all_era]
    }

    assert store.get_set_openers_for_set("set1", era="1.0") == [all_era]
    assert store.get_set_openers_for_set("set1", era=None) == [all_era]


def test_feature_store_loads_precomputed_set_openers(tmp_path, monkeypatch):
    path = tmp_path / "set_opening_frequencies.parquet"
    path.touch()
    monkeypatch.setattr(
        pd,
        "read_parquet",
        lambda _: pd.DataFrame(
            [
                {
                    "song_effective_title": "A",
                    "canonical_set": "set1",
                    "era": "1.0",
                    "opening_count": 20,
                    "total_count": 30,
                    "opening_probability": 2 / 3,
                }
            ]
        ),
    )
    store = FeatureStore(tmp_path)

    store._load_set_opening_frequencies()

    assert store.get_set_openers_for_set("set1", era="1.0")[0] == SetOpeningFrequency(
        "A", "set1", "1.0", 20, 30, 2 / 3
    )


def test_apply_historical_openers_only_reorders_existing_set_songs():
    class FakeFeatureStore:
        def get_set_openers_for_set(self, set_label, *, era=None):
            if era == "1.0":
                return [SetOpeningFrequency("B", set_label, era, 20, 30, 2 / 3)]
            return [SetOpeningFrequency("C", set_label, "all", 40, 60, 2 / 3)]

    generated = GeneratedSetlist(
        sets=[SetSegment("Set 1", ["A", "B", "C"])],
        encore=None,
        metadata=GenerationMetadata(
            reference_date=pd.Timestamp("2020-01-01").date(),
            cutoff_date=pd.Timestamp("2020-01-01").date(),
            era="1.0",
            year=2020,
        ),
    )

    apply_historical_set_openers(generated, FakeFeatureStore(), era="1.0", rng=Random(7))

    assert generated.sets[0].songs == ["B", "A", "C"]
    assert generated.metadata.notes[0].startswith("Selected B as Set 1 opener")


def test_apply_historical_openers_uses_all_era_fallback_when_candidates_do_not_match():
    class FakeFeatureStore:
        calls = []

        def get_set_openers_for_set(self, set_label, *, era=None):
            self.calls.append(era)
            if era == "1.0":
                return [SetOpeningFrequency("Outside candidates", set_label, era, 20, 30, 2 / 3)]
            return [SetOpeningFrequency("B", set_label, "all", 20, 30, 2 / 3)]

    store = FakeFeatureStore()
    generated = GeneratedSetlist(
        sets=[SetSegment("Set 1", ["A", "B", "C"])],
        encore=None,
        metadata=GenerationMetadata(
            reference_date=pd.Timestamp("2020-01-01").date(),
            cutoff_date=pd.Timestamp("2020-01-01").date(),
            era="1.0",
            year=2020,
        ),
    )

    apply_historical_set_openers(generated, store, era="1.0", rng=Random(2))

    assert store.calls == ["1.0", None]
    assert generated.sets[0].songs == ["B", "A", "C"]


def test_apply_historical_openers_skips_reorder_that_breaks_mandatory_segue():
    class FakeFeatureStore:
        def get_set_openers_for_set(self, set_label, *, era=None):
            return [SetOpeningFrequency("B", set_label, "all", 20, 30, 2 / 3)]

        def get_mandatory_next_songs(self, song):
            return {"C"} if song == "B" else set()

        def get_songs_that_must_follow(self, song):
            return set()

        def is_forbidden_transition(self, first, second):
            return False

    generated = GeneratedSetlist(
        sets=[SetSegment("Set 1", ["A", "B", "C", "D"])],
        encore=None,
        metadata=GenerationMetadata(
            reference_date=pd.Timestamp("2020-01-01").date(),
            cutoff_date=pd.Timestamp("2020-01-01").date(),
            era="1.0",
            year=2020,
        ),
    )

    apply_historical_set_openers(generated, FakeFeatureStore(), era="1.0", rng=Random(7))

    assert generated.sets[0].songs == ["A", "B", "C", "D"]
