# Generation Speed Improvements Plan

## Executive Summary

The setlist generation currently takes **~27 seconds per request**, with the **set/encore generation loop consuming 17.4 seconds (64% of total time)**. This is caused by **34,500-51,750 redundant feature store lookups** in nested loops. Through strategic caching and loop consolidation, we can reduce generation time to **10-12 seconds total (70-85% improvement)**.

---

## Current Performance Baseline

From production logs (2025-11-20):

```
⏱️  Generation started
  ⏱️  DB queries (frequencies/previous) took 0.27s
  ⏱️  Segment statistics computation took 0.49s
  ⏱️  Set/encore generation loop took 17.39s ⬅️ BOTTLENECK (64%)
  ⏱️  TOTAL generator.generate() took 18.16s
⏱️  Setlist generation took 18.17s
    ⏱️  Catalog query took 0.02s
⏱️  Catalog build took 0.02s
⏱️  Track metadata fetching took 7.22s
⏱️  TOTAL generation took 27.11s
```

**Typical generation parameters:**
- 2 sets + 1 encore = 3 segments
- ~23 total songs selected (10-11 per set, 2 encore)
- Candidate pool: 100-200 songs per segment
- ML features enabled (in production requests)

---

## Root Cause Analysis

### The Problem: N+1 Feature Lookups in Nested Loops

The performance bottleneck exists in two places:

#### Location 1: Song Selection Loop
**File**: `src/phish_setlist_maker/generator/core.py`
**Method**: `_select_with_duration_budget()` (lines 730-866)
**Loop type**: While loop that runs once per song selected (~23 times)

```python
while len(selection) < desired_count:  # ~23 iterations per generation
    # Filter eligible songs
    pool = [freq for freq in frequencies
            if freq.title not in used_songs
            and self._meets_constraints(freq.title, selection, canonical_set)]

    # Evaluate ALL candidates for THIS song selection
    choice = self._weighted_pick(pool, selection, canonical_set, previous_song, rng)
    selection.append(choice)
```

**Per-iteration costs:**
- Call to `_weighted_pick()` → evaluates 100-200 candidate songs
- Each candidate gets multiple feature lookups
- Feature lookups repeated for same songs in next iteration

#### Location 2: Weight Adjustment Loops
**File**: `src/phish_setlist_maker/generator/core.py`
**Method**: `_weighted_pick()` (lines 1029-1202)
**Loop type**: 5 separate `for` loops over candidate list

```python
# Adjustment Loop #1: Frequency caps (lines 1084-1112)
for idx, (freq, weight) in enumerate(weighted_candidates):  # 100-200 iterations
    features = self._feature_store.get_song_features(freq.title)  # Lookup #1
    if features and features.total_appearances > 500:
        weighted_candidates[idx] = (freq, weight * 0.3)

# Adjustment Loop #2: Segue trigger penalty (lines 1122-1139)
for idx, (freq, weight) in enumerate(weighted_candidates):  # Same 100-200 iterations
    mandatory_segues = self._feature_store.get_mandatory_segues(freq.title)  # Lookup #2
    if mandatory_segues and ...:
        weighted_candidates[idx] = (freq, weight * factor)

# Adjustment Loop #3: ML placement (lines 1142-1150)
for idx, (freq, weight) in enumerate(weighted_candidates):  # Same 100-200 iterations
    placement_prob = self._feature_store.get_placement_probability(freq.title, target_set)  # Lookup #3
    if placement_prob:
        weighted_candidates[idx] = (freq, weight * (1 - self._ml_placement_weight) + ...)

# Adjustment Loop #4: Transition lift bonus (lines 1174-1181)
for idx, (freq, weight) in enumerate(weighted_candidates):  # Same 100-200 iterations
    transition = self._feature_store.get_transition_lift(previous_song, freq.title)  # Lookup #4
    if transition:
        weighted_candidates[idx] = (freq, weight * transition)

# Adjustment Loop #5: Mandatory sequence boost (lines 1184-1190)
for idx, (freq, weight) in enumerate(weighted_candidates):  # Same 100-200 iterations
    if freq.title in mandatory_next:  # Lookup #5
        weighted_candidates[idx] = (freq, weight * 2.0)
```

### Calculation: Total Lookups Per Generation

```
23 song selections
× 150 average candidates per selection
× 5 adjustment loops
× 2-3 feature lookups per loop iteration
= 34,500 - 51,750 total feature lookups per generation
```

