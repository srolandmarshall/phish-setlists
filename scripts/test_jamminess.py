#!/usr/bin/env python3
"""Test script to verify jamminess parameter works correctly."""

from datetime import date
from random import Random

from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator.core import SetlistGenerator


def test_jamminess_levels():
    """Generate setlists with different jamminess levels to verify behavior."""
    print("=" * 80)
    print("JAMMINESS FEATURE TEST")
    print("=" * 80)
    print()

    levels = [
        (0.0, "Tight & Tidy (p30)"),
        (0.3, "Easy Does It (p50)"),
        (0.6, "Run of the Mill (p70)"),
        (0.9, "FULL SEND (p90)"),
        (None, "Dynamic (auto)"),
    ]

    with session_scope() as session:
        for jamminess, description in levels:
            print(f"\n{'=' * 80}")
            print(f"Testing Jamminess: {description}")
            print(f"{'=' * 80}\n")

            rng = Random(42)  # Same seed for consistency
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

                print("Generated Setlist:")
                print("-" * 80)

                for idx, segment in enumerate(result.sets):
                    print(f"\n{segment.label}:")
                    for song in segment.songs:
                        print(f"  - {song}")
                    print(f"  Total: {len(segment.songs)} songs")

                if result.encore:
                    print(f"\n{result.encore.label}:")
                    for song in result.encore.songs:
                        print(f"  - {song}")
                    print(f"  Total: {len(result.encore.songs)} songs")

                print("\nMetadata Notes:")
                for note in result.metadata.notes:
                    print(f"  • {note}")

            except Exception as e:
                print(f"  ⚠️  Error: {e}")

    print(f"\n{'=' * 80}")
    print("TEST COMPLETE")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    test_jamminess_levels()
