#!/usr/bin/env python3
"""Comprehensive jamminess analysis with matplotlib charts."""

from datetime import date
from random import Random
from typing import Dict, List
import statistics

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator.core import SetlistGenerator


def generate_setlists(jamminess: float | None, n: int, seed_offset: int, label: str) -> Dict:
    """Generate N setlists at a specific jamminess level and collect stats."""

    set1_durations: List[float] = []
    set2_durations: List[float] = []
    set1_counts: List[int] = []
    set2_counts: List[int] = []

    print(f"Generating {n} setlists for {label}...")

    with session_scope() as session:
        for i in range(n):
            if (i + 1) % 25 == 0:
                print(f"  Progress: {i + 1}/{n}")

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

                set1_durations.append(set1_est / 60)  # Convert to minutes
                set2_durations.append(set2_est / 60)
                set1_counts.append(len(result.sets[0].songs))
                set2_counts.append(len(result.sets[1].songs))

            except Exception:
                continue

    print(f"  ✓ Completed {len(set1_durations)} setlists\n")

    return {
        'set1_durations': set1_durations,
        'set2_durations': set2_durations,
        'set1_counts': set1_counts,
        'set2_counts': set2_counts,
    }


def create_charts():
    """Generate comprehensive charts analyzing jamminess levels."""

    N = 150  # Sample size per level (reduced for faster generation)

    print("=" * 80)
    print("PHISH SETLIST MAKER - JAMMINESS ANALYSIS WITH CHARTS")
    print("=" * 80)
    print(f"\nSample size: N={N} per jamminess level ({N * 3} total setlists)")
    print("Generating matplotlib charts...\n")

    # Define test levels
    levels = [
        (0.01, "Tight (0.01)", 1000),
        (None, "Dynamic (default)", 2000),
        (0.99, "Full Send (0.99)", 3000),
    ]

    results = {}

    # Generate setlists for each level
    for jamminess, label, seed_offset in levels:
        results[label] = generate_setlists(jamminess, N, seed_offset, label)

    # Set up matplotlib style
    plt.style.use('seaborn-v0_8-darkgrid')
    colors = ['#FF6B6B', '#4ECDC4', '#FFE66D']

    # Create figure with subplots
    fig = plt.figure(figsize=(16, 12))

    # 1. Set 1 Duration Distributions
    ax1 = plt.subplot(3, 3, 1)
    for idx, (jamminess, label, _) in enumerate(levels):
        data = results[label]['set1_durations']
        ax1.hist(data, bins=15, alpha=0.6, label=label, color=colors[idx])
    ax1.axvspan(60, 75, alpha=0.1, color='green', label='Target Range')
    ax1.set_xlabel('Duration (minutes)')
    ax1.set_ylabel('Frequency')
    ax1.set_title('Set 1 Duration Distribution')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Set 2 Duration Distributions
    ax2 = plt.subplot(3, 3, 2)
    for idx, (jamminess, label, _) in enumerate(levels):
        data = results[label]['set2_durations']
        ax2.hist(data, bins=15, alpha=0.6, label=label, color=colors[idx])
    ax2.axvspan(65, 80, alpha=0.1, color='green', label='Target Range')
    ax2.set_xlabel('Duration (minutes)')
    ax2.set_ylabel('Frequency')
    ax2.set_title('Set 2 Duration Distribution')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # 3. Song Count Comparison
    ax3 = plt.subplot(3, 3, 3)
    labels_short = ['Tight', 'Dynamic', 'Full Send']
    set1_means = [statistics.mean(results[label]['set1_counts']) for _, label, _ in levels]
    set2_means = [statistics.mean(results[label]['set2_counts']) for _, label, _ in levels]

    x = range(len(labels_short))
    width = 0.35
    ax3.bar([i - width/2 for i in x], set1_means, width, label='Set 1', color='#FF6B6B', alpha=0.8)
    ax3.bar([i + width/2 for i in x], set2_means, width, label='Set 2', color='#4ECDC4', alpha=0.8)
    ax3.set_ylabel('Average Songs per Set')
    ax3.set_title('Average Song Count by Jamminess')
    ax3.set_xticks(x)
    ax3.set_xticklabels(labels_short)
    ax3.legend()
    ax3.grid(True, axis='y', alpha=0.3)

    # 4. Set 1 Box Plot
    ax4 = plt.subplot(3, 3, 4)
    set1_data = [results[label]['set1_durations'] for _, label, _ in levels]
    bp1 = ax4.boxplot(set1_data, labels=labels_short, patch_artist=True)
    for patch, color in zip(bp1['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax4.axhspan(60, 75, alpha=0.1, color='green')
    ax4.set_ylabel('Duration (minutes)')
    ax4.set_title('Set 1 Duration Box Plot')
    ax4.grid(True, axis='y', alpha=0.3)

    # 5. Set 2 Box Plot
    ax5 = plt.subplot(3, 3, 5)
    set2_data = [results[label]['set2_durations'] for _, label, _ in levels]
    bp2 = ax5.boxplot(set2_data, labels=labels_short, patch_artist=True)
    for patch, color in zip(bp2['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax5.axhspan(65, 80, alpha=0.1, color='green')
    ax5.set_ylabel('Duration (minutes)')
    ax5.set_title('Set 2 Duration Box Plot')
    ax5.grid(True, axis='y', alpha=0.3)

    # 6. Duration Means Comparison
    ax6 = plt.subplot(3, 3, 6)
    set1_dur_means = [statistics.mean(results[label]['set1_durations']) for _, label, _ in levels]
    set2_dur_means = [statistics.mean(results[label]['set2_durations']) for _, label, _ in levels]

    ax6.bar([i - width/2 for i in x], set1_dur_means, width, label='Set 1', color='#FF6B6B', alpha=0.8)
    ax6.bar([i + width/2 for i in x], set2_dur_means, width, label='Set 2', color='#4ECDC4', alpha=0.8)
    ax6.axhline(y=67.5, color='green', linestyle='--', alpha=0.5, label='Set 1 Target Mid')
    ax6.axhline(y=72.5, color='blue', linestyle='--', alpha=0.5, label='Set 2 Target Mid')
    ax6.set_ylabel('Average Duration (minutes)')
    ax6.set_title('Average Set Duration by Jamminess')
    ax6.set_xticks(x)
    ax6.set_xticklabels(labels_short)
    ax6.legend()
    ax6.grid(True, axis='y', alpha=0.3)

    # 7. Set 1 Song Count Distribution
    ax7 = plt.subplot(3, 3, 7)
    for idx, (jamminess, label, _) in enumerate(levels):
        data = results[label]['set1_counts']
        ax7.hist(data, bins=range(min(data), max(data) + 2), alpha=0.6, label=label, color=colors[idx])
    ax7.set_xlabel('Number of Songs')
    ax7.set_ylabel('Frequency')
    ax7.set_title('Set 1 Song Count Distribution')
    ax7.legend()
    ax7.grid(True, alpha=0.3)

    # 8. Set 2 Song Count Distribution
    ax8 = plt.subplot(3, 3, 8)
    for idx, (jamminess, label, _) in enumerate(levels):
        data = results[label]['set2_counts']
        ax8.hist(data, bins=range(min(data), max(data) + 2), alpha=0.6, label=label, color=colors[idx])
    ax8.set_xlabel('Number of Songs')
    ax8.set_ylabel('Frequency')
    ax8.set_title('Set 2 Song Count Distribution')
    ax8.legend()
    ax8.grid(True, alpha=0.3)

    # 9. Target Compliance
    ax9 = plt.subplot(3, 3, 9)
    set1_compliance = []
    set2_compliance = []

    for jamminess, label, _ in levels:
        data = results[label]
        set1_in = sum(1 for d in data['set1_durations'] if 60 <= d <= 75)
        set2_in = sum(1 for d in data['set2_durations'] if 65 <= d <= 80)
        set1_compliance.append((set1_in / len(data['set1_durations'])) * 100)
        set2_compliance.append((set2_in / len(data['set2_durations'])) * 100)

    ax9.bar([i - width/2 for i in x], set1_compliance, width, label='Set 1', color='#FF6B6B', alpha=0.8)
    ax9.bar([i + width/2 for i in x], set2_compliance, width, label='Set 2', color='#4ECDC4', alpha=0.8)
    ax9.axhline(y=80, color='green', linestyle='--', alpha=0.5, label='80% Target')
    ax9.set_ylabel('Compliance (%)')
    ax9.set_title('Target Range Compliance')
    ax9.set_xticks(x)
    ax9.set_xticklabels(labels_short)
    ax9.set_ylim(0, 105)
    ax9.legend()
    ax9.grid(True, axis='y', alpha=0.3)

    # Add values on bars
    for i, (v1, v2) in enumerate(zip(set1_compliance, set2_compliance)):
        ax9.text(i - width/2, v1 + 2, f'{v1:.1f}%', ha='center', va='bottom', fontsize=9)
        ax9.text(i + width/2, v2 + 2, f'{v2:.1f}%', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()

    # Save figure
    output_path = 'jamminess_analysis.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n✓ Chart saved to: {output_path}")

    # Print summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print()

    for jamminess, label, _ in levels:
        data = results[label]
        print(f"{label}:")
        print(f"  Set 1: {statistics.mean(data['set1_counts']):.1f} songs, "
              f"{statistics.mean(data['set1_durations']):.1f} min avg")
        print(f"  Set 2: {statistics.mean(data['set2_counts']):.1f} songs, "
              f"{statistics.mean(data['set2_durations']):.1f} min avg")

        set1_in = sum(1 for d in data['set1_durations'] if 60 <= d <= 75)
        set2_in = sum(1 for d in data['set2_durations'] if 65 <= d <= 80)
        print(f"  Compliance: Set 1={set1_in}/{N} ({set1_in/N*100:.1f}%), "
              f"Set 2={set2_in}/{N} ({set2_in/N*100:.1f}%)")
        print()

    print("=" * 80)
    print(f"Analysis complete! View the chart: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    create_charts()