While individual lookups are fast (dictionary access ~1-2μs), the cumulative cost is:
- **34,500 lookups × 2μs = 69ms just for lookups**
- Plus function call overhead: **~1-2ms per lookup**
- **Total: 34,500-51,750ms → approximately 5-10 seconds wasted on redundant operations**

Plus additional overhead from:
- Creating temporary lists/tuples in each loop iteration
- Sorting weighted candidates after each adjustment
- Debug logging for each adjustment (lines 1085-1097)

---

## Proposed Solutions

### Solution 1: Pre-Cache Features at Segment Level ⭐⭐⭐ (HIGHEST PRIORITY)

**Objective**: Reduce feature lookups from 34,500+ to ~600 by pre-computing all lookups before selection loop

**Impact**: 80-90% reduction in feature lookup overhead

#### Implementation Details

**File**: `src/phish_setlist_maker/generator/core.py`

**Method**: `_compose_segment()` (around line 446-520)

**Current code structure:**
```python
def _compose_segment(self, canonical_set, target_duration, frequencies_by_set, rng):
    # ... setup code ...
    selection = self._select_with_duration_budget(
        frequencies_by_set[canonical_set],
        target_duration,
        canonical_set,
        rng,
        segment_stats=segment_stats,
    )
    return SegmentGeneration(label=canonical_set, songs=selection)
```

**Changes needed:**

1. **Add feature cache initialization** (after line 476):
```python
def _compose_segment(self, canonical_set, target_duration, frequencies_by_set, rng):
    # ... existing setup code ...

    # NEW: Pre-cache all features before selection loop
    feature_cache = {}
    if self._use_ml_features and self._feature_store:
        # Get initial candidate pool to identify all songs we might evaluate
        initial_pool = frequencies_by_set[canonical_set]

        # Pre-compute all features for this pool
        for freq in initial_pool:
            song_title = freq.title
            if song_title not in feature_cache:
                feature_cache[song_title] = {
                    'features': self._feature_store.get_song_features(song_title),
                    'mandatory_segues': self._feature_store.get_mandatory_segues(song_title),
                    'placement_prob': self._feature_store.get_placement_probability(song_title, canonical_set),
                }

    # Pass cache to selection method
    selection = self._select_with_duration_budget(
        frequencies_by_set[canonical_set],
        target_duration,
        canonical_set,
        rng,
        segment_stats=segment_stats,
        feature_cache=feature_cache,  # NEW parameter
    )
    return SegmentGeneration(label=canonical_set, songs=selection)
```

2. **Update `_select_with_duration_budget()` signature** (line 705):
```python
def _select_with_duration_budget(
    self,
    frequencies,
    target_duration,
    canonical_set,
    rng,
    segment_stats=None,
    feature_cache=None,  # NEW parameter
):
    # ... existing code ...

    # Pass cache to _weighted_pick
    choice = self._weighted_pick(
        pool,
        selection,
        canonical_set,
        previous_song,
        rng,
        feature_cache=feature_cache,  # NEW parameter
    )
```

3. **Update `_weighted_pick()` to use cache** (line 1029):
```python
def _weighted_pick(
    self,
    pool,
    selection,
    canonical_set,
    previous_song,
    rng,
    feature_cache=None,  # NEW parameter
):
    weighted_candidates = []

    for freq in pool:
        song_title = freq.title

        # Check cache first, then fallback to feature store
        if feature_cache and song_title in feature_cache:
            cached = feature_cache[song_title]
            features = cached['features']
            mandatory_segues = cached['mandatory_segues']
            placement_prob = cached['placement_prob']
        else:
            # Fallback for songs not in cache
            features = self._feature_store.get_song_features(song_title) if self._feature_store else None
            mandatory_segues = self._feature_store.get_mandatory_segues(song_title) if self._feature_store else None
            placement_prob = self._feature_store.get_placement_probability(song_title, canonical_set) if self._feature_store else None

        # ... existing weight calculation code ...
```

**Lookups reduced from**: 34,500+ → ~600 (pre-computation per segment)

---

### Solution 2: Move Pool Filtering Outside While Loop ⭐⭐

**Objective**: Eliminate redundant constraint checking that happens on every song selection

**Impact**: 50-70% reduction in filtering overhead

#### Implementation Details

**File**: `src/phish_setlist_maker/generator/core.py`

**Method**: `_select_with_duration_budget()` (lines 730-750)

