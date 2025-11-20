"""Helpers for caching per-segment feature lookups."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from .historical import SongFrequency
from ..analysis.feature_store import FeatureStore


class FeatureCache:
    """Lightweight cache for per-song feature bundles scoped to a segment."""

    def __init__(
        self,
        feature_store: Optional[FeatureStore],
        use_ml_features: bool,
        target_set: Optional[str],
    ) -> None:
        self._feature_store = feature_store
        self._enabled = bool(use_ml_features and feature_store)
        self._target_set = target_set
        self._cache: Dict[str, Dict[str, Any]] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def warm(self, pool: Iterable[SongFrequency]) -> None:
        """Pre-compute bundles for the provided pool."""
        if not self._enabled:
            return
        for freq in pool:
            self.get(freq.title)

    def get(self, song_title: str) -> Dict[str, Any]:
        """Return a feature bundle for the song, caching if needed."""
        if not self._enabled:
            return {"features": None, "mandatory_segues": [], "placement_prob": 0.0}

        if song_title in self._cache:
            return self._cache[song_title]

        features = self._feature_store.get_song_features(song_title)  # type: ignore[union-attr]
        mandatory_segues = self._feature_store.get_mandatory_segues(song_title) or []  # type: ignore[union-attr]
        placement_prob = (
            self._feature_store.get_placement_probability(song_title, self._target_set)  # type: ignore[union-attr]
            if self._target_set
            else 0.0
        )

        bundle = {
            "features": features,
            "mandatory_segues": mandatory_segues,
            "placement_prob": placement_prob,
        }
        self._cache[song_title] = bundle
        return bundle

    def __len__(self) -> int:
        return len(self._cache)
