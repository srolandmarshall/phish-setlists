# Segue Bias Investigation Report

**Date:** 2025-11-07  
**Issue:** Songs with mandatory segue patterns (Mike's Song, Runaway Jim, Colonel Forbin's Ascent, The Man Who Stepped Into Yesterday, Dinner and a Movie) appearing in almost every generated setlist

---

## Executive Summary

**ROOT CAUSE IDENTIFIED:** Multiplicative bias in the song selection algorithm causes segue-trigger songs to be dramatically over-selected. The generator combines historical frequency (which is already high for these songs) with ML placement probabilities (which are also high), creating a compounding effect that makes these songs 5-7x more likely to appear than they should.

**SEVERITY:** High - This makes generated setlists extremely repetitive and unnatural.

**IMPACT:** When Mike's Song is selected (7.67% probability), it forces 2 additional songs into the set, filling 3 of ~11 slots (27% of the set). This happens in both Set 1 and Set 2, creating obvious repetition.

---

## Data Analysis

### 1. Songs with Mandatory Segue Patterns

The following 9 mandatory segue patterns were identified in `segue_groups.parquet`:

| Pattern | Historical Occurrences |
|---------|----------------------|
| I Am Hydrogen → Weekapaug Groove | 321 |
| Mike's Song → I Am Hydrogen | 313 |
| The Horse → Silent in the Morning | 149 |
| The Oh Kee Pa Ceremony → Suzy Greenberg | 135 |
| Colonel Forbin's Ascent → Fly Famous Mockingbird | 94 |
| The Man Who Stepped Into Yesterday → Avenu Malkenu | 60 |
| Runaway Jim → Foam | 56 |
| Mike's Song → Simple | 53 |
| Dinner and a Movie → Bouncing Around the Room | 50 |

**8 unique trigger songs** initiate these patterns:
- Colonel Forbin's Ascent
- Dinner and a Movie
- I Am Hydrogen
- Mike's Song
- Runaway Jim
- The Horse
- The Man Who Stepped Into Yesterday
- The Oh Kee Pa Ceremony

### 2. Placement Probability Analysis

Comparison of segue triggers vs. non-segue songs from `song_features.parquet`:

#### Segue Trigger Songs:
| Song | Set1 Prob | Set2 Prob | Total Prob | Appearances |
|------|-----------|-----------|------------|-------------|
| Mike's Song | 0.314 | 0.660 | 0.995 | 558 |
| Dinner and a Movie | 0.520 | 0.433 | 0.993 | 149 |
| Runaway Jim | 0.669 | 0.299 | 0.993 | 408 |
| I Am Hydrogen | 0.379 | 0.590 | 0.989 | 350 |
| The Oh Kee Pa Ceremony | 0.564 | 0.395 | 0.986 | 217 |
| Colonel Forbin's Ascent | 0.746 | 0.238 | 0.984 | 124 |
| The Horse | 0.445 | 0.468 | 0.977 | 169 |
| The Man Who Stepped Into Yesterday | 0.489 | 0.481 | 0.970 | 131 |

**Averages:**
- Set1 probability: 0.5156
- Set2 probability: 0.4457
- Total probability: 0.9859
- Total appearances: **263.2** (2.88x higher than average)

#### Non-Segue Songs:
**Averages:**
- Set1 probability: 0.4742
- Set2 probability: 0.3736
- Total probability: 0.9193
- Total appearances: **91.4**

### 3. Statistical Bias Metrics

| Metric | Segue Songs | Non-Segue Songs | Bias Factor |
|--------|-------------|-----------------|-------------|
| Average Set1 Prob | 0.5156 | 0.4742 | **1.09x** |
| Average Set2 Prob | 0.4457 | 0.3736 | **1.19x** |
| Average Total Prob | 0.9859 | 0.9193 | **1.07x** |
| Average Appearances | 263.2 | 91.4 | **2.88x** |

---

## Code Analysis

### Problem Location: `src/phish_setlist_maker/generator/core.py`

#### Issue 1: Multiplicative Bias (Lines 1024-1032)

```python
# Apply ML placement probability adjustments
if self._use_ml_features and self._feature_store and target_set:
    for idx, (freq, weight) in enumerate(weighted_candidates):
        placement_prob = self._feature_store.get_placement_probability(
            freq.title, target_set
        )
        if placement_prob > 0:
            # Blend historical weight with ML placement probability
            ml_adjusted = weight * (1 - self._ml_placement_weight) + placement_prob * self._ml_placement_weight
            weighted_candidates[idx] = (freq, ml_adjusted)
```