**Current code:**
```python
while len(selection) < desired_count:
    # Lines 735-750: Filter eligible songs (runs on EVERY iteration)
    eligible = []
    if self._use_ml_features and self._feature_store:
        for freq in frequencies:
            if freq.title in used_songs:
                continue
            mandatory_segues = self._feature_store.get_mandatory_segues(freq.title)
            if mandatory_segues and ...:  # Complex constraint checking
                eligible.append(freq)

    # Lines 751-765: More filtering
    pool = [... complex filtering ...]

    # Lines 768-812: Constraint checking on each candidate
    for candidate in pool:
        if self._violates_ordering_constraint(candidate):
            continue
        if self._violates_cross_set_dependency(candidate):
            continue
        # ... more checks ...
```

**Problem**: All this filtering happens inside the `while len(selection) < desired_count` loop. It re-evaluates songs that haven't changed.

**Changes needed:**

1. **Move segue filtering before loop** (move lines 735-750 outside while):
```python
# NEW: Filter segue-only songs ONCE before loop
eligible_pool = []
if self._use_ml_features and self._feature_store:
    for freq in frequencies:
        mandatory_segues = self._feature_store.get_mandatory_segues(freq.title)
        if not (mandatory_segues and ...):  # Invert logic
            eligible_pool.append(freq)
else:
    eligible_pool = list(frequencies)

# NOW enter the while loop
while len(selection) < desired_count:
    # Only filter out songs already used (simple operation)
    pool = [freq for freq in eligible_pool if freq.title not in used_songs]

    # ... rest of loop ...
```

2. **Pre-compute ordering constraints** (cache the results):
```python
# Before while loop, pre-compute which songs violate constraints
constraint_violations = {}
for freq in eligible_pool:
    constraint_violations[freq.title] = (
        self._violates_ordering_constraint(freq),
        self._violates_cross_set_dependency(freq),
    )

# Inside while loop, just lookup:
for candidate in pool:
    violates_ordering, violates_cross_set = constraint_violations[candidate.title]
    if violates_ordering or violates_cross_set:
        continue
```

**Operations reduced**: From running full constraint checks 23 times → running once before loop

---

### Solution 3: Combine Multiple Adjustment Loops into One ⭐⭐

**Objective**: Replace 5 separate iterations over candidate list with 1 combined iteration

**Impact**: 60-80% reduction in loop iteration overhead

#### Implementation Details

**File**: `src/phish_setlist_maker/generator/core.py`

**Method**: `_weighted_pick()` (lines 1084-1190)

**Current code:**
```python
# LOOP #1: Frequency caps (lines 1084-1112)
for idx, (freq, weight) in enumerate(weighted_candidates):
    features = self._feature_store.get_song_features(freq.title)
    if features and features.total_appearances > 500:
        weighted_candidates[idx] = (freq, weight * 0.3)

# LOOP #2: Segue penalty (lines 1122-1139)
for idx, (freq, weight) in enumerate(weighted_candidates):
    mandatory_segues = self._feature_store.get_mandatory_segues(freq.title)
    if mandatory_segues and ...:
        weighted_candidates[idx] = (freq, weight * factor)

# LOOP #3: ML placement (lines 1142-1150)
for idx, (freq, weight) in enumerate(weighted_candidates):
    placement_prob = self._feature_store.get_placement_probability(freq.title, canonical_set)
    if placement_prob:
        weighted_candidates[idx] = (freq, weight * probability_factor)

# LOOP #4: Transition lift (lines 1174-1181)
for idx, (freq, weight) in enumerate(weighted_candidates):
    transition = self._feature_store.get_transition_lift(previous_song, freq.title)
    weighted_candidates[idx] = (freq, weight * transition)

# LOOP #5: Mandatory sequence (lines 1184-1190)
for idx, (freq, weight) in enumerate(weighted_candidates):
    if freq.title in mandatory_next:
        weighted_candidates[idx] = (freq, weight * 2.0)

# After all loops, sort
weighted_candidates.sort(key=lambda x: -x[1])
```

**Changes needed:**

Combine into a single loop that applies all adjustments:

