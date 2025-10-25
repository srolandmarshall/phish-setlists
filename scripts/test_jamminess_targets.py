#!/usr/bin/env python3
"""Quick test to show duration target relaxation at high jamminess."""

from datetime import date
from random import Random

from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator.core import SetlistGenerator


def test_jamminess_targets():
    """Generate a few setlists at different jamminess levels to show target relaxation."""

    print("=" * 80)
    print("DURATION TARGET BEHAVIOR AT DIFFERENT JAMMINESS LEVELS")
    print("=" * 80)
    print()

    levels = [
        (None, "Dynamic (default)", "60-75min Set1, 65-80min Set2"),
        (0.5, "Balanced (0.5)", "60-75min Set1, 65-80min Set2"),
        (0.8, "Pretty Jammy (0.8)", "75-100min Set1, 81-100min Set2 (+25%)"),
        (0.99, "FULL SEND (0.99)", "90-120min Set1, 97-120min Set2 (+50%)"),
    ]

    with session_scope() as session:
        for jamminess, label, expected in levels:
            print(f"\n{'=' * 80}")
            print(f"{label}")
            print(f"Expected: {expected}")
            print(f"{'=' * 80}\n")

            # Generate 3 examples
            for i in range(3):
                rng = Random(1000 + i)
                generator = SetlistGenerator(
                    session=session,
                    rng=rng,
                    use_ml_features=True,
                    jamminess=jamminess,
                )

                result = generator.generate(
                    reference_date=date(2023, 12, 31),
                    num_sets=2,
                    include_encore=True,
                )

                set1_songs = len(result.sets[0].songs)
                set2_songs = len(result.sets[1].songs)

                # Rough estimate
                set1_est_min = set1_songs * 7
                set2_est_min = set2_songs * 7

                # Check for capping notes
                capped = [note for note in result.metadata.notes if "Capped" in note]

                print(f"  Example {i+1}:")
                print(f"    Set 1: {set1_songs} songs (~{set1_est_min}min)")
                print(f"    Set 2: {set2_songs} songs (~{set2_est_min}min)")
                if capped:
                    for note in capped:
                        print(f"    Note: {note}")
                print()

    print("=" * 80)
    print("KEY INSIGHT")
    print("=" * 80)
    print()
    print("At jamminess >= 0.9:")
    print("  • Duration targets are RELAXED by 50%")
    print("  • Set 1: 60-75min → 90-112min cap")
    print("  • Set 2: 65-80min → 97-120min cap")
    print("  • User explicitly wants extended jams!")
    print()
    print("At jamminess >= 0.75:")
    print("  • Duration targets are RELAXED by 25%")
    print("  • Set 1: 60-75min → 75-94min cap")
    print("  • Set 2: 65-80min → 81-100min cap")
    print()


if __name__ == "__main__":
    test_jamminess_targets()
