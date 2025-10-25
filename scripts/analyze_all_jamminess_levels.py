#!/usr/bin/env python3
"""Comprehensive statistical analysis across all jamminess levels."""

from datetime import date
from random import Random
from typing import Dict, List, Optional, Tuple
import statistics

from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator.core import SetlistGenerator


def format_time(seconds: float) -> str:
    """Format seconds as MM:SS."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def generate_setlists(jamminess: Optional[float], n: int, seed_offset: int, label: str) -> Dict:
    """Generate N setlists at a specific jamminess level and collect stats."""

    set1_durations: List[float] = []
    set2_durations: List[float] = []
    encore_durations: List[float] = []
    set1_counts: List[int] = []
    set2_counts: List[int] = []
    extreme_outliers = 0  # Sets >120 minutes

    with session_scope() as session:
        for i in range(n):
            # Show progress
            if (i + 1) % 10 == 0 or i + 1 == n:
                print_progress_bar(i + 1, n, label)

            rng = Random(seed_offset + i)
            generator = SetlistGenerator(
                session=session,
                rng=rng,
                use_ml_features=True,
                jamminess=jamminess,
            )

            try:
                result = generator.generate(
                    reference_date=date(2023, 12, 31),
                    num_sets=2,
                    include_encore=True,
                )

                # Rough duration estimates
                set1_est = len(result.sets[0].songs) * 7 * 60
                set2_est = len(result.sets[1].songs) * 7 * 60
                encore_est = len(result.encore.songs) * 5 * 60 if result.encore else 0

                set1_durations.append(set1_est)
                set2_durations.append(set2_est)
                encore_durations.append(encore_est)
                set1_counts.append(len(result.sets[0].songs))
                set2_counts.append(len(result.sets[1].songs))

                # Count extreme outliers
                if set1_est > 120 * 60 or set2_est > 120 * 60:
                    extreme_outliers += 1

            except Exception:
                continue

    return {
        'set1_durations': set1_durations,
        'set2_durations': set2_durations,
        'encore_durations': encore_durations,
        'set1_counts': set1_counts,
        'set2_counts': set2_counts,
        'extreme_outliers': extreme_outliers,
    }


def calc_summary_stats(durations: List[float]) -> Dict:
    """Calculate summary statistics for a list of durations."""
    if not durations:
        return {}

    return {
        'mean': statistics.mean(durations),
        'median': statistics.median(durations),
        'stdev': statistics.stdev(durations) if len(durations) > 1 else 0,
        'min': min(durations),
        'max': max(durations),
        'p25': sorted(durations)[len(durations) // 4],
        'p75': sorted(durations)[3 * len(durations) // 4],
    }


def print_histogram(data: List[float], bin_size: int = 5):
    """Print a compact histogram."""
    if not data:
        return

    min_val = int(min(data) / 60 / bin_size) * bin_size
    max_val = int(max(data) / 60 / bin_size) * bin_size + bin_size

    bins = list(range(min_val, max_val + bin_size, bin_size))
    counts = [0] * (len(bins) - 1)

    for duration in data:
        minutes = duration / 60
        for i in range(len(bins) - 1):
            if bins[i] <= minutes < bins[i + 1]:
                counts[i] += 1
                break

    max_count = max(counts) if counts else 1
    scale = 40 / max_count

    for i in range(len(counts)):
        if counts[i] > 0:  # Only show non-zero bins
            bin_label = f"{bins[i]:3d}-{bins[i+1]:3d}m"
            bar_length = int(counts[i] * scale)
            bar = "█" * bar_length
            print(f"  {bin_label}: {bar} {counts[i]}")


def print_song_count_histogram(data: List[int]):
    """Print a compact song count histogram."""
    if not data:
        return

    counts_map: Dict[int, int] = {}
    for count in data:
        counts_map[count] = counts_map.get(count, 0) + 1

    max_freq = max(counts_map.values()) if counts_map else 1
    scale = 40 / max_freq

    for count in sorted(counts_map.keys()):
        freq = counts_map[count]
        bar_length = int(freq * scale)
        bar = "█" * bar_length
        print(f"  {count:2d} songs: {bar} {freq}")


def print_banner():
    """Print a fun ASCII banner."""
    print()
    print("╔═══════════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                               ║")
    print("║        🎸  PHISH SETLIST MAKER - JAMMINESS ANALYSIS  🎸                      ║")
    print("║                                                                               ║")
    print("║     Testing the full spectrum: Tight → Dynamic → FULL SEND                   ║")
    print("║                                                                               ║")
    print("╚═══════════════════════════════════════════════════════════════════════════════╝")
    print()


def print_progress_bar(current: int, total: int, label: str):
    """Print a fun progress bar."""
    pct = int((current / total) * 100)
    filled = int((current / total) * 40)
    bar = "█" * filled + "░" * (40 - filled)
    print(f"\r  {label}: [{bar}] {pct}% ({current}/{total})", end="", flush=True)
    if current == total:
        print()  # New line when complete


def analyze_all_jamminess_levels():
    """Comprehensive analysis across all jamminess levels."""

    N = 300  # Sample size per level

    print_banner()
    print("  Sample size: N=300 per jamminess level (900 total setlists)")
    print("  Estimated time: 2-3 minutes")
    print("  Grab some coffee... ☕")
    print()

    # Define test levels
    levels = [
        (0.01, "Tight & Tidy (0.01)", 1000),
        (None, "Dynamic (default)", 2000),
        (0.99, "Full Send (0.99)", 3000),
    ]

    results = {}

    # Generate setlists for each level
    for jamminess, label, seed_offset in levels:
        results[label] = generate_setlists(jamminess, N, seed_offset, label)
        print()

    # Print comparative summary
    print("=" * 80)
    print("COMPARATIVE SUMMARY TABLE")
    print("=" * 80)
    print()

    # Set 1 comparison
    print("SET 1 STATISTICS")
    print("-" * 80)
    print(f"{'Jamminess':<25} {'Mean':<10} {'Median':<10} {'StdDev':<10} {'Range':<15} {'Songs':<10}")
    print("-" * 80)

    for jamminess, label, _ in levels:
        data = results[label]
        stats = calc_summary_stats(data['set1_durations'])
        song_mean = statistics.mean(data['set1_counts'])

        print(f"{label:<25} "
              f"{stats['mean']/60:<10.1f} "
              f"{stats['median']/60:<10.1f} "
              f"{stats['stdev']/60:<10.1f} "
              f"{stats['min']/60:.0f}-{stats['max']/60:.0f}min      "
              f"{song_mean:<10.1f}")

    print()

    # Set 2 comparison
    print("SET 2 STATISTICS")
    print("-" * 80)
    print(f"{'Jamminess':<25} {'Mean':<10} {'Median':<10} {'StdDev':<10} {'Range':<15} {'Songs':<10}")
    print("-" * 80)

    for jamminess, label, _ in levels:
        data = results[label]
        stats = calc_summary_stats(data['set2_durations'])
        song_mean = statistics.mean(data['set2_counts'])

        print(f"{label:<25} "
              f"{stats['mean']/60:<10.1f} "
              f"{stats['median']/60:<10.1f} "
              f"{stats['stdev']/60:<10.1f} "
              f"{stats['min']/60:.0f}-{stats['max']/60:.0f}min      "
              f"{song_mean:<10.1f}")

    print()

    # Target compliance
    print("=" * 80)
    print("TARGET RANGE COMPLIANCE")
    print("=" * 80)
    print()

    for jamminess, label, _ in levels:
        data = results[label]

        # Set 1: 60-75 minutes (normal target)
        set1_in_range = sum(1 for d in data['set1_durations'] if 60*60 <= d <= 75*60)
        set1_pct = (set1_in_range / len(data['set1_durations'])) * 100 if data['set1_durations'] else 0

        # Set 2: 65-80 minutes (normal target)
        set2_in_range = sum(1 for d in data['set2_durations'] if 65*60 <= d <= 80*60)
        set2_pct = (set2_in_range / len(data['set2_durations'])) * 100 if data['set2_durations'] else 0

        print(f"{label}:")
        print(f"  Set 1 in target (60-75min): {set1_in_range}/{len(data['set1_durations'])} ({set1_pct:.1f}%)")
        print(f"  Set 2 in target (65-80min): {set2_in_range}/{len(data['set2_durations'])} ({set2_pct:.1f}%)")

        if data['extreme_outliers'] > 0:
            print(f"  ⚠️  Extreme outliers (>120min): {data['extreme_outliers']}")
        else:
            print(f"  ✓ No extreme outliers")
        print()

    # Detailed breakdowns
    for jamminess, label, _ in levels:
        data = results[label]

        print("=" * 80)
        print(f"{label.upper()} - DETAILED BREAKDOWN")
        print("=" * 80)
        print()

        # Set 1 duration histogram
        print(f"Set 1 Duration Distribution:")
        print_histogram(data['set1_durations'])
        print()

        # Set 1 song count histogram
        print(f"Set 1 Song Count Distribution:")
        print_song_count_histogram(data['set1_counts'])
        print()

        # Set 2 duration histogram
        print(f"Set 2 Duration Distribution:")
        print_histogram(data['set2_durations'])
        print()

        # Set 2 song count histogram
        print(f"Set 2 Song Count Distribution:")
        print_song_count_histogram(data['set2_counts'])
        print()

    # Key insights with fun visualizations
    print("=" * 80)
    print("🎯 KEY INSIGHTS & VISUAL COMPARISON")
    print("=" * 80)
    print()

    tight_data = results["Tight & Tidy (0.01)"]
    dynamic_data = results["Dynamic (default)"]
    full_data = results["Full Send (0.99)"]

    tight_song_avg = statistics.mean(tight_data['set1_counts'] + tight_data['set2_counts'])
    dynamic_song_avg = statistics.mean(dynamic_data['set1_counts'] + dynamic_data['set2_counts'])
    full_song_avg = statistics.mean(full_data['set1_counts'] + full_data['set2_counts'])

    tight_dur_avg = statistics.mean([d/60 for d in tight_data['set1_durations'] + tight_data['set2_durations']])
    dynamic_dur_avg = statistics.mean([d/60 for d in dynamic_data['set1_durations'] + dynamic_data['set2_durations']])
    full_dur_avg = statistics.mean([d/60 for d in full_data['set1_durations'] + full_data['set2_durations']])

    # Visual comparison chart for songs
    print("🎵 AVERAGE SONGS PER SET")
    print()
    max_songs = max(tight_song_avg, dynamic_song_avg, full_song_avg)
    scale = 50 / max_songs

    tight_bar = "█" * int(tight_song_avg * scale)
    dynamic_bar = "█" * int(dynamic_song_avg * scale)
    full_bar = "█" * int(full_song_avg * scale)

    print(f"  🎯 Tight (0.01):    {tight_bar} {tight_song_avg:.1f} songs")
    print(f"  🎸 Dynamic (auto):  {dynamic_bar} {dynamic_song_avg:.1f} songs")
    print(f"  🚀 Full Send (0.99): {full_bar} {full_song_avg:.1f} songs")
    print()

    # Visual comparison chart for duration
    print("⏱️  AVERAGE SET DURATION")
    print()
    max_dur = max(tight_dur_avg, dynamic_dur_avg, full_dur_avg)
    scale = 50 / max_dur

    tight_dur_bar = "█" * int(tight_dur_avg * scale)
    dynamic_dur_bar = "█" * int(dynamic_dur_avg * scale)
    full_dur_bar = "█" * int(full_dur_avg * scale)

    print(f"  🎯 Tight (0.01):    {tight_dur_bar} {tight_dur_avg:.1f} min")
    print(f"  🎸 Dynamic (auto):  {dynamic_dur_bar} {dynamic_dur_avg:.1f} min")
    print(f"  🚀 Full Send (0.99): {full_dur_bar} {full_dur_avg:.1f} min")
    print()

    # Summary boxes
    print("┌─────────────────────────────────────────────────────────────────────────────┐")
    print("│ BEHAVIOR SUMMARY                                                            │")
    print("├─────────────────────────────────────────────────────────────────────────────┤")
    print(f"│ 🎯 Tight (0.01):    {tight_song_avg:>4.0f} songs, ~{tight_dur_avg:>4.0f}min  │  Greatest hits style!        │")
    print(f"│ 🎸 Dynamic (auto):  {dynamic_song_avg:>4.0f} songs, ~{dynamic_dur_avg:>4.0f}min  │  Balanced & adaptive         │")
    print(f"│ 🚀 Full Send (0.99): {full_song_avg:>4.0f} songs, ~{full_dur_avg:>4.0f}min  │  Extended jam heaven!        │")
    print("└─────────────────────────────────────────────────────────────────────────────┘")
    print()

    # Normality check
    print("=" * 80)
    print("DISTRIBUTION NORMALITY CHECK")
    print("=" * 80)
    print()

    for jamminess, label, _ in levels:
        data = results[label]
        set1_stats = calc_summary_stats(data['set1_durations'])
        set2_stats = calc_summary_stats(data['set2_durations'])

        set1_diff = abs(set1_stats['mean'] - set1_stats['median']) / 60
        set2_diff = abs(set2_stats['mean'] - set2_stats['median']) / 60

        print(f"{label}:")
        print(f"  Set 1: mean-median diff = {set1_diff:.1f} min", end="")
        if set1_diff < 2:
            print(" ✓ (normal)")
        else:
            print(" ⚠️  (skewed)")

        print(f"  Set 2: mean-median diff = {set2_diff:.1f} min", end="")
        if set2_diff < 2:
            print(" ✓ (normal)")
        else:
            print(" ⚠️  (skewed)")
        print()

    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print()
    print(f"Analyzed {N * 3} total setlists across 3 jamminess levels.")
    print("Results show duration distributions and song counts for each setting.")
    print()


if __name__ == "__main__":
    analyze_all_jamminess_levels()