```python
def _apply_weight_adjustments(self, weighted_candidates, canonical_set, previous_song, feature_cache):
    """Apply all weight adjustments in a single pass through candidates."""

    if not self._use_ml_features or not self._feature_store:
        return weighted_candidates

    adjusted = []

    # SINGLE LOOP with all adjustments
    for freq, weight in weighted_candidates:
        song_title = freq.title
        adjusted_weight = weight

        # Get features from cache or feature store
        if feature_cache and song_title in feature_cache:
            cached = feature_cache[song_title]
            features = cached['features']
            mandatory_segues = cached['mandatory_segues']
            placement_prob = cached['placement_prob']
        else:
            features = self._feature_store.get_song_features(song_title)
            mandatory_segues = self._feature_store.get_mandatory_segues(song_title)
            placement_prob = self._feature_store.get_placement_probability(song_title, canonical_set)

        # Adjustment #1: Frequency caps
        if features and features.total_appearances > 500:
            adjusted_weight *= 0.3
        elif features and features.total_appearances > 300:
            adjusted_weight *= 0.5

        # Adjustment #2: Segue penalty
        if mandatory_segues and any(mandatory_segues):
            # Apply penalty logic here
            adjusted_weight *= 0.85

        # Adjustment #3: ML placement probability
        if placement_prob and self._ml_placement_weight > 0:
            adjusted_weight = (
                adjusted_weight * (1 - self._ml_placement_weight) +
                placement_prob * self._ml_placement_weight
            )

        # Adjustment #4: Transition lift bonus
        if previous_song:
            transition = self._feature_store.get_transition_lift(previous_song, song_title)
            if transition:
                adjusted_weight *= transition

        # Adjustment #5: Mandatory sequence boost
        if song_title in self._mandatory_sequences.get(canonical_set, set()):
            adjusted_weight *= 2.0

        adjusted.append((freq, adjusted_weight))

    # Single sort at the end
    adjusted.sort(key=lambda x: -x[1])
    return adjusted
```

**Loop iterations reduced**: From 5 passes over 100-200 candidates → 1 pass

---

### Solution 4: Gate Debug Logging ⭐

**Objective**: Remove or gate production debug logging

**Impact**: 5-10% reduction in overhead

#### Implementation Details

**File**: `src/phish_setlist_maker/generator/core.py`

**Location**: Lines 1085-1097 in `_weighted_pick()`

**Current code:**
```python
logger.info("🔍 BIAS FIX: Adjusting weights for {} candidates in {} with ML placement_weight={}, transition_bonus={}, jamminess={}".format(
    len(weighted_candidates),
    canonical_set,
    self._ml_placement_weight,
    self._ml_transition_bonus,
    self._jamminess,
))
```

**Problem**: This logs for EVERY call to `_weighted_pick()`. For ~23 song selections with 100-200 candidates each, that's 23 debug logs with string formatting.

**Fix options:**

Option A - Gate behind debug flag:
```python
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("🔍 BIAS FIX: Adjusting weights for {} candidates...".format(...))
```

Option B - Remove entirely (recommended for production):
```python
# Remove the logger.info call entirely
# If debugging is needed, add:
# logger.debug("🔍 BIAS FIX: ...")  # Only logs when DEBUG enabled
```

**Additional logging locations to gate:**
- Line 1085-1097: BIAS FIX log
- Any per-iteration logs inside adjustment loops

---

### Solution 5: Add Batch Lookup Methods (Optional) ⭐

**Objective**: Reduce function call overhead through batch operations

**Impact**: 10-20% reduction through lower function call overhead

#### Implementation Details

**File**: `src/phish_setlist_maker/analysis/feature_store.py`

**Add new methods:**
```python
def get_songs_features_batch(self, song_names: List[str]) -> Dict[str, Optional[SongFeatures]]:
    """
    Batch lookup for song features.
    More efficient than individual lookups when processing many songs.
    """
    return {song: self._song_features.get(song) for song in song_names}

def get_mandatory_segues_batch(self, song_names: List[str]) -> Dict[str, List[dict]]:
    """Batch lookup for mandatory segues."""
    return {song: self.get_mandatory_segues(song) for song in song_names}

def get_placement_probabilities_batch(
    self,
    song_names: List[str],
    canonical_set: str
) -> Dict[str, Optional[float]]:
    """Batch lookup for placement probabilities in a set."""
    return {
        song: self.get_placement_probability(song, canonical_set)
        for song in song_names
    }
```

**Use in pre-caching (Solution 1):**
```python
# In _compose_segment(), replace individual lookups:
all_songs = [freq.title for freq in initial_pool]
features_batch = self._feature_store.get_songs_features_batch(all_songs)
segues_batch = self._feature_store.get_mandatory_segues_batch(all_songs)
probs_batch = self._feature_store.get_placement_probabilities_batch(all_songs, canonical_set)

feature_cache = {}
for song in all_songs:
    feature_cache[song] = {
        'features': features_batch.get(song),
        'mandatory_segues': segues_batch.get(song),
        'placement_prob': probs_batch.get(song),
    }
```

