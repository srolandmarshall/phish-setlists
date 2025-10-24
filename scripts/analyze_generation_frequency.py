#!/usr/bin/env python3
"""
Frequency analysis tool for generated setlists.

Generates a large number of setlists and analyzes their statistical properties
to identify potential outliers or unrealistic patterns compared to historical data.
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

import pandas as pd

from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator.core import SetlistGenerator


def generate_many_setlists(
    num_setlists: int,
    num_sets: int = 2,
    include_encore: bool = True,
    use_ml_features: bool = True,
    seed: int = 42,
) -> List[Dict]:
    """Generate many setlists and return their song lists."""
    setlists = []
    
    with session_scope() as session:
        for i in range(num_setlists):
            # Use different seed for each generation
            from random import Random
            rng = Random(seed + i)
            
            generator = SetlistGenerator(
                session=session,
                rng=rng,
                use_ml_features=use_ml_features,
            )
            
            result = generator.generate(
                num_sets=num_sets,
                include_encore=include_encore,
            )
            
            # Extract songs by set
            setlist_data = {
                "index": i,
                "all_songs": [],
            }
            
            for s in result.sets:
                set_label = s.label.lower().replace(" ", "")
                setlist_data[set_label] = s.songs
                setlist_data["all_songs"].extend(s.songs)
            
            if result.encore:
                setlist_data["encore"] = result.encore.songs
                setlist_data["all_songs"].extend(result.encore.songs)
            
            setlists.append(setlist_data)
    
    return setlists


def analyze_song_frequencies(setlists: List[Dict]) -> pd.DataFrame:
    """Analyze how often each song appears across all generated setlists."""
    song_counts = Counter()
    set_specific_counts = defaultdict(Counter)
    
    for setlist in setlists:
        # Count overall appearances
        for song in setlist["all_songs"]:
            song_counts[song] += 1
        
        # Count set-specific appearances
        for set_label in ["set1", "set2", "set3", "encore"]:
            if set_label in setlist:
                for song in setlist[set_label]:
                    set_specific_counts[set_label][song] += 1
    
    # Build dataframe
    rows = []
    for song, count in song_counts.items():
        row = {
            "song": song,
            "total_appearances": count,
            "appearance_rate": count / len(setlists),
        }
        
        # Add set-specific rates
        for set_label in ["set1", "set2", "set3", "encore"]:
            set_count = set_specific_counts[set_label].get(song, 0)
            row[f"{set_label}_count"] = set_count
            row[f"{set_label}_rate"] = set_count / len(setlists) if len(setlists) > 0 else 0
        
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df = df.sort_values("total_appearances", ascending=False)
    
    return df


def analyze_set_closers(setlists: List[Dict]) -> pd.DataFrame:
    """Analyze which songs are selected as set closers."""
    closer_counts = defaultdict(Counter)
    
    for setlist in setlists:
        for set_label in ["set1", "set2", "set3", "encore"]:
            if set_label in setlist and setlist[set_label]:
                # Last song in the set
                closer = setlist[set_label][-1]
                closer_counts[set_label][closer] += 1
    
    # Build dataframe
    rows = []
    for set_label, counts in closer_counts.items():
        for song, count in counts.items():
            rows.append({
                "set": set_label,
                "song": song,
                "closer_count": count,
                "closer_rate": count / len(setlists),
            })
    
    df = pd.DataFrame(rows)
    df = df.sort_values(["set", "closer_count"], ascending=[True, False])
    
    return df


def compare_to_historical(
    generated_freq: pd.DataFrame,
    historical_features_path: Path,
) -> pd.DataFrame:
    """
    Compare generated frequencies to historical probabilities.
    
    Identifies songs that appear significantly more or less often than expected.
    """
    # Load historical features
    historical = pd.read_parquet(historical_features_path)
    
    # Merge on song name
    comparison = generated_freq.merge(
        historical[["song_effective_title", "total_appearances", "set1", "set2", "set3", "encore"]],
        left_on="song",
        right_on="song_effective_title",
        how="left",
        suffixes=("_gen", "_hist")
    )
    
    # Calculate deviation ratios
    comparison["set1_deviation"] = comparison["set1_rate"] / comparison["set1"].fillna(0.001)
    comparison["set2_deviation"] = comparison["set2_rate"] / comparison["set2"].fillna(0.001)
    
    # Flag outliers (appearing 2x or more than expected)
    comparison["is_set1_outlier"] = comparison["set1_deviation"] > 2.0
    comparison["is_set2_outlier"] = comparison["set2_deviation"] > 2.0
    
    return comparison


def print_summary_statistics(
    freq_df: pd.DataFrame,
    closers_df: pd.DataFrame,
    num_setlists: int,
):
    """Print summary statistics to console."""
    print(f"\n{'='*80}")
    print(f"FREQUENCY ANALYSIS: {num_setlists} Generated Setlists")
    print(f"{'='*80}\n")
    
    print(f"Total unique songs generated: {len(freq_df)}")
    print(f"Average songs per setlist: {freq_df['total_appearances'].sum() / num_setlists:.1f}")
    
    print(f"\n{'='*80}")
    print("TOP 20 MOST FREQUENT SONGS (across all sets)")
    print(f"{'='*80}")
    print(f"{'Rank':<6}{'Song':<40}{'Count':<10}{'Rate':<10}")
    print("-" * 80)
    
    for idx, row in freq_df.head(20).iterrows():
        rank = idx + 1 if isinstance(idx, int) else "-"
        print(f"{rank:<6}{row['song'][:38]:<40}{row['total_appearances']:<10}{row['appearance_rate']:<10.2%}")
    
    print(f"\n{'='*80}")
    print("TOP 10 SET 1 CLOSERS")
    print(f"{'='*80}")
    set1_closers = closers_df[closers_df["set"] == "set1"].head(10)
    print(f"{'Rank':<6}{'Song':<40}{'Count':<10}{'Rate':<10}")
    print("-" * 80)
    
    for idx, row in set1_closers.iterrows():
        rank = idx + 1 if isinstance(idx, int) else "-"
        print(f"{rank:<6}{row['song'][:38]:<40}{row['closer_count']:<10}{row['closer_rate']:<10.2%}")
    
    print(f"\n{'='*80}")
    print("TOP 10 SET 2 CLOSERS")
    print(f"{'='*80}")
    set2_closers = closers_df[closers_df["set"] == "set2"].head(10)
    print(f"{'Rank':<6}{'Song':<40}{'Count':<10}{'Rate':<10}")
    print("-" * 80)
    
    for idx, row in set2_closers.iterrows():
        rank = idx + 1 if isinstance(idx, int) else "-"
        print(f"{rank:<6}{row['song'][:38]:<40}{row['closer_count']:<10}{row['closer_rate']:<10.2%}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-n", "--num-setlists",
        type=int,
        default=100,
        help="Number of setlists to generate (default: 100)",
    )
    parser.add_argument(
        "--num-sets",
        type=int,
        default=2,
        help="Number of sets per show (default: 2)",
    )
    parser.add_argument(
        "--no-encore",
        action="store_true",
        help="Exclude encore from generation",
    )
    parser.add_argument(
        "--no-ml",
        action="store_true",
        help="Disable ML features (use legacy generator)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (default: random)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/analytics/frequency_analysis"),
        help="Output directory for analysis results",
    )
    parser.add_argument(
        "--compare-historical",
        action="store_true",
        help="Compare to historical features (requires song_features.parquet)",
    )
    
    args = parser.parse_args()
    
    # Use random seed if not specified
    if args.seed is None:
        import time
        args.seed = int(time.time() * 1000) % (2**31)
    
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nGenerating {args.num_setlists} setlists...")
    print(f"  Sets per show: {args.num_sets}")
    print(f"  Include encore: {not args.no_encore}")
    print(f"  Use ML features: {not args.no_ml}")
    print(f"  Random seed: {args.seed}")
    
    setlists = generate_many_setlists(
        num_setlists=args.num_setlists,
        num_sets=args.num_sets,
        include_encore=not args.no_encore,
        use_ml_features=not args.no_ml,
        seed=args.seed,
    )
    
    print(f"\n✅ Generated {len(setlists)} setlists")
    
    print("\nAnalyzing song frequencies...")
    freq_df = analyze_song_frequencies(setlists)
    freq_path = args.output_dir / "song_frequencies.parquet"
    freq_df.to_parquet(freq_path, index=False)
    print(f"  → {freq_path}")
    
    print("\nAnalyzing set closers...")
    closers_df = analyze_set_closers(setlists)
    closers_path = args.output_dir / "set_closers.parquet"
    closers_df.to_parquet(closers_path, index=False)
    print(f"  → {closers_path}")
    
    if args.compare_historical:
        historical_path = Path("data/analytics/features/song_features.parquet")
        if historical_path.exists():
            print("\nComparing to historical data...")
            comparison = compare_to_historical(freq_df, historical_path)
            comparison_path = args.output_dir / "historical_comparison.parquet"
            comparison.to_parquet(comparison_path, index=False)
            print(f"  → {comparison_path}")
            
            # Show outliers
            outliers = comparison[
                (comparison["is_set1_outlier"] == True) | 
                (comparison["is_set2_outlier"] == True)
            ]
            if not outliers.empty:
                print(f"\n⚠️  Found {len(outliers)} potential outliers (appearing 2x+ more than expected):")
                for _, row in outliers.head(10).iterrows():
                    print(f"  - {row['song']}: Set1 {row['set1_deviation']:.1f}x, Set2 {row['set2_deviation']:.1f}x")
        else:
            print(f"\n⚠️  Historical features not found at {historical_path}")
            print("   Run 'poetry run python scripts/build_features.py' first")
    
    # Print summary to console
    print_summary_statistics(freq_df, closers_df, args.num_setlists)
    
    print(f"\n✅ Analysis complete! Results saved to {args.output_dir}/")


if __name__ == "__main__":
    main()
