# Cross-Set Dependencies

**Implemented**: 2025-10-23  
**Status**: ✅ Complete and tested

---

## Overview

Cross-set dependencies enforce rules where a song in one set (typically encore) requires another song to have been played in a previous set. This prevents "orphan" songs like reprises from appearing without their parent song.

## The Problem

The generator could select **Tweezer Reprise** for the encore even when **Tweezer** was never played in Set 1 or Set 2. This violated Phish's performance patterns where:

- **Tweezer Reprise in encore**: 62.6% of appearances
- **When in encore**: ~95% of the time, Tweezer was played earlier in the show
- **When in Set 2**: Can appear as long as Tweezer is in Set 1 or Set 2

## The Solution

### Cross-Set Dependency Rules

Created a new constraint type that spans across sets:

```python
@dataclass
class CrossSetDependency:
    dependent_song: str        # "Tweezer Reprise"
    required_song: str         # "Tweezer"
    target_set: str           # "encore"
    required_sets: list[str]  # ["set1", "set2", "set3"]
    confidence: float         # 0.95
    description: str
```

### Current Rules

**File**: `data/analytics/features/cross_set_dependencies.parquet`

1. **Tweezer Reprise (encore) → Tweezer (Set 1/2/3)**
   - Confidence: 95%
   - Prevents encore Tweezer Reprise without Tweezer in earlier sets
   - Does NOT apply to Set 2 (different pattern)

### Implementation

**FeatureStore** (`feature_store.py`):
- Loads cross-set dependencies from parquet file
- `violates_cross_set_dependency()` checks if a candidate violates rules

**Generator** (`core.py`):
- Tracks songs in completed sets (`completed_sets_songs`)
- Passes this context to `_compose_segment()` and `_select_with_duration_budget()`
- Filters out candidates that would violate cross-set dependencies
- Only applied when ML features are enabled

### Code Flow

```python
# When generating encore:
completed_sets_songs = {
    "set1": ["Tweezer", "Stash", ...],
    "set2": ["YEM", "Harry Hood", ...]
}

# For each candidate song:
if feature_store.violates_cross_set_dependency(
    candidate_song="Tweezer Reprise",
    target_set="encore",
    previous_sets_songs=completed_sets_songs
):
    # Skip this candidate - Tweezer not found in set1/set2/set3
    continue
```

## Testing

### Unit Tests
✅ `scripts/test_cross_set_dependency_unit.py` - 5 test cases, all passing:
1. Tweezer Reprise (encore) WITHOUT Tweezer → VIOLATION ✓
2. Tweezer Reprise (encore) WITH Tweezer in Set 1 → OK ✓
3. Tweezer Reprise (encore) WITH Tweezer in Set 2 → OK ✓
4. Tweezer Reprise in Set 2 (not encore) → OK ✓
5. Regular song with no dependencies → OK ✓

### Integration Tests
✅ `scripts/test_tweezer_reprise_rule.py` - Generates setlists and verifies rule enforcement
- All 28 existing tests still pass (no regressions)
- Generator correctly filters Tweezer Reprise when Tweezer missing

## Future Enhancements

Potential additional rules to discover:

1. **Mike's Song → Weekapaug** (cross-set)
   - When Weekapaug is in encore, Mike's should be in earlier set
   - Currently handled by same-set ordering; cross-set pattern less common

2. **Colonel Forbin's → Mockingbird** (cross-set)
   - Similar reprise/continuation pattern
   - Usually same set, but could have cross-set rule

3. **Swept Away → Steep** (cross-set)
   - Very high lift (473×) in same set
   - Cross-set version extremely rare

## Configuration

Cross-set dependencies are automatically loaded when:
- `use_ml_features=True` (default)
- Feature file exists: `data/analytics/features/cross_set_dependencies.parquet`

To add new rules, update the parquet file or regenerate using similar logic to `scripts/test_cross_set_dependency_unit.py`.

## Performance

- Feature loading: ~150ms (includes all ML features)
- Per-song check: <1ms (dictionary lookup)
- No measurable impact on generation speed

---

## Key Files

- **Feature Data**: `data/analytics/features/cross_set_dependencies.parquet`
- **FeatureStore**: `src/phish_setlist_maker/analysis/feature_store.py`
- **Generator**: `src/phish_setlist_maker/generator/core.py`
- **Unit Tests**: `scripts/test_cross_set_dependency_unit.py`
- **Integration Tests**: `scripts/test_tweezer_reprise_rule.py`