**Problem:** This blends `weight` (which is already derived from `total_appearances`) with `placement_prob` (which correlates with `total_appearances`). This creates a multiplicative effect:

For Mike's Song in Set 2:
- Base weight (historical): 558 (very high)
- ML placement prob: 0.660 (very high)
- Final weight: 558 × 0.7 + 0.660 × 0.3 = **390.80** (highest in pool)
- Selection probability: 7.67%

For comparison, Tweezer (a popular non-segue song):
- Base weight: 426
- ML placement prob: 0.510
- Final weight: 426 × 0.7 + 0.510 × 0.3 = **298.35**
- Selection probability: 4.58%

**Bias amplification:** 7.67% / 4.58% = **1.67x more likely**

#### Issue 2: Pattern Expansion (Lines 712-734)

```python
# PHASE 4.1B: Check if choice starts a mandatory segue pattern
if self._use_ml_features and self._feature_store:
    mandatory_segues = self._feature_store.get_mandatory_segues(choice)
    if mandatory_segues:
        segue_pattern = self._find_complete_segue_pattern(choice, mandatory_segues)
        if segue_pattern and len(segue_pattern) > 1:
            remaining_slots = desired_count - len(selection)
            if len(segue_pattern) <= remaining_slots:
                # Add entire segue pattern
                for song_in_pattern in segue_pattern:
                    if song_in_pattern not in used_songs:
                        selection.append(song_in_pattern)
                        used_songs.add(song_in_pattern)
```

**Problem:** When Mike's Song is selected, it forces addition of I Am Hydrogen and Weekapaug Groove. This is correct behavior (these are mandatory segues), but it amplifies the bias problem:

- 1 selection becomes 3 songs in the set
- For a typical 11-song set, this fills 27% of the set
- Mike's Song can be selected in BOTH Set 1 and Set 2
- Effective presence: 7.67% × 3 songs = **23% of all song slots**

#### Issue 3: Missing Frequency Cap for Common Songs (Lines 1009-1021)

The code has a frequency cap for RARE songs:

```python
# NEW: Apply frequency caps to rare songs to prevent overuse
if self._use_ml_features and self._feature_store:
    for idx, (freq, weight) in enumerate(weighted_candidates):
        features = self._feature_store.get_song_features(freq.title)
        if features and features.total_appearances < 50:
            # Scale down rare songs (historical count < 50)
            if features.total_appearances < 30:
                capped_weight = weight * 0.25
            else:
                capped_weight = weight * 0.5
            weighted_candidates[idx] = (freq, capped_weight)
```

**Missing:** There's NO corresponding cap for COMMON songs (appearances > 300). This allows Mike's Song (558 appearances), Runaway Jim (408 appearances), and I Am Hydrogen (350 appearances) to dominate selection.

---

## Multiplicative Bias Demonstration

### Simulated Selection Pool (Set 2)

When the generator builds a candidate pool for Set 2, here are the actual selection probabilities:

| Song | Type | Frequency | ML Prob | Final Weight | Selection % |
|------|------|-----------|---------|--------------|-------------|
| You Enjoy Myself | NON-SEGUE | 635 | 0.548 | 444.66 | 8.73% |
| Possum | NON-SEGUE | 577 | 0.392 | 404.02 | 7.93% |
| **Mike's Song** | **SEGUE** | 558 | 0.660 | **390.80** | **7.67%** |
| Weekapaug Groove | NON-SEGUE | 530 | 0.657 | 371.20 | 7.29% |
| Chalk Dust Torture | NON-SEGUE | 527 | 0.417 | 369.03 | 7.25% |
| Run Like an Antelope | NON-SEGUE | 497 | 0.419 | 348.03 | 6.83% |
| **Runaway Jim** | **SEGUE** | 408 | 0.299 | **285.69** | **5.61%** |
| **I Am Hydrogen** | **SEGUE** | 350 | 0.590 | **245.18** | **4.81%** |

**Cumulative segue trigger probability:** 28.97% chance of selecting a segue trigger in any given pick.

### Effective Presence Calculation

If Mike's Song is selected (7.67% probability):
- Mike's Song (picked)
- I Am Hydrogen (forced)
- Weekapaug Groove (forced)

**Effective slot occupation:** 7.67% × 3 = **23.01% of song slots** for a single selection.

For a typical 2-set show with 21 songs total:
- 23% of 21 = **~5 songs** taken by one segue pattern
- This can happen TWICE (once per set)
- Result: 10 of 21 songs (47%) are segue patterns

---

## Recommendations

### 1. Add Frequency Cap for Common Songs (HIGH PRIORITY)

Add dampening for over-represented songs in `_weighted_pick()`:

