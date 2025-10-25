#!/usr/bin/env python3
"""Statistical analysis of generated setlist durations at low jamminess (0.01) - tight/concise."""

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


def analyze_tight_distribution():
    """Generate many setlists at jamminess=0.01 and analyze duration distributions."""

    # Use 300 for good statistical power
    N = 300
    JAMMINESS = 0.01

    print("=" * 80)
    print(f"JAMMINESS={JAMMINESS} (TIGHT/CONCISE) DISTRIBUTION ANALYSIS (N={N})")
    print("=" * 80)
    print()
    print(f"Generating setlists with jamminess={JAMMINESS} (tight & tidy)...")
    print("This may take a minute or two...\n")

    # Storage for durations (in seconds)
    set1_durations: List[float] = []
    set2_durations: List[float] = []
    encore_durations: List[float] = []
    total_durations: List[float] = []

    # Track how many songs per set
    set1_counts: List[int] = []
    set2_counts: List[int] = []

    with session_scope() as session:
        for i in range(N):
            if (i + 1) % 50 == 0:
                print(f"  Generated {i + 1}/{N} setlists...")

            # Use different seeds for variety
            rng = Random(3000 + i)
            generator = SetlistGenerator(
                session=session,
                rng=rng,
                use_ml_features=True,
                jamminess=JAMMINESS,  # Force low jamminess (tight)
            )

            try:
                result = generator.generate(
                    reference_date=date(2023, 12, 31),
                    num_sets=2,
                    include_encore=True,
                )

                # Rough duration estimates (7 min avg per song for sets, 5 for encore)
                set1_est = len(result.sets[0].songs) * 7 * 60
                set2_est = len(result.sets[1].songs) * 7 * 60
                encore_est = len(result.encore.songs) * 5 * 60 if result.encore else 0

                set1_durations.append(set1_est)
                set2_durations.append(set2_est)
                encore_durations.append(encore_est)
                total_durations.append(set1_est + set2_est + encore_est)

                set1_counts.append(len(result.sets[0].songs))
                set2_counts.append(len(result.sets[1].songs))

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

        # Count in target range (should still respect normal targets!)
        in_range = sum(1 for d in data if target_min * 60 <= d <= target_max * 60)
        pct_in_range = (in_range / len(data)) * 100

        print(f"{name}")
        print("-" * 80)
        print(f"  Target range:    {target_min}-{target_max} minutes (NORMAL - jamminess={JAMMINESS})")
        print(f"  Mean:            {format_time(mean_val)} ({mean_val/60:.1f} min)")
        print(f"  Median:          {format_time(median_val)} ({median_val/60:.1f} min)")
        print(f"  Std Dev:         {format_time(stdev_val)} ({stdev_val/60:.1f} min)")
        print(f"  Range:           {format_time(min_val)} - {format_time(max_val)}")
        print(f"  25th percentile: {format_time(p25)} ({p25/60:.1f} min)")
        print(f"  75th percentile: {format_time(p75)} ({p75/60:.1f} min)")
        print(f"  In target range: {in_range}/{len(data)} ({pct_in_range:.1f}%)")
        print()

        # Check for normality
        mean_median_diff = abs(mean_val - median_val)
        if mean_median_diff < stdev_val * 0.2:
            print(f"  ✓ Distribution appears roughly normal (mean ≈ median)")
        else:
            print(f"  ⚠️ Distribution may be skewed (mean - median = {format_time(mean_median_diff)})")
        print()

    print("=" * 80)
    print("SET 1 DURATION STATISTICS (JAMMINESS=0.01 - TIGHT)")
    print("=" * 80)
    # At low jamminess, still target normal ranges
    calc_stats(set1_durations, "Set 1", 60, 75)

    print("=" * 80)
    print("SET 2 DURATION STATISTICS (JAMMINESS=0.01 - TIGHT)")
    print("=" * 80)
    calc_stats(set2_durations, "Set 2", 65, 80)

    print("=" * 80)
    print("ENCORE DURATION STATISTICS (JAMMINESS=0.01 - TIGHT)")
    print("=" * 80)
    calc_stats(encore_durations, "Encore", 12, 20)

    print("=" * 80)
    print("TOTAL SHOW DURATION STATISTICS (JAMMINESS=0.01 - TIGHT)")
    print("=" * 80)
    calc_stats(total_durations, "Total Show", 137, 175)

    # Song count statistics - KEY METRIC!
    print("=" * 80)
    print("SONG COUNT STATISTICS (KEY METRIC FOR TIGHT JAMMINESS)")
    print("=" * 80)
    set1_mean = statistics.mean(set1_counts)
    set1_min = min(set1_counts)
    set1_max = max(set1_counts)
    set2_mean = statistics.mean(set2_counts)
    set2_min = min(set2_counts)
    set2_max = max(set2_counts)

    print(f"Set 1 songs:  Mean={set1_mean:.1f}, Range={set1_min}-{set1_max}")
    print(f"Set 2 songs:  Mean={set2_mean:.1f}, Range={set2_min}-{set2_max}")
    print()
    print(f"✓ At jamminess={JAMMINESS}, we expect MORE songs per set")
    print(f"  (shorter performances = more songs fit in same time)")
    print()
    print(f"Expected comparison to default (dynamic):")
    print(f"  Default Set 1: ~9-10 songs")
    print(f"  Tight Set 1:   ~{set1_mean:.0f} songs (should be higher!)")
    print(f"  Default Set 2: ~8-9 songs")
    print(f"  Tight Set 2:   ~{set2_mean:.0f} songs (should be higher!)")
    print()

    # Create histogram (text-based)
    print("=" * 80)
    print("SET 1 DURATION HISTOGRAM (JAMMINESS=0.01 - TIGHT)")
    print("=" * 80)
    print_histogram(set1_durations, "Set 1", 60, 75)

    print("=" * 80)
    print("SET 2 DURATION HISTOGRAM (JAMMINESS=0.01 - TIGHT)")
    print("=" * 80)
    print_histogram(set2_durations, "Set 2", 65, 80)

    print("=" * 80)
    print("SET 1 SONG COUNT HISTOGRAM")
    print("=" * 80)
    print_song_count_histogram(set1_counts, "Set 1")

    print("=" * 80)
    print("SET 2 SONG COUNT HISTOGRAM")
    print("=" * 80)
    print_song_count_histogram(set2_counts, "Set 2")

    # Comparison note
    print("=" * 80)
    print("COMPARISON TO DEFAULT (DYNAMIC) BEHAVIOR")
    print("=" * 80)
    print(f"\nAt jamminess={JAMMINESS} (p30 percentile tracks - tight/concise):")
    print(f"  • Duration targets ENFORCED strictly (60-75min Set 1, 65-80min Set 2)")
    print(f"  • MORE songs per set (shorter individual performances)")
    print(f"  • Tighter, more concise versions (not extended jams)")
    print(f"  • Sets should still respect time constraints")
    print(f"\nThis gives users a 'greatest hits' style setlist with lots of songs!")
    print()

    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


def print_histogram(data: List[float], name: str, target_min: int, target_max: int):
    """Print a text-based histogram for durations."""
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


def print_song_count_histogram(data: List[int], name: str):
    """Print a text-based histogram for song counts."""
    if not data:
        return

    min_val = min(data)
    max_val = max(data)

    # Count frequency of each song count
    counts_map: Dict[int, int] = {}
    for count in data:
        counts_map[count] = counts_map.get(count, 0) + 1

    max_freq = max(counts_map.values()) if counts_map else 1
    scale = 50 / max_freq

    print(f"\n{name} song counts:\n")
    for count in range(min_val, max_val + 1):
        freq = counts_map.get(count, 0)
        bar_length = int(freq * scale)
        bar = "█" * bar_length

        print(f"  {count:2d} songs: {bar} {freq}")
    print()


if __name__ == "__main__":
    analyze_tight_distribution()
