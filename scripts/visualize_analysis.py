#!/usr/bin/env python3
"""Generate Phase 1 analysis visualizations."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def plot_set_placement_heatmap(freq_df: pd.DataFrame, out_dir: Path):
    """Create heatmap of top songs by set placement probability."""
    # Get top 30 songs by total appearances
    top_songs = (
        freq_df.groupby("song_effective_title")["count"]
        .sum()
        .nlargest(30)
        .index.tolist()
    )
    
    # Pivot to wide format
    wide = freq_df[freq_df["song_effective_title"].isin(top_songs)].pivot(
        index="song_effective_title",
        columns="canonical_set",
        values="probability",
    ).fillna(0)
    
    # Reorder columns
    col_order = ["set1", "set2", "set3", "encore"]
    wide = wide[[c for c in col_order if c in wide.columns]]
    
    # Create heatmap
    fig, ax = plt.subplots(figsize=(8, 14))
    sns.heatmap(wide, annot=True, fmt=".2f", cmap="YlOrRd", ax=ax, cbar_kws={"label": "Probability"})
    ax.set_title("Top 30 Songs: Set Placement Probabilities")
    ax.set_xlabel("Set")
    ax.set_ylabel("Song")
    
    plt.tight_layout()
    out_path = out_dir / "set_placement_heatmap.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"  → {out_path}")
    plt.close()


def plot_entropy_distribution(entropy_df: pd.DataFrame, out_dir: Path):
    """Plot distribution of set entropy scores."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Histogram
    ax1.hist(entropy_df["set_entropy"], bins=30, edgecolor="black", alpha=0.7)
    ax1.set_xlabel("Set Entropy (bits)")
    ax1.set_ylabel("Number of Songs")
    ax1.set_title("Distribution of Set Entropy")
    ax1.axvline(entropy_df["set_entropy"].median(), color="red", linestyle="--", label="Median")
    ax1.legend()
    
    # Top and bottom entropy songs
    top_10 = entropy_df.nlargest(10, "set_entropy")
    bottom_10 = entropy_df.nsmallest(10, "set_entropy")
    
    combined = pd.concat([
        top_10.assign(category="High Entropy (Versatile)"),
        bottom_10.assign(category="Low Entropy (Predictable)"),
    ])
    
    sns.barplot(
        data=combined,
        y="song_effective_title",
        x="set_entropy",
        hue="category",
        ax=ax2,
        dodge=False,
    )
    ax2.set_xlabel("Set Entropy")
    ax2.set_ylabel("")
    ax2.set_title("Most/Least Versatile Songs")
    ax2.legend(title="")
    
    plt.tight_layout()
    out_path = out_dir / "entropy_distribution.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"  → {out_path}")
    plt.close()


def plot_transition_network(transitions_df: pd.DataFrame, out_dir: Path, top_n: int = 20):
    """Create visualization of top song transitions."""
    top_trans = transitions_df.nlargest(top_n, "lift")
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create position mapping for songs
    unique_songs = sorted(set(top_trans["from_title"]) | set(top_trans["to_title"]))
    y_pos = {song: i for i, song in enumerate(unique_songs)}
    
    # Draw arrows
    for _, row in top_trans.iterrows():
        from_y = y_pos[row["from_title"]]
        to_y = y_pos[row["to_title"]]
        
        # Arrow width based on lift
        width = min(row["lift"] / 50, 5)
        
        ax.annotate(
            "",
            xy=(1, to_y),
            xytext=(0, from_y),
            arrowprops=dict(
                arrowstyle="->",
                lw=width,
                alpha=0.6,
                color="steelblue",
            ),
        )
    
    # Add labels
    ax.set_yticks(range(len(unique_songs)))
    ax.set_yticklabels(unique_songs)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["From", "To"])
    ax.set_xlim(-0.2, 1.2)
    ax.set_title(f"Top {top_n} Song Transitions by Lift")
    
    plt.tight_layout()
    out_path = out_dir / "transition_network.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"  → {out_path}")
    plt.close()


def plot_temporal_trends(tracks_df: pd.DataFrame, out_dir: Path):
    """Plot song popularity over time."""
    # Get top 10 songs by total appearances
    top_songs = (
        tracks_df.groupby("song_effective_title")
        .size()
        .nlargest(10)
        .index.tolist()
    )
    
    # Count by year
    yearly = (
        tracks_df[tracks_df["song_effective_title"].isin(top_songs)]
        .groupby(["year", "song_effective_title"])
        .size()
        .reset_index(name="count")
    )
    
    fig, ax = plt.subplots(figsize=(14, 7))
    
    for song in top_songs:
        song_data = yearly[yearly["song_effective_title"] == song]
        ax.plot(song_data["year"], song_data["count"], marker="o", label=song, alpha=0.7)
    
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Performances")
    ax.set_title("Top 10 Songs: Popularity Over Time")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    out_path = out_dir / "temporal_trends.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"  → {out_path}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/analytics"),
        help="Directory with source data",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("docs/figures"),
        help="Output directory for figures",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    freq_df = pd.read_parquet(args.data_dir / "song_set_frequencies.parquet")
    entropy_df = pd.read_parquet(args.data_dir / "features" / "song_set_entropy.parquet")
    transitions_df = pd.read_parquet(args.data_dir / "features" / "transition_lift.parquet")
    tracks_df = pd.read_parquet(args.data_dir / "tracks.parquet")

    print("\nGenerating visualizations...")
    plot_set_placement_heatmap(freq_df, args.out_dir)
    plot_entropy_distribution(entropy_df, args.out_dir)
    plot_transition_network(transitions_df, args.out_dir)
    plot_temporal_trends(tracks_df, args.out_dir)

    print(f"\n✅ All visualizations saved to {args.out_dir}/")


if __name__ == "__main__":
    main()
