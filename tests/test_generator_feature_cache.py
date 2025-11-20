"""Tests for segment-level feature caching in the generator."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from random import Random
from typing import Dict, Iterable, List, Optional, Set

from phish_setlist_maker.analysis.feature_store import SongFeatures
from phish_setlist_maker.generator.core import SetlistGenerator
from phish_setlist_maker.generator.historical import SongFrequency


class _CountingFeatureStore:
    """Minimal feature store stub that records lookup counts."""

    def __init__(self) -> None:
        self.calls: Dict[str, int] = defaultdict(int)

    def _hit(self, name: str) -> None:
        self.calls[name] += 1

    def get_song_features(self, song_name: str) -> SongFeatures:
        self._hit("song_features")
        return SongFeatures(
            song_name=song_name,
            total_appearances=100,
            entropy=0.0,
            is_multi_home=False,
            set_probabilities={"set1": 0.5},
        )

    def get_mandatory_segues(self, song_title: str) -> List[dict]:
        self._hit("mandatory_segues")
        return []

    def get_placement_probability(self, song_title: str, set_label: str) -> float:
        self._hit("placement_probability")
        return 0.2

    def get_transition_lift(self, from_song: str, to_song: str):
        self._hit("transition_lift")
        return None

    def get_mandatory_next_songs(self, from_song: str) -> Set[str]:
        self._hit("mandatory_next_songs")
        return set()

    def violates_ordering_constraint(self, songs_so_far: List[str], candidate_song: str) -> bool:
        self._hit("ordering_constraint")
        return False

    def violates_cross_set_dependency(
        self,
        candidate_song: str,
        target_set: str,
        previous_sets_songs: Optional[Dict[str, List[str]]],
    ) -> bool:
        self._hit("cross_set_dependency")
        return False

    def is_forbidden_transition(self, from_song: str, to_song: str) -> bool:
        self._hit("forbidden_transition")
        return False

    def get_set_enders_for_set(self, canonical_set: str, min_probability: float = 0.0) -> list:
        return []


def test_feature_cache_limits_duplicate_lookups(db_session) -> None:
    """Segment caching should cap feature lookups to one per song."""

    # Deliberately disable built-in ML loading so we can inject the stub store.
    generator = SetlistGenerator(db_session, rng=Random(0), adjacency_bonus=0.0, use_ml_features=False)
    generator._feature_store = _CountingFeatureStore()
    generator._use_ml_features = True

    pool = [
        SongFrequency("Song Alpha", 10),
        SongFrequency("Song Beta", 8),
        SongFrequency("Song Gamma", 6),
    ]
    eligible: Iterable[str] = [freq.title for freq in pool]

    selection, duration_capped, _ = generator._select_with_duration_budget(
        base_songs=tuple(),
        desired_count=2,
        frequencies_by_set={"set1": pool},
        target_set="set1",
        segment_label="set1",
        used_songs=set(),
        eligible_songs=eligible,
        previous_song=None,
        adjacency_map=None,
        stats=None,
        duration_target=None,
        previous_sets_songs=None,
        max_segues_per_set=None,
    )

    assert len(selection) == 2
    assert duration_capped is False

    unique_titles = {freq.title for freq in pool}
    calls = generator._feature_store.calls  # type: ignore[assignment]
    assert calls["mandatory_segues"] <= len(unique_titles)
    assert calls["song_features"] <= len(unique_titles)
    assert calls["placement_probability"] <= len(unique_titles)


def test_weight_adjustments_use_single_pass_lookups(db_session) -> None:
    """Combined adjustment loop should only touch each feature once per song."""

    generator = SetlistGenerator(db_session, rng=Random(1), adjacency_bonus=0.0, use_ml_features=False)
    generator._feature_store = _CountingFeatureStore()
    generator._use_ml_features = True

    pool = [
        SongFrequency("Song Alpha", 10),
        SongFrequency("Song Beta", 8),
    ]
    feature_cache: Dict[str, Dict[str, Any]] = {}

    choice = generator._weighted_pick(
        pool=pool,
        used_songs=set(),
        previous_song="Prev Song",
        adjacency_map={"Prev Song": {"Song Alpha": 2, "Song Beta": 1}},
        target_set="set1",
        feature_cache=feature_cache,
    )

    assert choice in {"Song Alpha", "Song Beta"}

    calls = generator._feature_store.calls  # type: ignore[assignment]
    assert calls["song_features"] == len(pool)
    assert calls["mandatory_segues"] == len(pool)
    assert calls["placement_probability"] == len(pool)
    assert calls["transition_lift"] == len(pool)
    assert calls["mandatory_next_songs"] == 1