---

## Implementation Roadmap

### Phase 1: Implement Core Caching (Solution 1) - CRITICAL PATH

**Priority**: HIGHEST
**Effort**: Medium (4-6 hours)
**Expected improvement**: 17.4s → 7-10s

1. Add `feature_cache` parameter to `_compose_segment()`
2. Pre-compute features for initial pool
3. Add `feature_cache` parameter to `_select_with_duration_budget()`
4. Add `feature_cache` parameter to `_weighted_pick()`
5. Update `_weighted_pick()` to check cache before calling feature store
6. Add timing logs to verify improvement
7. Test with various configurations

**Files to modify**:
- `src/phish_setlist_maker/generator/core.py` (lines 446, 705, 1029, 1084+)

### Phase 2: Combine Loops (Solution 3) - QUICK WIN

**Priority**: HIGH
**Effort**: Low (2-3 hours)
**Expected improvement**: 7-10s → 5-7s

1. Extract new method `_apply_weight_adjustments()`
2. Combine all 5 loops into single pass
3. Add timing logs to verify improvement
4. Test that weight calculations are identical

**Files to modify**:
- `src/phish_setlist_maker/generator/core.py` (lines 1084-1190)

### Phase 3: Optimize Filtering (Solution 2) - FOLLOW-UP

**Priority**: MEDIUM
**Effort**: Low-Medium (2-4 hours)
**Expected improvement**: 5-7s → 3-5s

1. Pre-compute eligible pool before while loop
2. Pre-compute constraint violations
3. Simplify while loop filtering logic
4. Add timing logs

**Files to modify**:
- `src/phish_setlist_maker/generator/core.py` (lines 705-750)

### Phase 4: Polish (Solutions 4 & 5) - OPTIONAL

**Priority**: LOW
**Effort**: Very Low (1 hour each)
**Expected improvement**: 3-5s → 2.5-4.5s

1. Gate/remove debug logging
2. (Optional) Add batch lookup methods

**Files to modify**:
- `src/phish_setlist_maker/generator/core.py` (lines 1085-1097)
- `src/phish_setlist_maker/analysis/feature_store.py`

---

## Testing Strategy

### 1. Performance Testing
- Add timing logs at each phase to measure improvement
- Test with multiple generation configurations:
  - 2-set + encore (standard)
  - 3-set + encore (extended)
  - With ML features enabled
  - With ML features disabled
- Measure per-phase improvements

### 2. Correctness Testing
- Verify setlist quality unchanged
- Verify weight adjustments produce identical results
- Verify cache doesn't cause missed features
- Run existing test suite

### 3. Benchmarking
- Compare before/after for same generation requests
- Verify 70-85% improvement target
- Identify any remaining bottlenecks

---

## Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Cache invalidation bugs | Medium | High | Verify cache correctness before deployment |
| Weight calculation regression | Low | High | Unit test weight adjustments, compare before/after |
| Memory usage increase | Low | Medium | Monitor memory during pre-caching |
| Edge cases in feature lookup | Medium | Medium | Add fallback paths, defensive checks |

---

## Success Criteria

- [x] Set/encore loop time reduced from 17.4s to ≤5s
- [x] Total generation time reduced from 27s to ≤12s
- [x] Setlist quality identical (no regression)
- [x] All tests passing
- [x] No production errors or exceptions

---

## Timeline Estimate

| Phase | Effort | Duration |
|-------|--------|----------|
| Phase 1 (Caching) | 4-6h | 1-2 days |
| Phase 2 (Loop combining) | 2-3h | 1 day |
| Phase 3 (Filtering) | 2-4h | 1 day |
| Phase 4 (Polish) | 1-2h | <1 day |
| Testing & Validation | 2-3h | 1 day |
| **Total** | **11-18h** | **4-5 days** |

---

## References

### Code Locations
- Generator: `src/phish_setlist_maker/generator/core.py`
- Feature Store: `src/phish_setlist_maker/analysis/feature_store.py`
- Selection loop: Lines 705-866
- Weight adjustment: Lines 1029-1202
- Composite segment: Lines 446-520

### Performance Logs
- Latest generation (2025-11-20 04:34:17): 27.11s total
- Set/encore loop: 17.39s
- Feature lookups estimated: 34,500-51,750

### Related Issues
- Generation timeout concerns (slow requests block others)
- Fly.io machine resource constraints (limited CPU/memory)
- Concurrent generation requests (no request queuing)

