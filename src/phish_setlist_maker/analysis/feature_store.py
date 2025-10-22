"""Feature store for loading and caching ML-derived features.

Provides fast access to Phase 1 feature tables:
- Song placement probabilities (entropy, set distributions)
- Transition lift scores (song pair affinities)
- Multi-home classifications
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

import pandas as pd


@dataclass
class SongFeatures:
    """Aggregated features for a single song."""

    song_name: str
    total_appearances: int
    entropy: float
    is_multi_home: bool
    set_probabilities: Dict[str, float]  # set_label -> probability


@dataclass
class TransitionFeature:
    """Transition lift score between two songs."""

    from_song: str
    to_song: str
    set_label: str
    lift: float
    count: int


class FeatureStore:
    """In-memory cache of ML features for fast lookup."""

    def __init__(self, features_dir: Path):
        self.features_dir = features_dir
        self._song_features: Optional[Dict[str, SongFeatures]] = None
        self._transition_lifts: Optional[Dict[Tuple[str, str], TransitionFeature]] = None
        self._multi_home_songs: Optional[Set[str]] = None

    def load(self) -> None:
        """Load all feature tables into memory."""
        self._load_song_features()
        self._load_transition_lifts()
        self._load_multi_home_songs()

    def _load_song_features(self) -> None:
        """Load song-level features from parquet."""
        df = pd.read_parquet(self.features_dir / "song_features.parquet")
        multi_home_df = pd.read_parquet(self.features_dir / "multi_home_songs.parquet")
        multi_home_set = set(multi_home_df["song_effective_title"].tolist())
        
        self._song_features = {}
        for _, row in df.iterrows():
            song_name = row["song_effective_title"]
            
            # Build set probabilities from columns
            set_probs = {}
            for set_label in ["set1", "set2", "set3", "encore"]:
                if set_label in df.columns:
                    set_probs[set_label] = float(row[set_label])
            
            self._song_features[song_name] = SongFeatures(
                song_name=song_name,
                total_appearances=int(row.get("total_appearances", 0)),
                entropy=float(row.get("set_entropy", 0.0)),
                is_multi_home=(song_name in multi_home_set),
                set_probabilities=set_probs,
            )

    def _load_transition_lifts(self) -> None:
        """Load transition lift scores from parquet."""
        df = pd.read_parquet(self.features_dir / "transition_lift.parquet")
        
        self._transition_lifts = {}
        for _, row in df.iterrows():
            from_song = row["from_title"]
            to_song = row["to_title"]
            key = (from_song, to_song)
            
            self._transition_lifts[key] = TransitionFeature(
                from_song=from_song,
                to_song=to_song,
                set_label=row["canonical_set"],
                lift=float(row["lift"]),
                count=int(row["count"]),
            )

    def _load_multi_home_songs(self) -> None:
        """Load multi-home song classifications."""
        df = pd.read_parquet(self.features_dir / "multi_home_songs.parquet")
        self._multi_home_songs = set(df["song_effective_title"].tolist())

    def get_song_features(self, song_name: str) -> Optional[SongFeatures]:
        """Retrieve features for a specific song."""
        if self._song_features is None:
            raise RuntimeError("FeatureStore not loaded. Call load() first.")
        return self._song_features.get(song_name)

    def get_transition_lift(
        self, from_song: str, to_song: str
    ) -> Optional[TransitionFeature]:
        """Retrieve lift score for a song pair."""
        if self._transition_lifts is None:
            raise RuntimeError("FeatureStore not loaded. Call load() first.")
        return self._transition_lifts.get((from_song, to_song))

    def is_multi_home(self, song_name: str) -> bool:
        """Check if song is classified as multi-home."""
        if self._multi_home_songs is None:
            raise RuntimeError("FeatureStore not loaded. Call load() first.")
        return song_name in self._multi_home_songs

    def get_placement_probability(self, song_name: str, set_label: str) -> float:
        """Get probability of song appearing in specific set."""
        features = self.get_song_features(song_name)
        if features is None:
            return 0.0
        return features.set_probabilities.get(set_label, 0.0)

    def get_high_lift_transitions(
        self, from_song: str, min_lift: float = 2.0
    ) -> list[TransitionFeature]:
        """Get all high-affinity transitions from a song."""
        if self._transition_lifts is None:
            raise RuntimeError("FeatureStore not loaded. Call load() first.")
        
        return [
            trans
            for (f, _), trans in self._transition_lifts.items()
            if f == from_song and trans.lift >= min_lift
        ]

    @property
    def loaded(self) -> bool:
        """Check if features are loaded."""
        return self._song_features is not None
