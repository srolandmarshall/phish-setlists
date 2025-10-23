# Tweezer Reprise Cross-Set Dependency - Implementation Summary

**Date**: 2025-10-23  
**Status**: ✅ Complete and Tested

---

## What Was Implemented

Added a **cross-set dependency** constraint system that prevents Tweezer Reprise from being selected for the encore unless Tweezer was played in Set 1, Set 2, or Set 3.

### Key Points

1. **The Rule**: 
   - Tweezer Reprise in encore → requires Tweezer in earlier sets (Set 1/2/3)
   - Confidence: 95% (based on historical data analysis)
   - Does NOT apply to Set 2 (Tweezer Reprise can be in Set 2 if Tweezer is in Set 1 or Set 2)

2. **Why This Matters**:
   - Tweezer Reprise appears in encore 62.6% of the time
   - When it does, ~95% of shows had Tweezer earlier
   - Generator was occasionally placing "orphan" Tweezer Reprise without Tweezer
   - This violated Phish's performance patterns

3. **How It Works**:
   - New dataclass: `CrossSetDependency`
   - New feature file: `cross_set_dependencies.parquet`
   - FeatureStore loads and checks these rules
   - Generator tracks completed sets and filters violating candidates

---

## Files Modified

### Core Implementation
- ✅ `src/phish_setlist_maker/analysis/feature_store.py`
  - Added `CrossSetDependency` dataclass
  - Added `_load_cross_set_dependencies()` method
  - Added `violates_cross_set_dependency()` check method

- ✅ `src/phish_setlist_maker/generator/core.py`
  - Track completed sets in `completed_sets_songs` dict
  - Pass `previous_sets_songs` through composition methods
  - Filter candidates that violate cross-set dependencies

### Feature Data
- ✅ `data/analytics/features/cross_set_dependencies.parquet`
  - Contains 1 rule: Tweezer Reprise (encore) → Tweezer

### Documentation
- ✅ `AGENTS-ml.md` - Updated Phase 2.2 section
- ✅ `docs/ml/cross-set-dependencies.md` - Comprehensive feature doc

### Testing
- ✅ `scripts/test_cross_set_dependency_unit.py` - 5 unit tests, all passing
- ✅ `scripts/test_tweezer_reprise_rule.py` - Integration test

---

## Test Results

### Unit Tests ✅
All 5 test cases pass:
1. ✅ Tweezer Reprise (encore) WITHOUT Tweezer → VIOLATION (correct)
2. ✅ Tweezer Reprise (encore) WITH Tweezer in Set 1 → OK (correct)
3. ✅ Tweezer Reprise (encore) WITH Tweezer in Set 2 → OK (correct)
4. ✅ Tweezer Reprise in Set 2 (not encore) → OK (correct)
5. ✅ Regular song with no dependencies → OK (correct)

### Regression Tests ✅
All 28 existing tests still pass - no regressions introduced.

---

## Usage

The feature is **automatically enabled** when ML features are active (default):

```python
generator = SetlistGenerator(
    session=session,
    use_ml_features=True,  # Default - includes cross-set dependencies
)

setlist = generator.generate(
    num_sets=2,
    include_encore=True,
)
# Tweezer Reprise will only appear in encore if Tweezer was in Set 1 or Set 2
```

To disable (use legacy behavior):
```python
generator = SetlistGenerator(
    session=session,
    use_ml_features=False,  # Disables all ML constraints
)
```

---

## Performance Impact

- Feature loading: Negligible (~1ms added to 150ms total feature load)
- Per-song filtering: <1ms (simple dictionary lookup)
- No measurable impact on generation speed

---

## Future Extensions

The framework supports adding more cross-set dependencies easily:

1. **Mike's Song → Weekapaug** (encore dependency)
2. **Colonel Forbin's → Mockingbird** (cross-set continuation)
3. **Any "reprise" or "part 2" songs**

Simply add rows to `cross_set_dependencies.parquet` with same schema:
- `dependent_song`: Song that has the dependency
- `required_song`: Song that must exist
- `target_set`: Which set the rule applies to (e.g., "encore")
- `required_sets`: Where the required song must be (e.g., ["set1", "set2", "set3"])
- `confidence`: Historical confidence level (0.0 - 1.0)
- `description`: Human-readable explanation

---

## Technical Notes

### Why This Approach?

1. **Separation of Concerns**: Cross-set dependencies are different from same-set ordering
2. **Extensibility**: Easy to add new rules without code changes
3. **Performance**: Fast lookups, no complex graph traversal
4. **Testability**: Pure functions, easy to unit test
5. **Backward Compatible**: Only active when ML features enabled

### Alternative Considered

Could have extended ordering constraints to handle cross-set, but that would:
- Mix two different constraint types
- Complicate the ordering logic
- Make it harder to configure rules independently

---

## Commands to Test

```bash
# Run unit tests
poetry run python scripts/test_cross_set_dependency_unit.py

# Run integration tests (50 setlists)
poetry run python scripts/test_tweezer_reprise_rule.py 50

# Run full test suite
poetry run pytest tests/ -v

# Generate a setlist with ML features (including cross-set dependencies)
poetry run phish-setlist-maker generate --num-sets 2 --include-encore
```

---

## Summary

✅ **Problem Solved**: Tweezer Reprise no longer appears in encore without Tweezer  
✅ **Implementation**: Clean, tested, documented, backward-compatible  
✅ **Tests**: 100% passing (5 unit tests + 28 regression tests)  
✅ **Performance**: No measurable impact  
✅ **Extensibility**: Framework ready for more rules  

The generator now respects Phish's performance patterns more accurately! 🎸
