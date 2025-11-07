# Ordering Rules Investigation Report
**Date**: 2025-11-07  
**Status**: Analysis Complete - Issues Identified

---

## Executive Summary

The ordering/pairing system has **3 separate mechanisms** with different behaviors:
1. **Ordering Constraints** (686 rules) - ✅ WORKING but only prevents violations
2. **Directional Transitions** (181 rules, 5 mandatory) - ⚠️ NOT FORCING adjacent placement
3. **Post-generation Rules** (1 rule) - ✅ WORKING but reactive/limited

**Core Problem**: System prevents Mike's after Weekapaug, but doesn't guarantee Weekapaug follows Mike's.

---

## Current Implementation

### 1. Ordering Constraints (`ordering_constraints.parquet`)
- **Count**: 686 rules (672 mandatory)
- **Logic**: `song_a` must come BEFORE `song_b` in same set
- **Loaded in**: `feature_store._load_ordering_constraints()`
- **Checked in**: `core.py` lines 690-698
- **Behavior**: **NEGATIVE ONLY** - Prevents violations, doesn't force pairing

**Example**: Mike's Song → Weekapaug Groove
```python
# Data shows:
- set1: 160 co-occurrences, 99.4% Mike's before Weekapaug
- set2: 351 co-occurrences, 99.4% Mike's before Weekapaug

# What it does:
✅ Blocks adding Mike's if Weekapaug already in set
❌ Does NOT force Weekapaug when Mike's is added
```

**Verification**:
```python
fs.get_songs_that_must_follow("Mike's Song")
# Returns: {'Weekapaug Groove', 'I Am Hydrogen', ...} (17 songs)

fs.violates_ordering_constraint(["Weekapaug Groove"], "Mike's Song")
# Returns: True (CORRECT - violation detected)
```

### 2. Directional Transitions (`directional_transitions.parquet`)
- **Count**: 181 rules (5 mandatory)
- **Logic**: Adjacent transitions with forward confidence
- **Loaded in**: `feature_store._load_directional_rules()`
- **Used in**: `core.py` line 970 via `get_mandatory_next_songs()`
- **Behavior**: **WEIGHT BOOST ONLY** (3× multiplier) - Doesn't guarantee

**Mandatory Rules**:
1. I Am Hydrogen → Weekapaug Groove (96% confidence) ×2 entries
2. The Horse → Silent in the Morning (91-94% confidence) ×3 entries

**Key Finding**: Mike's Song → Weekapaug is **NOT** in directional_transitions
- Only exists in ordering_constraints
- `get_mandatory_next_songs("Mike's Song")` returns `set()` (empty)

**What it does**:
```python
# Lines 968-975 in core.py:
if previous_song:
    mandatory_next = self._feature_store.get_mandatory_next_songs(previous_song)
    if mandatory_next:
        for candidate in pool:
            if candidate in mandatory_next:
                weight *= 3.0  # Just boost weight
```

✅ Increases probability of selection (3×)  
❌ Does NOT guarantee adjacency  
❌ Mike's → Weekapaug not even in this table

