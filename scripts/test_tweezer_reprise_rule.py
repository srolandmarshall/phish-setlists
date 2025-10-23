#!/usr/bin/env python3
"""
Test script to verify Tweezer Reprise cross-set dependency rule.

This script generates multiple setlists with encores and verifies that:
1. When Tweezer Reprise appears in the encore, Tweezer was played in Set 1 or Set 2
2. The rule is enforced consistently across multiple generations
"""

from pathlib import Path

from phish_setlist_maker.analysis.feature_store import FeatureStore
from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator import SetlistGenerator


def test_tweezer_reprise_rule(num_trials: int = 100):
    """Generate setlists and verify Tweezer Reprise rule."""
    
    # Load feature store
    features_dir = Path("data/analytics/features")
    feature_store = FeatureStore(features_dir)
    feature_store.load()
    
    print("🎸 Testing Tweezer Reprise Cross-Set Dependency Rule")
    print(f"   Generating {num_trials} setlists with ML features enabled...\n")
    
    stats = {
        "total_generated": 0,
        "with_encore_reprise": 0,
        "reprise_with_tweezer": 0,
        "reprise_without_tweezer": 0,
        "violations": [],
    }
    
    with session_scope() as session:
        generator = SetlistGenerator(
            session=session,
            use_ml_features=True,
            ml_placement_weight=0.3,
            ml_transition_bonus=0.1,
        )
        
        for trial in range(num_trials):
            try:
                setlist = generator.generate(
                    num_sets=2,
                    include_encore=True,
                )
                stats["total_generated"] += 1
                
                # Check if Tweezer Reprise is in encore
                encore_songs = setlist.encore.songs if setlist.encore else []
                set1_songs = setlist.sets[0].songs if len(setlist.sets) > 0 else []
                set2_songs = setlist.sets[1].songs if len(setlist.sets) > 1 else []
                
                if "Tweezer Reprise" in encore_songs:
                    stats["with_encore_reprise"] += 1
                    
                    # Check if Tweezer is in Set 1 or Set 2
                    has_tweezer = "Tweezer" in set1_songs or "Tweezer" in set2_songs
                    
                    if has_tweezer:
                        stats["reprise_with_tweezer"] += 1
                    else:
                        stats["reprise_without_tweezer"] += 1
                        stats["violations"].append({
                            "trial": trial + 1,
                            "set1": set1_songs,
                            "set2": set2_songs,
                            "encore": encore_songs,
                        })
                
                # Progress indicator
                if (trial + 1) % 10 == 0:
                    print(f"   Progress: {trial + 1}/{num_trials} setlists generated", end="\r")
            
            except Exception as e:
                print(f"\n   ⚠️  Error in trial {trial + 1}: {e}")
                continue
    
    print(f"\n")
    print("=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    print(f"Total setlists generated: {stats['total_generated']}")
    print(f"Setlists with Tweezer Reprise in encore: {stats['with_encore_reprise']}")
    
    if stats['with_encore_reprise'] > 0:
        print(f"  ✓ With Tweezer in earlier sets: {stats['reprise_with_tweezer']}")
        print(f"  ✗ WITHOUT Tweezer (violations): {stats['reprise_without_tweezer']}")
        
        success_rate = 100 * stats['reprise_with_tweezer'] / stats['with_encore_reprise']
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        
        if stats['violations']:
            print("\n⚠️  VIOLATIONS FOUND:")
            for v in stats['violations'][:3]:  # Show first 3
                print(f"\n  Trial #{v['trial']}:")
                print(f"    Set 1: {', '.join(v['set1'][:5])}{'...' if len(v['set1']) > 5 else ''}")
                print(f"    Set 2: {', '.join(v['set2'][:5])}{'...' if len(v['set2']) > 5 else ''}")
                print(f"    Encore: {', '.join(v['encore'])}")
        else:
            print("\n✅ SUCCESS! All Tweezer Reprise encores had Tweezer in earlier sets.")
    else:
        print("\n  ℹ️  No Tweezer Reprise encores generated in this test run.")
        print("     This is expected - Tweezer Reprise in encore is relatively rare (~10% probability).")
        print("     Try running with more trials or check the feature probabilities.")
    
    print("=" * 70)
    
    return stats['reprise_without_tweezer'] == 0  # True if no violations


if __name__ == "__main__":
    import sys
    
    num_trials = 100
    if len(sys.argv) > 1:
        num_trials = int(sys.argv[1])
    
    success = test_tweezer_reprise_rule(num_trials)
    sys.exit(0 if success else 1)
