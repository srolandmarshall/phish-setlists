#!/usr/bin/env python3
"""Build feature tables for ML models from analytics data."""

import argparse
from pathlib import Path

import pandas as pd

from phish_setlist_maker.analysis.features import (
    build_song_features,
    compute_set_entropy,
    compute_transition_lift,
    identify_multi_home_songs,
)
from phish_setlist_maker.analysis.database import build_set_ending_frequencies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/analytics"),
        help="Directory with source Parquet files",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/analytics/features"),
        help="Output directory for feature tables",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading source data...")
    freq_df = pd.read_parquet(args.data_dir / "song_set_frequencies.parquet")
    transitions_df = pd.read_parquet(args.data_dir / "song_transitions.parquet")
    tracks_df = pd.read_parquet(args.data_dir / "tracks.parquet")

    print(f"  → {len(freq_df)} frequency records")
    print(f"  → {len(transitions_df)} transitions")
    print(f"  → {len(tracks_df)} tracks")

    print("\nComputing set entropy...")
    entropy = compute_set_entropy(freq_df)
    entropy_path = args.out_dir / "song_set_entropy.parquet"
    entropy.to_parquet(entropy_path, index=False)
    print(f"  → {entropy_path} ({len(entropy)} songs)")

    print("\nIdentifying multi-home songs...")
    multi_home = identify_multi_home_songs(freq_df, min_probability=0.15)
    multi_home_path = args.out_dir / "multi_home_songs.parquet"
    multi_home.to_parquet(multi_home_path, index=False)
    print(f"  → {multi_home_path} ({len(multi_home)} songs)")
    print(f"  Examples: {', '.join(multi_home.head(5)['song_effective_title'].tolist())}")

    print("\nComputing transition lift...")
    # Need song counts per set for lift calculation
    song_counts = (
        freq_df.groupby(["song_effective_title", "canonical_set"])["count"]
        .first()
        .reset_index()
    )
    transitions_with_lift = compute_transition_lift(transitions_df, song_counts)
    lift_path = args.out_dir / "transition_lift.parquet"
    transitions_with_lift.to_parquet(lift_path, index=False)
    print(f"  → {lift_path}")
    
    # Show top lift transitions
    top_lift = transitions_with_lift.nlargest(5, "lift")
    print(f"  Top lift transitions:")
    for _, row in top_lift.iterrows():
        print(f"    {row['from_title']} → {row['to_title']} (lift={row['lift']:.2f})")

    print("\nBuilding comprehensive song features...")
    song_features = build_song_features(freq_df, transitions_df)
    features_path = args.out_dir / "song_features.parquet"
    song_features.to_parquet(features_path, index=False)
    print(f"  → {features_path} ({len(song_features)} songs)")
    print(f"  Columns: {', '.join(song_features.columns.tolist())}")

    print("\nBuilding set-ending frequencies...")
    set_endings = build_set_ending_frequencies(
        tracks_df,
        allowed_sets=["set1", "set2", "set3", "encore"]
    )
    endings_path = args.out_dir / "set_ending_frequencies.parquet"
    set_endings.to_parquet(endings_path, index=False)
    print(f"  → {endings_path} ({len(set_endings)} song-set combinations)")
    
    # Show top set enders by probability
    for set_name in ["set1", "set2"]:
        set_data = set_endings[set_endings["canonical_set"] == set_name]
        if not set_data.empty:
            top_enders = set_data.nlargest(5, "ending_probability")
            print(f"  Top {set_name} enders:")
            for _, row in top_enders.iterrows():
                print(f"    {row['song_effective_title']}: {row['ending_probability']:.1%} ({row['ending_count']}/{row['total_count']})")

    print("\n✅ Feature engineering complete!")
    print(f"   All outputs in {args.out_dir}/")
    
    print("\nNote: To build set-ending TRACK lookup, run:")
    print("  poetry run python scripts/build_set_ending_tracks.py")


if __name__ == "__main__":
    main()
