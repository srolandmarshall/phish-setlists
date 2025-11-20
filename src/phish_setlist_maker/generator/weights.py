"""Weight adjustment helpers for song selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import logging

from .feature_cache import FeatureCache
from .historical import SongFrequency
from ..analysis.feature_store import FeatureStore


@dataclass
class WeightingContext:
    use_ml_features: bool
    feature_store: Optional[FeatureStore]
    adjacency_bonus: float
    adjacency_min_support: int
    ml_placement_weight: float
    ml_transition_bonus: float
    logger: logging.Logger


def adjust_candidate_weights(
    weighted_candidates: List[Tuple[SongFrequency, float]],
    *,
    previous_song: Optional[str],
    adjacency_map: Optional[Dict[str, Dict[str, int]]],
    target_set: Optional[str],
    feature_cache: FeatureCache,
    context: WeightingContext,
) -> List[Tuple[SongFrequency, float]]:
    """Apply all candidate weight adjustments in a single pass."""

    # Pre-compute adjacency normalization for this previous song (if any).
    filtered_neighbors: Dict[str, int] = {}
    max_neighbor = 0
    if previous_song and adjacency_map:
        neighbors = adjacency_map.get(previous_song)
        if neighbors:
            filtered_neighbors = {
                song: count
                for song, count in neighbors.items()
                if count >= context.adjacency_min_support
            }
            if filtered_neighbors:
                max_neighbor = max(filtered_neighbors.values())

    mandatory_next = set()
    if context.use_ml_features and context.feature_store and previous_song:
        mandatory_next = context.feature_store.get_mandatory_next_songs(previous_song)

    adjusted: List[Tuple[SongFrequency, float]] = []

    if context.use_ml_features and context.feature_store:
        context.logger.info(
            "🔍 BIAS FIX: Applying frequency caps (use_ml=%s, store=%s, candidates=%d)",
            context.use_ml_features,
            context.feature_store is not None,
            len(weighted_candidates),
        )
        if weighted_candidates:
            context.logger.info(
                "🔍 BIAS FIX: Sample songs to check: %s",
                [candidate.title for candidate, _ in weighted_candidates[:5]],
            )

    for freq, weight in weighted_candidates:
        adjusted_weight = weight

        if context.use_ml_features and context.feature_store:
            bundle = feature_cache.get(freq.title)
            features = bundle["features"]
            mandatory_segues = bundle["mandatory_segues"]
            placement_prob = bundle["placement_prob"]

            if not features:
                context.logger.warning(
                    "⚠️  BIAS FIX: No features found for song: %s (repr: %r)",
                    freq.title,
                    freq.title,
                )
            if features:
                if freq.title in [
                    "Mike's Song",
                    "Runaway Jim",
                    "Colonel Forbin's Ascent",
                    "I Am Hydrogen",
                ]:
                    context.logger.info(
                        "🔍 BIAS FIX: Found features for %s - appearances: %d",
                        freq.title,
                        features.total_appearances,
                    )

                if features.total_appearances > 500:
                    capped_weight = adjusted_weight * 0.3
                    context.logger.info(
                        "⬇️  BIAS FIX: Reducing %s (>500 appearances): %.2f → %.2f",
                        freq.title,
                        adjusted_weight,
                        capped_weight,
                    )
                    adjusted_weight = capped_weight
                elif features.total_appearances > 300:
                    capped_weight = adjusted_weight * 0.5
                    context.logger.info(
                        "⬇️  BIAS FIX: Reducing %s (>300 appearances): %.2f → %.2f",
                        freq.title,
                        adjusted_weight,
                        capped_weight,
                    )
                    adjusted_weight = capped_weight
                elif features.total_appearances < 30:
                    adjusted_weight *= 0.25
                elif features.total_appearances < 50:
                    adjusted_weight *= 0.5

            if mandatory_segues:
                pattern_lengths = [len(seg.get("songs", [])) for seg in mandatory_segues]
                avg_pattern_length = sum(pattern_lengths) / len(pattern_lengths) if pattern_lengths else 1

                if avg_pattern_length > 1:
                    penalty = 1.0 / avg_pattern_length
                    penalized_weight = adjusted_weight * penalty
                    adjusted_weight = penalized_weight
                    context.logger.debug(
                        "Applying segue penalty to %s (pattern length %.1f): %.2f → %.2f",
                        freq.title,
                        avg_pattern_length,
                        weight,
                        penalized_weight,
                    )

            if placement_prob > 0 and target_set:
                adjusted_weight = (
                    adjusted_weight * (1 - context.ml_placement_weight)
                    + placement_prob * context.ml_placement_weight
                )

        if previous_song and max_neighbor > 0:
            neighbor_weight = filtered_neighbors.get(freq.title)
            if neighbor_weight:
                normalized = neighbor_weight / max_neighbor
                boost = 1.0 + context.adjacency_bonus * normalized
                adjusted_weight *= boost

        if context.use_ml_features and context.feature_store and previous_song:
            transition = context.feature_store.get_transition_lift(previous_song, freq.title)
            if transition and transition.lift > 2.0:  # Only boost strong transitions
                normalized_lift = min((transition.lift - 2.0) / 8.0, 1.0)
                boost = 1.0 + context.ml_transition_bonus * normalized_lift
                adjusted_weight *= boost

            if mandatory_next and freq.title in mandatory_next:
                adjusted_weight *= 3.0

        adjusted.append((freq, adjusted_weight))

    adjusted.sort(key=lambda x: -x[1])
    return adjusted
