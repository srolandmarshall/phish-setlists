"""Feature engineering utilities for ML models."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def compute_set_ordering_constraints(
    tracks_df: pd.DataFrame,
    min_cooccurrence: int = 20,
    directionality_threshold: float = 0.90,
) -> pd.DataFrame:
    """
    Detect ordering constraints for song pairs within the same set.
    
    Identifies pairs where A and B often appear together, and when they do,
    A almost always comes before B (regardless of distance between them).
    
    Example: Mike's Song and Weekapaug Groove
      - Appear together in 400+ sets
      - Mike's comes first 98% of the time
      - Distance varies (sometimes adjacent, sometimes 3+ songs apart)
    
    Args:
        tracks_df: DataFrame with [song_effective_title, show_id, canonical_set, position]
        min_cooccurrence: Minimum times pair must appear together
        directionality_threshold: Minimum % for ordering constraint (0.90 = 90%)
        
    Returns:
        DataFrame with [song_a, song_b, set_label, cooccurrence_count, 
                       a_before_b_count, a_before_b_ratio, is_ordering_mandatory]
    """
    if tracks_df.empty or "position" not in tracks_df.columns:
        return pd.DataFrame(columns=[
            "song_a", "song_b", "set_label", "cooccurrence_count",
            "a_before_b_count", "a_before_b_ratio", "is_ordering_mandatory"
        ])
    
    # For each show/set, get all pairs of songs with their positions
    results = []
    
    grouped = tracks_df.groupby(["show_id", "canonical_set"])
    for (show_id, set_label), group in grouped:
        songs = group[["song_effective_title", "position"]].values
        
        # Check all pairs in this set
        for i in range(len(songs)):
            for j in range(i + 1, len(songs)):
                song_a, pos_a = songs[i]
                song_b, pos_b = songs[j]
                
                # Record which comes first
                if pos_a < pos_b:
                    results.append({
                        "song_a": song_a,
                        "song_b": song_b,
                        "set_label": set_label,
                        "a_before_b": True,
                    })
                else:
                    results.append({
                        "song_a": song_a,
                        "song_b": song_b,
                        "set_label": set_label,
                        "a_before_b": False,
                    })
    
    if not results:
        return pd.DataFrame(columns=[
            "song_a", "song_b", "set_label", "cooccurrence_count",
            "a_before_b_count", "a_before_b_ratio", "is_ordering_mandatory"
        ])
    
    pairs_df = pd.DataFrame(results)
    
    # Aggregate: count cooccurrences and ordering
    stats = pairs_df.groupby(["song_a", "song_b", "set_label"]).agg(
        cooccurrence_count=("a_before_b", "count"),
        a_before_b_count=("a_before_b", "sum"),
    ).reset_index()
    
    # Calculate ordering ratio
    stats["a_before_b_ratio"] = stats["a_before_b_count"] / stats["cooccurrence_count"]
    
    # Filter by minimum cooccurrence
    stats = stats[stats["cooccurrence_count"] >= min_cooccurrence].copy()
    
    # Detect mandatory ordering (A before B happens 90%+ of the time)
    stats["is_ordering_mandatory"] = (
        stats["a_before_b_ratio"] >= directionality_threshold
    )
    
    return stats


def compute_directional_transitions(
    transitions_df: pd.DataFrame,
    min_support: int = 10,
    mandatory_threshold: float = 0.85,
    adjacency_threshold: float = 1.5,
) -> pd.DataFrame:
    """
    Compute directional transition rules with constraints.
    
    Identifies:
    - Mandatory forward sequences (A→B happens 85%+ when A appears)
    - Forbidden reverse sequences (B→A rarely/never happens)
    - Adjacency requirements (songs typically next to each other)
    
    Args:
        transitions_df: DataFrame with [from_title, to_title, canonical_set, count]
        min_support: Minimum occurrences to consider
        mandatory_threshold: Confidence threshold for mandatory sequences (0-1)
        adjacency_threshold: Max average gap for adjacency requirement
        
    Returns:
        DataFrame with [from_song, to_song, set_label, forward_count, reverse_count,
                       forward_confidence, is_mandatory, is_reverse_forbidden, avg_gap]
    """
    if transitions_df.empty:
        return pd.DataFrame(columns=[
            "from_song", "to_song", "set_label", "forward_count", "reverse_count",
            "forward_confidence", "is_mandatory", "is_reverse_forbidden", "avg_gap"
        ])
    
    # Count forward transitions (A→B)
    forward = transitions_df.groupby(
        ["from_title", "to_title", "canonical_set"], as_index=False
    )["count"].sum()
    forward.columns = ["from_song", "to_song", "set_label", "forward_count"]
    
    # Count reverse transitions (B→A) 
    reverse = transitions_df.groupby(
        ["to_title", "from_title", "canonical_set"], as_index=False
    )["count"].sum()
    reverse.columns = ["from_song", "to_song", "set_label", "reverse_count"]
    
    # Merge forward and reverse counts
    directional = forward.merge(
        reverse, on=["from_song", "to_song", "set_label"], how="outer"
    ).fillna(0)
    
    # Calculate how often from_song appears (denominator for confidence)
    from_totals = transitions_df.groupby(
        ["from_title", "canonical_set"], as_index=False
    )["count"].sum()
    from_totals.columns = ["from_song", "set_label", "from_total"]
    
    directional = directional.merge(
        from_totals, on=["from_song", "set_label"], how="left"
    )
    
    # Calculate forward confidence: P(B|A) = count(A→B) / count(A)
    directional["forward_confidence"] = (
        directional["forward_count"] / directional["from_total"]
    )
    
    # Filter by minimum support
    directional = directional[directional["forward_count"] >= min_support].copy()
    
    # Detect mandatory sequences (A→B happens 85%+ of the time A appears)
    directional["is_mandatory"] = (
        directional["forward_confidence"] >= mandatory_threshold
    )
    
    # Detect forbidden reverse (B→A is rare, <5% as common as A→B)
    directional["is_reverse_forbidden"] = (
        (directional["reverse_count"] < directional["forward_count"] * 0.05) &
        (directional["forward_count"] >= min_support)
    )
    
    # Placeholder for avg_gap (would need positional data to compute)
    directional["avg_gap"] = 0.0
    
    return directional[
        ["from_song", "to_song", "set_label", "forward_count", "reverse_count",
         "forward_confidence", "is_mandatory", "is_reverse_forbidden", "avg_gap"]
    ]


def compute_set_entropy(freq_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Shannon entropy for song set placement.
    
    High entropy = song appears across many sets (versatile)
    Low entropy = song is set-specific (predictable)
    
    Args:
        freq_df: DataFrame with columns [song_effective_title, canonical_set, probability]
        
    Returns:
        DataFrame with columns [song_effective_title, set_entropy]
    """
    if freq_df.empty or "probability" not in freq_df.columns:
        return pd.DataFrame(columns=["song_effective_title", "set_entropy"])
    
    def _entropy(probs: pd.Series) -> float:
        p = probs[probs > 0]
        return float(-np.sum(p * np.log2(p)))
    
    entropy = (
        freq_df.groupby("song_effective_title")["probability"]
        .apply(_entropy)
        .reset_index(name="set_entropy")
    )
    return entropy


