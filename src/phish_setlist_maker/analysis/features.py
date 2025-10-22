"""Feature engineering utilities for ML models."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


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
