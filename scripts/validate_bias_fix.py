#!/usr/bin/env python
"""Validate that the frequency cap and segue penalty fix reduce song bias."""

from collections import Counter
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from phish_setlist_maker.generator import SetlistGenerator
from phish_setlist_maker.analysis.feature_store import FeatureStore
from phish_setlist_maker.database import SessionLocal


def generate_multiple_setlists(num_setlists=50, seed_offset=0):
    """Generate multiple setlists and track which songs appear."""
    db = SessionLocal()
    try:
        feature_store = FeatureStore(features_dir=Path("data/analytics/features"))
        feature_store.load()

        song_counts = Counter()
        segue_trigger_songs = {
            "Mike's Song", "Runaway Jim", "Colonel Forbin's Ascent",
            "The Man Who Stepped Into Yesterday", "Dinner and a Movie",
            "I Am Hydrogen", "The Horse", "The Oh Kee Pa Ceremony"
        }
        segue_appearances = Counter()

        for i in range(num_setlists):
            generator = SetlistGenerator(
                db_session=db,
                feature_store=feature_store,
                use_ml_features=True,
                ml_placement_weight=0.3,
                ml_transition_bonus=0.1,
            )

            result = generator.generate(
                num_sets=2,
                include_encore=True,
                seed=1000 + seed_offset + i,
            )

            # Count all songs
            for segment in result.sets:
                for song in segment.songs:
                    song_counts[song] += 1
                    if song in segue_trigger_songs:
                        segue_appearances[song] += 1

            if result.encore:
                for song in result.encore.songs:
                    song_counts[song] += 1
                    if song in segue_trigger_songs:
                        segue_appearances[song] += 1

        return song_counts, segue_appearances, num_setlists

    finally:
        db.close()


def print_results(song_counts, segue_appearances, num_setlists):
    """Print analysis of song distribution."""
    print(f"\n{'='*70}")
    print(f"ANALYSIS: {num_setlists} Generated Setlists")
    print(f"{'='*70}\n")

    # Top 10 most common songs
    print("Top 10 Most Common Songs:")
    print(f"{'Song':<40} {'Appearances':<12} {'%'}")
    print("-" * 70)
    for song, count in song_counts.most_common(10):
        pct = (count / num_setlists) * 100
        print(f"{song:<40} {count:<12} {pct:>5.1f}%")

    # Segue trigger analysis
    print(f"\n\nSegue Trigger Songs:")
    print(f"{'Song':<40} {'Appearances':<12} {'%'}")
    print("-" * 70)
    for song, count in segue_appearances.most_common():
        pct = (count / num_setlists) * 100
        print(f"{song:<40} {count:<12} {pct:>5.1f}%")

    # Summary statistics
    total_segue_appearances = sum(segue_appearances.values())
    total_songs = sum(song_counts.values())
    segue_pct = (total_segue_appearances / total_songs) * 100

    print(f"\n\nSummary:")
    print(f"  Total songs selected: {total_songs}")
    print(f"  Total segue trigger appearances: {total_segue_appearances}")
    print(f"  Segue triggers as % of all songs: {segue_pct:.1f}%")
    print(f"  Average songs per setlist: {total_songs / num_setlists:.1f}")

    # Expected vs Actual for Mike's Song
    mikes_appearances = segue_appearances.get("Mike's Song", 0)
    mikes_pct = (mikes_appearances / num_setlists) * 100
    print(f"\n  Mike's Song appearances: {mikes_appearances}/{num_setlists} ({mikes_pct:.1f}%)")
    print(f"  Expected with fix: <30%")

    if mikes_pct < 30:
        print(f"  ✅ PASS: Mike's Song within expected range")
    else:
        print(f"  ❌ FAIL: Mike's Song still over-represented")


if __name__ == "__main__":
    print("\nGenerating setlists to validate bias fix...")
    print("This may take a minute...\n")

    song_counts, segue_appearances, num_setlists = generate_multiple_setlists(
        num_setlists=50,
        seed_offset=2000
    )

    print_results(song_counts, segue_appearances, num_setlists)
    print("\n" + "="*70 + "\n")