def compute_transition_lift(
    transitions_df: pd.DataFrame,
    song_freq_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute lift metric for song transitions.
    
    Lift = P(A→B) / (P(A) * P(B))
    Lift > 1 means the transition is more common than random
    
    Args:
        transitions_df: DataFrame with [from_title, to_title, canonical_set, count]
        song_freq_df: DataFrame with [song_effective_title, canonical_set, count]
        
    Returns:
        transitions_df with added 'lift' column
    """
    if transitions_df.empty or song_freq_df.empty:
        return transitions_df.assign(lift=np.nan)
    
    # Get per-set totals
    set_totals = song_freq_df.groupby("canonical_set")["count"].sum().to_dict()
    
    # Join song frequencies
    trans_with_freq = transitions_df.copy()
    trans_with_freq = trans_with_freq.merge(
        song_freq_df.rename(columns={"song_effective_title": "from_title", "count": "from_count"})[
            ["from_title", "canonical_set", "from_count"]
        ],
        on=["from_title", "canonical_set"],
        how="left",
    )
    trans_with_freq = trans_with_freq.merge(
        song_freq_df.rename(columns={"song_effective_title": "to_title", "count": "to_count"})[
            ["to_title", "canonical_set", "to_count"]
        ],
        on=["to_title", "canonical_set"],
        how="left",
    )
    
    # Compute lift
    trans_with_freq["set_total"] = trans_with_freq["canonical_set"].map(set_totals)
    trans_with_freq["expected"] = (
        (trans_with_freq["from_count"] / trans_with_freq["set_total"])
        * (trans_with_freq["to_count"] / trans_with_freq["set_total"])
        * trans_with_freq["set_total"]
    )
    trans_with_freq["lift"] = trans_with_freq["count"] / trans_with_freq["expected"]
    
    return trans_with_freq[
        ["from_title", "to_title", "canonical_set", "count", "lift"]
    ].copy()


def identify_multi_home_songs(
    freq_df: pd.DataFrame,
    min_probability: float = 0.15,
) -> pd.DataFrame:
    """
    Identify songs that appear in multiple sets with significant probability.
    
    Args:
        freq_df: DataFrame with [song_effective_title, canonical_set, probability]
        min_probability: Minimum probability threshold for a set to count
        
    Returns:
        DataFrame with [song_effective_title, set_count, primary_set, sets]
    """
    if freq_df.empty:
        return pd.DataFrame(columns=["song_effective_title", "set_count", "primary_set", "sets"])
    
    # Filter significant placements
    significant = freq_df[freq_df["probability"] >= min_probability].copy()
    
    # Group by song
    multi_home = (
        significant.groupby("song_effective_title")
        .agg(
            set_count=("canonical_set", "nunique"),
            sets=("canonical_set", lambda x: sorted(x.tolist())),
        )
        .reset_index()
    )
    
    # Find primary set (highest probability)
    primary = (
        freq_df.sort_values("probability", ascending=False)
        .groupby("song_effective_title")
        .first()[["canonical_set"]]
        .rename(columns={"canonical_set": "primary_set"})
    )
    
    multi_home = multi_home.merge(primary, on="song_effective_title", how="left")
    
    return multi_home[multi_home["set_count"] > 1].reset_index(drop=True)


def build_song_features(
    freq_df: pd.DataFrame,
    transitions_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Build comprehensive song-level features for ML.
    
    Args:
        freq_df: Song set frequencies
        transitions_df: Optional transition counts
        
    Returns:
        DataFrame with features per song
    """
    features = freq_df.copy()
    
    # Add entropy
    entropy = compute_set_entropy(freq_df)
    features = features.merge(entropy, on="song_effective_title", how="left")
    
    # Add total appearances
    total_counts = (
        freq_df.groupby("song_effective_title")["count"]
        .sum()
        .reset_index(name="total_appearances")
    )
    features = features.merge(total_counts, on="song_effective_title", how="left")
    
    # Pivot to wide format for per-set probabilities
    wide = features.pivot(
        index="song_effective_title",
        columns="canonical_set",
        values="probability",
    ).reset_index()
    
    # Fill missing sets with 0
    for col in ["set1", "set2", "set3", "encore"]:
        if col not in wide.columns:
            wide[col] = 0.0
        else:
            wide[col] = wide[col].fillna(0.0)
    
    # Merge back with entropy and total
    final = wide.merge(entropy, on="song_effective_title", how="left")
    final = final.merge(total_counts, on="song_effective_title", how="left")
    
    return final