### 3. Post-Generation Rules (`rules.py`)
- **Count**: 1 rule (Mike's Song → Weekapaug Groove)
- **Logic**: After generation, if Mike's exists without Weekapaug, insert it
- **When**: After all sets composed (`apply_rules()` at line 339)
- **Behavior**: **REACTIVE** - Fixes missing pairs post-hoc

**Code** (rules.py lines 150-156):
```python
SongDependencyRule(
    trigger="Mike's Song",
    requirements=("Weekapaug Groove",),
    insert_candidates=("set2", "set1"),
    allow_insert_in_trigger_segment=True,
    insert_adjacent=True,
)
```

**What it does**:
✅ Ensures Weekapaug added if Mike's appears  
✅ Attempts adjacent placement  
❌ Only works if insertion succeeds (duration/space available)  
❌ Only 1 rule defined (doesn't scale to 36+ famous sequences)

---

## Gap Analysis

### What's Missing

1. **Proactive Pairing** during generation
   - Current: Reactive fixes after generation
   - Needed: Force pairs during selection

2. **Mike's → Weekapaug NOT in Directional Transitions**
   - Famous sequence (511× occurrences, 99.4% ordering)
   - Only in ordering_constraints (prevents wrong order)
   - Not in directional_transitions (would boost adjacency)
   - Only in post-gen rules (reactive fix)

3. **Limited Mandatory Directional Rules**
   - Only 5 mandatory rules (Hydrogen→Weekapaug, The Horse→Silent)
   - Famous sequences CSV shows 36 sequences (>95% confidence)
   - 31 missing from enforcement

4. **No Guarantee of Adjacency**
   - Ordering constraints: Just prevents wrong order
   - Directional rules: Just boosts weight (3×)
   - Post-gen rules: Only 1 rule, may fail if no space

### Data Discrepancy

**Famous Sequences CSV** (docs/figures/famous_song_sequences.csv):
- 36 sequences with >95% consistency
- Top 5:
  1. Mike's Song → Weekapaug Groove (511×, 99.4%)
  2. I Am Hydrogen → Weekapaug Groove (339×, 97.9%)
  3. Mike's Song → I Am Hydrogen (334×, 98.6%)
  4. The Oh Kee Pa Ceremony → Suzy Greenberg (133×, 98.4%)
  5. Colonel Forbin's Ascent → Fly Famous Mockingbird (124×, 94.9%)

**Directional Transitions Parquet** (mandatory only):
- 5 entries total
- Only has: Hydrogen→Weekapaug, The Horse→Silent

**Conclusion**: Data pipeline incomplete or different thresholds applied

---

## Why It's Not Working

### Scenario: Mike's Song selected during generation

**Step 1**: Mike's Song added to set  
**Step 2**: Next song selection runs  
- Pool has Weekapaug + 100 other songs
- Ordering constraint: ✅ Allows Weekapaug (Mike's before Weekapaug = OK)
- Directional transition: ❌ No boost (Mike's not in mandatory_next)
- Weight: Same as other candidates
- Result: Weekapaug has ~1% chance (1/100 songs)

**Step 3**: Set continues, other songs added  
**Step 4**: Set ends  
**Step 5**: Post-generation rules run  
- Detects: Mike's Song without Weekapaug
- Action: Tries to insert Weekapaug after Mike's
- Success?: Only if duration budget allows

**Failure Modes**:
1. Weekapaug not selected randomly (99% chance)
2. Duration budget full, can't insert
3. Other songs fill set before Weekapaug considered

---

## Test Case

```python
# Generate 100 setlists with ML features enabled
# Count: How many times does Mike's Song appear?
# Count: How many times is it followed by Weekapaug?
# Expected: ~99% (historical rate)
# Actual: Unknown (needs testing)
```

**Expected Issue**: Mike's Song appears without Weekapaug frequently

---

## Comparison: What Works vs. What Doesn't

### ✅ What Works
- **Ordering prevention**: Can't add Mike's after Weekapaug (enforced)
- **Cross-set dependencies**: Tweezer Reprise requires Tweezer (enforced)
- **Post-gen safety net**: Mike's → Weekapaug insertion (when space allows)

### ❌ What Doesn't Work
- **Proactive pairing**: No guarantee Weekapaug follows Mike's
- **Adjacent placement**: 3× weight boost not enough (1→3 out of 100)
- **Scale**: Only 1 post-gen rule vs. 36 famous sequences
- **Data coverage**: 31 famous sequences missing from directional rules

---

## Recommendations

### Option 1: Fix Data Pipeline (Root Cause)
**Issue**: directional_transitions.parquet missing 31 famous sequences

**Action**: Update `scripts/build_features.py` to include all 36 famous sequences as mandatory directional rules

**Pros**: 
- Fixes at data layer
- Scales to all 36 sequences
- Consistent with existing architecture

**Cons**:
- Still uses 3× weight boost (not guarantee)
- May need higher boost multiplier

### Option 2: Enhance Directional Rule Enforcement
**Issue**: 3× weight boost too weak (3/100 vs. 99/100)

**Action**: Change from weight boost to **immediate selection**
```python
if previous_song:
    mandatory_next = self._feature_store.get_mandatory_next_songs(previous_song)
    if mandatory_next:
        # Check if any mandatory songs available in pool
        available_mandatory = [s for s in mandatory_next if s in pool]
        if available_mandatory:
            # Force selection from mandatory songs
            return random.choice(available_mandatory)
```

**Pros**:
- Guarantees adjacency
- No random chance
- Matches historical behavior (99.4%)

**Cons**:
- More rigid (less variety)
- May conflict with duration budgets

### Option 3: Expand Post-Generation Rules
**Issue**: Only 1 SongDependencyRule defined

**Action**: Add all 36 famous sequences to `SONG_DEPENDENCY_RULES`

**Pros**:
- Safety net for all sequences
- Keeps generation flexible

**Cons**:
- Reactive (not proactive)
- May fail if no space
- Doesn't enforce adjacency reliably

### Option 4: Hybrid Approach (RECOMMENDED)
1. **Fix data pipeline**: Add 36 famous sequences to directional_transitions
2. **Strengthen enforcement**: Change mandatory directional rules from weight boost to forced selection
3. **Keep safety net**: Maintain post-gen rules as fallback

**Benefits**:
- Proactive (forces during generation)
- Reactive (fixes if missed)
- Scales to all 36 sequences
- Matches historical behavior

---

## Next Steps

1. **Validate Issue**: Generate 100 setlists, measure Mike's → Weekapaug adjacency rate
2. **Root Cause Analysis**: Check `scripts/build_features.py` for why directional_transitions is incomplete
3. **Fix Data Pipeline**: Ensure all 36 famous sequences become mandatory directional rules
4. **Enhance Enforcement**: Change from weight boost to forced selection for mandatory sequences
5. **Test**: Verify 99%+ adjacency rate for top 5 famous sequences
6. **Scale**: Apply to all 36 sequences

---

## Files to Review/Modify

### Core Implementation
- `src/phish_setlist_maker/generator/core.py:968-975` - Directional rule application
- `src/phish_setlist_maker/analysis/feature_store.py:159-201` - Directional rules loading
- `src/phish_setlist_maker/generator/rules.py:147-157` - Post-gen dependency rules

### Data Pipeline
- `scripts/build_features.py` - Feature table generation
- `docs/figures/famous_song_sequences.csv` - Source of truth (36 sequences)
- `data/analytics/features/directional_transitions.parquet` - Incomplete (5 vs. 36)

### Analysis
- `data/analytics/features/ordering_constraints.parquet` - Working (686 rules)
- `data/analytics/features/directional_transitions.parquet` - Incomplete (181 rules, 5 mandatory)

---

## Summary

**Problem**: Song pairing is preventative, not proactive  
**Root Cause**: Incomplete data + weak enforcement (weight boost vs. forced selection)  
**Impact**: Famous sequences like Mike's → Weekapaug likely don't appear adjacently at historical rates  
**Solution**: Fix data pipeline + strengthen directional rule enforcement to forced selection  
**Priority**: High (affects core quality of generated setlists)
