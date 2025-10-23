#!/usr/bin/env python3
"""
Unit test for cross-set dependency checking.
Tests the FeatureStore.violates_cross_set_dependency() method directly.
"""

from pathlib import Path

from phish_setlist_maker.analysis.feature_store import FeatureStore


def test_cross_set_dependency_logic():
    """Test the cross-set dependency checking logic."""
    
    print("🧪 Testing Cross-Set Dependency Logic\n")
    
    # Load feature store
    features_dir = Path("data/analytics/features")
    feature_store = FeatureStore(features_dir)
    feature_store.load()
    
    print("✓ Feature store loaded")
    print(f"  Cross-set dependencies: {len(feature_store._cross_set_dependencies) if feature_store._cross_set_dependencies else 0}")
    
    if feature_store._cross_set_dependencies:
        print("\n  Rules loaded:")
        for dep in feature_store._cross_set_dependencies:
            print(f"    • {dep.dependent_song} ({dep.target_set}) → requires {dep.required_song} in {dep.required_sets}")
    
    # Test Case 1: Tweezer Reprise in encore WITHOUT Tweezer in earlier sets (should violate)
    print("\n" + "=" * 70)
    print("TEST CASE 1: Tweezer Reprise in encore WITHOUT Tweezer")
    print("=" * 70)
    
    previous_sets = {
        "set1": ["Chalk Dust Torture", "Stash", "David Bowie"],
        "set2": ["Mike's Song", "Weekapaug Groove", "Harry Hood"],
    }
    
    violates = feature_store.violates_cross_set_dependency(
        candidate_song="Tweezer Reprise",
        target_set="encore",
        previous_sets_songs=previous_sets
    )
    
    print(f"Previous sets: {previous_sets}")
    print(f"Candidate: Tweezer Reprise (encore)")
    print(f"Result: {'VIOLATION ✗' if violates else 'OK ✓'}")
    
    if violates:
        print("✅ PASS: Correctly identified violation (no Tweezer in earlier sets)")
    else:
        print("❌ FAIL: Should have detected violation!")
    
    # Test Case 2: Tweezer Reprise in encore WITH Tweezer in Set 1 (should be OK)
    print("\n" + "=" * 70)
    print("TEST CASE 2: Tweezer Reprise in encore WITH Tweezer in Set 1")
    print("=" * 70)
    
    previous_sets = {
        "set1": ["Chalk Dust Torture", "Tweezer", "Stash", "David Bowie"],
        "set2": ["Mike's Song", "Weekapaug Groove", "Harry Hood"],
    }
    
    violates = feature_store.violates_cross_set_dependency(
        candidate_song="Tweezer Reprise",
        target_set="encore",
        previous_sets_songs=previous_sets
    )
    
    print(f"Previous sets: {previous_sets}")
    print(f"Candidate: Tweezer Reprise (encore)")
    print(f"Result: {'VIOLATION ✗' if violates else 'OK ✓'}")
    
    if not violates:
        print("✅ PASS: Correctly allowed (Tweezer in Set 1)")
    else:
        print("❌ FAIL: Should NOT have detected violation!")
    
    # Test Case 3: Tweezer Reprise in encore WITH Tweezer in Set 2 (should be OK)
    print("\n" + "=" * 70)
    print("TEST CASE 3: Tweezer Reprise in encore WITH Tweezer in Set 2")
    print("=" * 70)
    
    previous_sets = {
        "set1": ["Chalk Dust Torture", "Stash", "David Bowie"],
        "set2": ["Tweezer", "Mike's Song", "Weekapaug Groove", "Harry Hood"],
    }
    
    violates = feature_store.violates_cross_set_dependency(
        candidate_song="Tweezer Reprise",
        target_set="encore",
        previous_sets_songs=previous_sets
    )
    
    print(f"Previous sets: {previous_sets}")
    print(f"Candidate: Tweezer Reprise (encore)")
    print(f"Result: {'VIOLATION ✗' if violates else 'OK ✓'}")
    
    if not violates:
        print("✅ PASS: Correctly allowed (Tweezer in Set 2)")
    else:
        print("❌ FAIL: Should NOT have detected violation!")
    
    # Test Case 4: Tweezer Reprise in Set 2 WITH Tweezer in Set 1 (should be OK - different rule)
    print("\n" + "=" * 70)
    print("TEST CASE 4: Tweezer Reprise in Set 2 (not encore)")
    print("=" * 70)
    
    previous_sets = {
        "set1": ["Chalk Dust Torture", "Tweezer", "Stash", "David Bowie"],
    }
    
    violates = feature_store.violates_cross_set_dependency(
        candidate_song="Tweezer Reprise",
        target_set="set2",  # Not encore
        previous_sets_songs=previous_sets
    )
    
    print(f"Previous sets: {previous_sets}")
    print(f"Candidate: Tweezer Reprise (set2)")
    print(f"Result: {'VIOLATION ✗' if violates else 'OK ✓'}")
    print(f"Note: Rule only applies to encore, not set2")
    
    if not violates:
        print("✅ PASS: Correctly allowed (rule doesn't apply to Set 2)")
    else:
        print("❌ FAIL: Should NOT have detected violation for Set 2!")
    
    # Test Case 5: Non-Tweezer song (should be OK)
    print("\n" + "=" * 70)
    print("TEST CASE 5: Regular song with no dependencies")
    print("=" * 70)
    
    previous_sets = {
        "set1": ["Chalk Dust Torture", "Stash", "David Bowie"],
        "set2": ["Mike's Song", "Weekapaug Groove", "Harry Hood"],
    }
    
    violates = feature_store.violates_cross_set_dependency(
        candidate_song="Possum",
        target_set="encore",
        previous_sets_songs=previous_sets
    )
    
    print(f"Previous sets: {previous_sets}")
    print(f"Candidate: Possum (encore)")
    print(f"Result: {'VIOLATION ✗' if violates else 'OK ✓'}")
    
    if not violates:
        print("✅ PASS: Correctly allowed (no dependency rule for Possum)")
    else:
        print("❌ FAIL: Should NOT have detected violation!")
    
    print("\n" + "=" * 70)
    print("✅ All unit tests completed!")
    print("=" * 70)


if __name__ == "__main__":
    test_cross_set_dependency_logic()
