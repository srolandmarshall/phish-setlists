"""Apply precomputed historical probabilities to generated set openers."""

from __future__ import annotations

from math import sqrt
from random import Random
from typing import Any, Optional


def _preserves_constraints(songs: list[str], feature_store: Any) -> bool:
    positions = {song: index for index, song in enumerate(songs)}
    get_must_follow = getattr(feature_store, "get_songs_that_must_follow", None)
    if callable(get_must_follow):
        for song, index in positions.items():
            for required_song in get_must_follow(song):
                if required_song in positions and positions[required_song] < index:
                    return False

    get_mandatory_next = getattr(feature_store, "get_mandatory_next_songs", None)
    is_forbidden = getattr(feature_store, "is_forbidden_transition", None)
    for first, second in zip(songs, songs[1:]):
        if callable(get_mandatory_next) and second in get_mandatory_next(first):
            continue
        if callable(is_forbidden) and is_forbidden(first, second):
            return False

    if callable(get_mandatory_next):
        for index, song in enumerate(songs[:-1]):
            present_next = get_mandatory_next(song).intersection(positions)
            if present_next and songs[index + 1] not in present_next:
                return False
    return True


def apply_historical_set_openers(
    generated: Any,
    feature_store: Any,
    *,
    era: Optional[str],
    rng: Random,
) -> None:
    """Move a historically plausible song to the start of each generated set.

    Selection is restricted to songs already chosen for the set, so all
    generator eligibility, era, uniqueness, and song-count constraints remain
    intact. Era-specific statistics are used when sufficiently populated;
    FeatureStore supplies the all-era fallback for sparse eras.
    """
    if feature_store is None or not hasattr(feature_store, "get_set_openers_for_set"):
        return

    for set_index, segment in enumerate(generated.sets, start=1):
        # Keep the generated closer fixed; opener selection only promotes a
        # song from the middle of this already eligible set.
        if len(segment.songs) < 3:
            continue

        set_label = f"set{set_index}"
        def candidate_weights(opener_stats: list[Any]) -> tuple[list[str], list[float]]:
            stats_by_song = {stat.song_name: stat for stat in opener_stats}
            candidates: list[str] = []
            weights: list[float] = []
            for song in segment.songs[1:-1]:
                stat = stats_by_song.get(song)
                if stat is None or stat.opening_count <= 0 or stat.total_count <= 0:
                    continue
                weight = stat.opening_probability * sqrt(stat.total_count)
                if weight > 0:
                    candidates.append(song)
                    weights.append(weight)
            return candidates, weights

        opener_stats = feature_store.get_set_openers_for_set(set_label, era=era)
        candidates, weights = candidate_weights(opener_stats)
        if not candidates and era:
            # A populated era can still have no opener observations for this
            # generated candidate pool; use the precomputed all-era table then.
            candidates, weights = candidate_weights(
                feature_store.get_set_openers_for_set(set_label, era=None)
            )

        if not candidates:
            continue

        selected = rng.choices(candidates, weights=weights, k=1)[0]
        if selected != segment.songs[0]:
            reordered = [selected, *[song for song in segment.songs if song != selected]]
            if not _preserves_constraints(reordered, feature_store):
                continue
            segment.songs[:] = reordered
            generated.metadata.notes.append(
                f"Selected {selected} as {segment.label} opener from historical {era or 'all-era'} opener frequencies."
            )
