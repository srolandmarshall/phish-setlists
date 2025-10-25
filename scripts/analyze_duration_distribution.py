#!/usr/bin/env python3
"""Statistical analysis of generated setlist durations."""

from datetime import date
from random import Random
from typing import Dict, List
import statistics

from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator.core import SetlistGenerator


def format_time(seconds: float) -> str:
    """Format seconds as MM:SS."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def analyze_distribution():
    """Generate many setlists and analyze duration distributions."""

    # Use 300 for good statistical power (n>30 is standard, n>100 is better)
    N = 300

    print("=" * 80)
    print(f"DURATION DISTRIBUTION ANALYSIS (N={N})")
    print("=" * 80)
    print()
    print("Generating setlists with dynamic jam intensity (default behavior)...")
    print("This may take a minute or two...\n")

    # Storage for durations (in seconds)
    set1_durations: List[float] = []
    set2_durations: List[float] = []
    encore_durations: List[float] = []
    total_durations: List[float] = []

    # Track how many songs per set
    set1_counts: List[int] = []
    set2_counts: List[int] = []

    # Track outliers (>90 minutes for Set 1/2)
    outliers: List[Dict] = []

    with session_scope() as session:
        for i in range(N):
            if (i + 1) % 50 == 0:
                print(f"  Generated {i + 1}/{N} setlists...")

            # Use different seeds for variety
            rng = Random(1000 + i)
            generator = SetlistGenerator(
                session=session,
                rng=rng,
                use_ml_features=True,
                jamminess=None,  # Dynamic selection
            )

            try:
                result = generator.generate(
                    reference_date=date(2023, 12, 31),
                    num_sets=2,
                    include_encore=True,
                )

                # Rough duration estimates (7 min avg per song for sets, 5 for encore)
                # In real world we'd use actual track durations
                set1_est = len(result.sets[0].songs) * 7 * 60
                set2_est = len(result.sets[1].songs) * 7 * 60
                encore_est = len(result.encore.songs) * 5 * 60 if result.encore else 0

                set1_durations.append(set1_est)
                set2_durations.append(set2_est)
                encore_durations.append(encore_est)
                total_durations.append(set1_est + set2_est + encore_est)

                set1_counts.append(len(result.sets[0].songs))
                set2_counts.append(len(result.sets[1].songs))

                # Check for outliers (>90 minutes = >540 seconds)
                if set1_est > 90 * 60:
                    outliers.append({
                        "seed": 1000 + i,
                        "set": "Set 1",
                        "duration": set1_est,
                        "songs": len(result.sets[0].songs),
                    })
                if set2_est > 90 * 60:
                    outliers.append({
                        "seed": 1000 + i,
                        "set": "Set 2",
                        "duration": set2_est,
                        "songs": len(result.sets[1].songs),
                    })

            except Exception as e:
                print(f"  ⚠️  Error generating setlist {i}: {e}")
                continue

    print(f"\n✓ Generated {len(set1_durations)} setlists successfully\n")

    # Calculate statistics
    def calc_stats(data: List[float], name: str, target_min: int, target_max: int):
        if not data:
            return

        mean_val = statistics.mean(data)
        median_val = statistics.median(data)
        stdev_val = statistics.stdev(data) if len(data) > 1 else 0
        min_val = min(data)
        max_val = max(data)

        # Percentiles
        sorted_data = sorted(data)
        p25 = sorted_data[len(sorted_data) // 4]
        p75 = sorted_data[3 * len(sorted_data) // 4]

        # Count in target range
        in_range = sum(1 for d in data if target_min * 60 <= d <= target_max * 60)
        pct_in_range = (in_range / len(data)) * 100

        print(f"{name}")
        print("-" * 80)
        print(f"  Target range:    {target_min}-{target_max} minutes")
        print(f"  Mean:            {format_time(mean_val)} ({mean_val/60:.1f} min)")
        print(f"  Median:          {format_time(median_val)} ({median_val/60:.1f} min)")
        print(f"  Std Dev:         {format_time(stdev_val)} ({stdev_val/60:.1f} min)")
        print(f"  Range:           {format_time(min_val)} - {format_time(max_val)}")
        print(f"  25th percentile: {format_time(p25)} ({p25/60:.1f} min)")
        print(f"  75th percentile: {format_time(p75)} ({p75/60:.1f} min)")
        print(f"  In target range: {in_range}/{len(data)} ({pct_in_range:.1f}%)")
        print()

        # Check for normality (rough test - if mean ≈ median, likely normal)
        mean_median_diff = abs(mean_val - median_val)
        if mean_median_diff < stdev_val * 0.2:
            print(f"  ✓ Distribution appears roughly normal (mean ≈ median)")
        else:
            print(f"  ⚠️ Distribution may be skewed (mean - median = {format_time(mean_median_diff)})")
        print()

    print("=" * 80)
    print("SET 1 DURATION STATISTICS")
    print("=" * 80)
    calc_stats(set1_durations, "Set 1", 60, 75)

    print("=" * 80)
    print("SET 2 DURATION STATISTICS")
    print("=" * 80)
    calc_stats(set2_durations, "Set 2", 65, 80)

    print("=" * 80)
    print("ENCORE DURATION STATISTICS")
    print("=" * 80)
    calc_stats(encore_durations, "Encore", 12, 20)

    print("=" * 80)
    print("TOTAL SHOW DURATION STATISTICS")
    print("=" * 80)
    calc_stats(total_durations, "Total Show", 137, 175)

    # Song count statistics
    print("=" * 80)
    print("SONG COUNT STATISTICS")
    print("=" * 80)
    print(f"Set 1 songs:  Mean={statistics.mean(set1_counts):.1f}, Range={min(set1_counts)}-{max(set1_counts)}")
    print(f"Set 2 songs:  Mean={statistics.mean(set2_counts):.1f}, Range={min(set2_counts)}-{max(set2_counts)}")
    print()

    # Report outliers
    if outliers:
        print("=" * 80)
        print(f"OUTLIERS DETECTED (>90 minutes)")
        print("=" * 80)
        print(f"Found {len(outliers)} outliers:\n")
        for outlier in outliers[:10]:  # Show first 10
            print(f"  {outlier['set']}: {format_time(outlier['duration'])} "
                  f"({outlier['songs']} songs, seed={outlier['seed']})")
        if len(outliers) > 10:
            print(f"  ... and {len(outliers) - 10} more")
        print()
        print(f"Outlier rate: {len(outliers)}/{len(set1_durations) * 2} sets ({len(outliers)/(len(set1_durations)*2)*100:.1f}%)")
        print()
    else:
        print("=" * 80)
        print("✓ NO OUTLIERS DETECTED (all sets <90 minutes)")
        print("=" * 80)
        print()

    # Create histogram (text-based)
    print("=" * 80)
    print("SET 1 DURATION HISTOGRAM")
    print("=" * 80)
    print_histogram(set1_durations, "Set 1", 60, 75)

    print("=" * 80)
    print("SET 2 DURATION HISTOGRAM")
    print("=" * 80)
    print_histogram(set2_durations, "Set 2", 65, 80)

    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


def print_histogram(data: List[float], name: str, target_min: int, target_max: int):
    """Print a text-based histogram."""
    if not data:
        return

    # Create bins (5-minute intervals)
    min_val = int(min(data) / 60 / 5) * 5
    max_val = int(max(data) / 60 / 5) * 5 + 5

    bins = list(range(min_val, max_val + 5, 5))
    counts = [0] * (len(bins) - 1)

    for duration in data:
        minutes = duration / 60
        for i in range(len(bins) - 1):
            if bins[i] <= minutes < bins[i + 1]:
                counts[i] += 1
                break

    max_count = max(counts) if counts else 1
    scale = 50 / max_count  # Scale to 50 chars max

    print(f"\n{name} durations (5-minute bins):\n")
    for i in range(len(counts)):
        bin_label = f"{bins[i]:3d}-{bins[i+1]:3d}m"
        bar_length = int(counts[i] * scale)
        bar = "█" * bar_length

        # Mark target range
        in_target = target_min <= bins[i] < target_max or target_min < bins[i+1] <= target_max
        marker = " ✓" if in_target else ""

        print(f"  {bin_label}: {bar} {counts[i]}{marker}")
    print()


if __name__ == "__main__":
    analyze_distribution()
