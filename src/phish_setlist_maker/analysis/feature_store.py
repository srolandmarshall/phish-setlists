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


@dataclass
class DirectionalRule:
    """Directional sequence rule with constraints."""
    
    from_song: str
    to_song: str
    set_label: str
    forward_confidence: float
    is_mandatory: bool
    is_reverse_forbidden: bool


@dataclass
class OrderingConstraint:
    """Set-level ordering constraint (A must precede B in same set)."""
    
    song_a: str
    song_b: str
    set_label: str
    cooccurrence_count: int
    a_before_b_ratio: float
    is_mandatory: bool


@dataclass
class CrossSetDependency:
    """Cross-set dependency (song A in set X requires song B in earlier sets)."""
    
    dependent_song: str
    required_song: str
    target_set: str
    required_sets: list[str]
    confidence: float
    description: str


class FeatureStore:
    """In-memory cache of ML features for fast lookup."""

    def __init__(self, features_dir: Path):
        self.features_dir = features_dir
        self._song_features: Optional[Dict[str, SongFeatures]] = None
        self._transition_lifts: Optional[Dict[Tuple[str, str], TransitionFeature]] = None
        self._multi_home_songs: Optional[Set[str]] = None
        self._directional_rules: Optional[Dict[Tuple[str, str], DirectionalRule]] = None
        self._mandatory_sequences: Optional[Dict[str, Set[str]]] = None
        self._forbidden_transitions: Optional[Set[Tuple[str, str]]] = None
        self._ordering_constraints: Optional[Dict[str, Set[str]]] = None  # song_a -> songs that must come after
        self._cross_set_dependencies: Optional[list[CrossSetDependency]] = None

    def load(self) -> None:
        """Load all feature tables into memory."""
        self._load_song_features()
        self._load_transition_lifts()
        self._load_multi_home_songs()
        self._load_directional_rules()
        self._load_ordering_constraints()
        self._load_cross_set_dependencies()

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

    def _load_directional_rules(self) -> None:
        """Load directional sequence rules."""
        directional_path = self.features_dir / "directional_transitions.parquet"
        
        # Gracefully handle missing file (Phase 2.2 feature)
        if not directional_path.exists():
            self._directional_rules = {}
            self._mandatory_sequences = {}
            self._forbidden_transitions = set()
            return
        
        df = pd.read_parquet(directional_path)
        
        # Build directional rules dict
        self._directional_rules = {}
        for _, row in df.iterrows():
            key = (row["from_song"], row["to_song"])
            self._directional_rules[key] = DirectionalRule(
                from_song=row["from_song"],
                to_song=row["to_song"],
                set_label=row["set_label"],
                forward_confidence=float(row["forward_confidence"]),
                is_mandatory=bool(row["is_mandatory"]),
                is_reverse_forbidden=bool(row["is_reverse_forbidden"]),
            )
        
        # Build mandatory sequences index (from_song → set of must_follow songs)
        self._mandatory_sequences = {}
        mandatory_df = df[df["is_mandatory"]]
        for _, row in mandatory_df.iterrows():
            from_song = row["from_song"]
            to_song = row["to_song"]
            if from_song not in self._mandatory_sequences:
                self._mandatory_sequences[from_song] = set()
            self._mandatory_sequences[from_song].add(to_song)
        
        # Build forbidden transitions set
        self._forbidden_transitions = set()
        forbidden_df = df[df["is_reverse_forbidden"]]
        for _, row in forbidden_df.iterrows():
            # If A→B is mandatory and forbidden_reverse, then B→A is forbidden
            forbidden_pair = (row["to_song"], row["from_song"])
            self._forbidden_transitions.add(forbidden_pair)

    def _load_ordering_constraints(self) -> None:
        """Load set-level ordering constraints."""
        ordering_path = self.features_dir / "ordering_constraints.parquet"
        
        # Gracefully handle missing file (Phase 2.2 feature)
        if not ordering_path.exists():
            self._ordering_constraints = {}
            return
        
        df = pd.read_parquet(ordering_path)
        
        # Build index: song_a -> set of songs that must come after song_a
        self._ordering_constraints = {}
        mandatory_df = df[df["is_ordering_mandatory"]]
        
        for _, row in mandatory_df.iterrows():
            song_a = row["song_a"]
            song_b = row["song_b"]
            
            if song_a not in self._ordering_constraints:
                self._ordering_constraints[song_a] = set()
            self._ordering_constraints[song_a].add(song_b)

    def _load_cross_set_dependencies(self) -> None:
        """Load cross-set dependency rules."""
        dep_path = self.features_dir / "cross_set_dependencies.parquet"
        
        # Gracefully handle missing file (new Phase 2 feature)
        if not dep_path.exists():
            self._cross_set_dependencies = []
            return
        
        df = pd.read_parquet(dep_path)
        
        # Convert dataframe to list of CrossSetDependency objects
        self._cross_set_dependencies = []
        for _, row in df.iterrows():
            # Handle required_sets as either string or list
            required_sets = row["required_sets"]
            if isinstance(required_sets, str):
                import json
                required_sets = json.loads(required_sets)
            
            dep = CrossSetDependency(
                dependent_song=row["dependent_song"],
                required_song=row["required_song"],
                target_set=row["target_set"],
                required_sets=required_sets,
                confidence=float(row["confidence"]),
                description=row["description"],
            )
            self._cross_set_dependencies.append(dep)

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

    def get_mandatory_next_songs(self, from_song: str) -> Set[str]:
        """Get songs that must follow the given song."""
        if self._mandatory_sequences is None:
            return set()
        return self._mandatory_sequences.get(from_song, set())

    def is_forbidden_transition(self, from_song: str, to_song: str) -> bool:
        """Check if a transition is forbidden (reverse of mandatory sequence)."""
        if self._forbidden_transitions is None:
            return False
        return (from_song, to_song) in self._forbidden_transitions

    def get_directional_rule(
        self, from_song: str, to_song: str
    ) -> Optional[DirectionalRule]:
        """Get directional rule for a song pair."""
        if self._directional_rules is None:
            return None
        return self._directional_rules.get((from_song, to_song))

    def get_songs_that_must_follow(self, song: str) -> Set[str]:
        """Get songs that must come after this song in the same set."""
        if self._ordering_constraints is None:
            return set()
        return self._ordering_constraints.get(song, set())

    def violates_ordering_constraint(
        self, songs_so_far: List[str], candidate_song: str
    ) -> bool:
        """
        Check if adding candidate_song would violate ordering constraints.
        
        Returns True if candidate_song must come BEFORE any song already in the set.
        
        Example: If Mike's Song is already in songs_so_far, and candidate is Weekapaug,
                 this returns False (OK to add Weekapaug after Mike's).
                 But if Weekapaug is in songs_so_far and candidate is Mike's,
                 this returns True (VIOLATION - Mike's must come before Weekapaug).
        """
        if self._ordering_constraints is None:
            return False
        
        # Check if candidate must come BEFORE any song already in the set
        must_follow = self.get_songs_that_must_follow(candidate_song)
        for existing_song in songs_so_far:
            if existing_song in must_follow:
                # candidate must come before existing_song, but existing is already there
                return True
        
        return False

    def violates_cross_set_dependency(
        self, candidate_song: str, target_set: str, previous_sets_songs: Dict[str, list[str]]
    ) -> bool:
        """
        Check if adding candidate_song to target_set would violate cross-set dependencies.
        
        Args:
            candidate_song: Song being considered for placement
            target_set: Set where song would be placed (e.g., "encore")
            previous_sets_songs: Dict mapping set_label -> list of songs already in that set
                                 Example: {"set1": ["Tweezer", "Stash"], "set2": ["YEM"]}
        
        Returns:
            True if placement would violate a dependency (required song missing from earlier sets)
            
        Example: Tweezer Reprise in encore requires Tweezer in set1/set2/set3.
                 If previous_sets_songs doesn't contain Tweezer, returns True (violation).
        """
        if self._cross_set_dependencies is None:
            return False
        
        # Check all dependencies for this candidate song in this target set
        for dep in self._cross_set_dependencies:
            if dep.dependent_song != candidate_song:
                continue
            if dep.target_set != target_set:
                continue
            
            # This dependency applies - check if required song exists in required sets
            required_song_found = False
            for set_label in dep.required_sets:
                if set_label in previous_sets_songs:
                    if dep.required_song in previous_sets_songs[set_label]:
                        required_song_found = True
                        break
            
            if not required_song_found:
                # Dependency violated: required song not found in any required set
                return True
        
        return False