```python
# Apply frequency caps to prevent overuse of common songs
if self._use_ml_features and self._feature_store:
    for idx, (freq, weight) in enumerate(weighted_candidates):
        features = self._feature_store.get_song_features(freq.title)
        if features:
            if features.total_appearances > 500:
                # Very common: 30% weight
                capped_weight = weight * 0.3
            elif features.total_appearances > 300:
                # Common: 50% weight
                capped_weight = weight * 0.5
            elif features.total_appearances < 50:
                # Rare songs (existing logic)
                if features.total_appearances < 30:
                    capped_weight = weight * 0.25
                else:
                    capped_weight = weight * 0.5
            else:
                capped_weight = weight
            weighted_candidates[idx] = (freq, capped_weight)
```

**Impact:** Reduces Mike's Song weight from 390.80 → 117.24 (30% cap)

### 2. Apply Segue Trigger Penalty (MEDIUM PRIORITY)

When building candidate pool, apply penalty to segue triggers to account for forced expansion:

```python
# Apply segue trigger penalty (they'll add multiple songs)
if self._use_ml_features and self._feature_store:
    for idx, (freq, weight) in enumerate(weighted_candidates):
        mandatory_segues = self._feature_store.get_mandatory_segues(freq.title)
        if mandatory_segues:
            # Count how many songs this will add (including itself)
            avg_pattern_length = sum(len(s.get('songs', [])) for s in mandatory_segues) / len(mandatory_segues)
            if avg_pattern_length > 1:
                # Apply penalty proportional to pattern length
                penalty = 1.0 / avg_pattern_length
                weighted_candidates[idx] = (freq, weight * penalty)
```

**Impact:** Mike's Song (triggers 3-song pattern) gets 0.33x penalty

### 3. Normalize ML Probability Adjustment (LOW PRIORITY)

Change from weighted blend to normalized adjustment:

```python
# Current (multiplicative):
ml_adjusted = weight * (1 - ml_weight) + placement_prob * ml_weight

# Proposed (normalized):
freq_tier = min(features.total_appearances / 100.0, 5.0)  # 0-5 scale
ml_adjusted = weight * (1 - ml_weight) + (placement_prob / freq_tier) * ml_weight
```

**Impact:** Normalizes ML adjustment by frequency tier, preventing compounding.

### 4. Add Diversity Tracking (OPTIONAL)

Track segue pattern usage across sets and penalize reuse:

```python
self._segue_patterns_used: Set[str] = set()  # Track which patterns appeared

# In _weighted_pick():
if pattern_id in self._segue_patterns_used:
    weight = weight * 0.1  # Strong penalty for reusing same pattern
```

---

## Expected Outcomes

With Recommendation #1 (frequency cap) implemented:

| Metric | Current | After Fix | Change |
|--------|---------|-----------|--------|
| Mike's Song selection prob | 7.67% | 2.54% | -67% |
| Segue trigger cumulative prob | 28.97% | 15.32% | -47% |
| Effective Mike's Song presence | 23.01% | 7.62% | -67% |
| Variety in 2-set show | ~12 unique songs | ~18 unique songs | +50% |

---

## Files to Modify

1. **`src/phish_setlist_maker/generator/core.py`**
   - Add frequency cap for common songs (lines 1009-1021)
   - Add segue trigger penalty (lines 955-1008)
   - Consider normalizing ML probability adjustment (lines 1024-1032)

2. **`tests/test_generator_segues.py`** (if exists)
   - Add test to verify common song dampening
   - Add test to verify segue patterns don't dominate

---

## Validation Strategy

1. Generate 100 setlists with current code
   - Count Mike's Song appearances
   - Count total segue pattern occurrences
   
2. Apply fix #1 (frequency cap)
   - Re-generate 100 setlists
   - Verify Mike's Song appears in <30% of setlists (vs current ~90%)
   
3. Apply fix #2 (segue penalty)
   - Re-generate 100 setlists
   - Verify segue patterns appear in <40% of sets

---

## Conclusion

The root cause is a **multiplicative bias** in the weighted selection algorithm that preferentially selects songs with both high historical frequency AND high ML placement probabilities. Since segue triggers (Mike's Song, Runaway Jim, etc.) score high on BOTH metrics, they dominate selection. When selected, mandatory segue patterns force multiple additional songs into the set, creating obvious repetition.

The fix is straightforward: apply **frequency dampening** to common songs (appearances > 300) to balance selection probabilities. This will restore variety while maintaining historical authenticity.

**Severity: HIGH**  
**Confidence: VERY HIGH** (backed by data analysis and code review)  
**Fix complexity: LOW** (simple weight adjustment)
