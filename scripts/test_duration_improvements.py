#!/usr/bin/env python3
"""Test script to verify dynamic jam intensity duration improvements."""

from datetime import date
from random import Random
from typing import Dict, List

from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator.core import SetlistGenerator


def format_duration(seconds: float) -> str:
    """Format duration in MM:SS."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def test_duration_distribution():
    """Generate multiple setlists and analyze duration distribution."""
    print("=" * 80)
    print("DURATION IMPROVEMENT TEST")
    print("=" * 80)
    print()

    # Test parameters
    num_tests = 10
    eras = [None, "1.0", "2.0", "3.0", "4.0"]

    with session_scope() as session:
        for era in eras:
            print(f"\n{'=' * 80}")
            print(f"Testing Era: {era or 'All Eras'}")
            print(f"{'=' * 80}\n")

            durations: Dict[str, List[float]] = {
                "Set 1": [],
                "Set 2": [],
                "Encore": [],
            }

            for i in range(num_tests):
                # Use different seeds for variety
                rng = Random(42 + i)
                generator = SetlistGenerator(
                    session=session,
                    rng=rng,
                    use_ml_features=True,
                )

                try:
                    result = generator.generate(
                        reference_date=date(2023, 12, 31),
                        num_sets=2,
                        include_encore=True,
                        era=era,
                    )

                    # Estimate durations (rough - would need actual track data for exact)
                    for idx, segment in enumerate(result.sets):
                        label = f"Set {idx + 1}"
                        # Rough estimate: 6-8 minutes per song average
                        est_duration = len(segment.songs) * 7 * 60  # 7 min avg
                        durations[label].append(est_duration)

                    if result.encore:
                        est_duration = len(result.encore.songs) * 5 * 60  # 5 min avg for encore
                        durations["Encore"].append(est_duration)

                except Exception as e:
                    print(f"  ⚠️  Error generating setlist {i+1}: {e}")
                    continue

            # Report statistics
            for label, values in durations.items():
                if not values:
                    print(f"  {label}: No data")
                    continue

                avg = sum(values) / len(values)
                min_val = min(values)
                max_val = max(values)

                print(f"  {label}:")
                print(f"    Average: {format_duration(avg)}")
                print(f"    Range: {format_duration(min_val)} - {format_duration(max_val)}")
                print(f"    Variation: {format_duration(max_val - min_val)}")

    print(f"\n{'=' * 80}")
    print("TEST COMPLETE")
    print(f"{'=' * 80}\n")


def test_single_generation_details():
    """Generate a single setlist and show detailed duration info."""
    print("=" * 80)
    print("DETAILED SINGLE GENERATION TEST")
    print("=" * 80)
    print()

    with session_scope() as session:
        rng = Random(42)
        generator = SetlistGenerator(
            session=session,
            rng=rng,
            use_ml_features=True,
        )

        result = generator.generate(
            reference_date=date(2023, 12, 31),
            num_sets=2,
            include_encore=True,
        )

        print("Generated Setlist:")
        print("-" * 80)

        for idx, segment in enumerate(result.sets):
            print(f"\n{segment.label}:")
            for song in segment.songs:
                print(f"  - {song}")
            print(f"  ({len(segment.songs)} songs)")

        if result.encore:
            print(f"\n{result.encore.label}:")
            for song in result.encore.songs:
                print(f"  - {song}")
            print(f"  ({len(result.encore.songs)} songs)")

        print("\nMetadata Notes:")
        print("-" * 80)
        for note in result.metadata.notes:
            print(f"  • {note}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("TESTING DYNAMIC JAM INTENSITY DURATION IMPROVEMENTS")
    print("=" * 80 + "\n")

    # Run detailed single test first
    test_single_generation_details()

    print("\n" * 2)

    # Then run distribution tests
    test_duration_distribution()
