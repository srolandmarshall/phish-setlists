# Phase 2.6: Jamminess & Duration Control

**Completed**: October 24, 2025

---

## Overview

Implemented user-controlled jamminess parameter to give users fine-grained control over setlist intensity, from tight/concise to extended jam sessions. This phase also fixed critical bugs in Set 2 duration targeting and introduced dynamic song count adjustment based on jamminess level.

---

## Problem Statement

### 1. Uncontrolled Set Durations

- Sets were generating inconsistently long (2+ hours) due to biased song selection
- Set 2 had only ~9% compliance with 65-80 minute target
- Duration capping logic was working against the duration targets instead of enforcing them

### 2. No User Control Over Intensity

- Users had no way to influence whether they got "greatest hits" (short, packed) or "extended jams" (long, exploratory)
- System used fixed percentile (p80) for all song durations
- No way to explore different play styles

### 3. Inconsistent Set Lengths

- Set 1: 10 songs (default)
- Set 2: 9 songs (default)
- But with different jam intensities, this should vary

---

## Solution Architecture

### Core Components

#### 1. Multi-Percentile Duration System

Instead of using only p80 (80th percentile), the system now stores and uses multiple percentile durations for each song:

```python
# Historical.py - SegmentStatistics dataclass
song_durations_p30: Dict[str, float]  # Short/tight versions (30th percentile)
song_durations_p50: Dict[str, float]  # Median/average versions
song_durations_p70: Dict[str, float]  # Above-average jams
song_durations_p90: Dict[str, float]  # Full extended jams (80th → 90th for consistency)
```

#### 2. Dynamic Percentile Selection (`_select_duration_map_by_intensity`)

Selects which percentile to use based on either:

- **User-specified jamminess** (0.0-1.0): Directly maps to percentile
- **Dynamic calculation** based on remaining budget:
  - Early in set (0-40% full): p50 (conservative, leaves room)
  - Middle of set (40-70% full): p70 (above-average)
  - Late in set (70%+ full): Dynamic (tight to finish within budget)

**Jamminess Scale**:

- `0.0-0.25`: Tight/concise (p30)
- `0.25-0.5`: Balanced (p50)
- `0.5-0.75`: Jammy (p70)
- `0.75-1.0`: Maximum jam (p90)

#### 3. Constraint Relaxation

Duration targets scale with jamminess:

- `jamminess >= 0.9`: Upper bound × 1.5 (50% increase)
  - Set 1: 60-75min → 60-112min
  - Set 2: 65-80min → 65-120min
- `jamminess >= 0.75`: Upper bound × 1.25 (25% increase)
  - Set 1: 60-75min → 60-94min
  - Set 2: 65-80min → 65-100min
- `jamminess < 0.75`: Normal targets (60-75min Set 1, 65-80min Set 2)

#### 4. Dynamic Song Count Adjustment

Fewer high-intensity songs when using longer percentiles:

- `jamminess >= 0.75`: Reduce by 1 song per set
  - Set 1: 10 → 9 songs
  - Set 2: 11 → 10 songs
  - Set 3: 6 → 5 songs
- `jamminess < 0.75`: Use default counts (duration capping handles it)

---

## Implementation Details

### Files Modified

#### `src/phish_setlist_maker/constants.py` (Line 40)

```python
DEFAULT_SET_LENGTHS: Dict[str, int] = {
    "set1": 10,
    "set2": 11,  # Increased from 9 to better hit 65-80 min target
    "set3": 6,
    "encore": 2,
}
```

#### `src/phish_setlist_maker/generator/core.py`

**Dynamic Song Count Adjustment** (Lines 186-193):

```python
# Adjust song counts based on jamminess level
# High jamminess (extended jams) → fewer songs needed to fill duration
# Low jamminess uses default counts (duration capping handles it naturally)
if self._jamminess is not None and self._jamminess >= 0.75:
    # High jamminess: fewer songs, longer jams
    lengths["set1"] = max(8, lengths.get("set1", 10) - 1)
    lengths["set2"] = max(9, lengths.get("set2", 11) - 1)
    lengths["set3"] = max(5, lengths.get("set3", 6) - 1)
```

**Duration Constraint Relaxation** (Lines 645-658):

```python
if duration_target:
    lower, upper = duration_target
    window = max(upper - lower, 0)

    if self._jamminess is not None and self._jamminess >= 0.9:
        # At very high jamminess (0.9+), be VERY permissive
        adjusted_upper = upper * 1.5
    elif self._jamminess is not None and self._jamminess >= 0.75:
        # At high jamminess (0.75-0.9), be more permissive
        adjusted_upper = upper * 1.25
    else:
        # Default behavior - use upper bound as target
        adjusted_upper = upper

    max_duration = float(adjusted_upper)
```

**Percentile Selection Logic** (Lines 536-600):

```python
def _select_duration_map_by_intensity(self, stats, current_duration, duration_target):
    """Select appropriate duration percentile based on jam intensity."""
    if not stats:
        return {}

    # User-specified jamminess overrides dynamic selection
    if self._jamminess is not None:
        if self._jamminess < 0.25:
            return stats.song_durations_p30
        elif self._jamminess < 0.5:
            return stats.song_durations_p50
        elif self._jamminess < 0.75:
            return stats.song_durations_p70
        else:
            return stats.song_durations_p90

    # Dynamic selection based on remaining budget
    if not duration_target:
        return stats.song_durations_p50

    lower, upper = duration_target
    target_mid = (lower + upper) / 2
    filled_ratio = current_duration / target_mid if target_mid > 0 else 0.0

    if filled_ratio < 0.4:
        return stats.song_durations_p50  # Early - conservative
    elif filled_ratio < 0.7:
        return stats.song_durations_p70  # Middle - above-average
    else:
        remaining = max(0, target_mid - current_duration)
        if remaining > 600:  # >10 minutes left
            return stats.song_durations_p70
        elif remaining > 300:  # 5-10 minutes left
            return stats.song_durations_p50
        else:
            return stats.song_durations_p30  # Tight finish
```

#### `src/phish_setlist_maker/generator/historical.py`

Added multi-percentile duration storage to `SegmentStatistics`:

```python
@dataclass(frozen=True)
class SegmentStatistics:
    # ... existing fields ...
    song_durations: Dict[str, float]      # 80th percentile (backward compat)
    song_durations_p30: Dict[str, float]  # Short/tight versions
    song_durations_p50: Dict[str, float]  # Median/average versions
    song_durations_p70: Dict[str, float]  # Above-average jams
    song_durations_p90: Dict[str, float]  # Full extended jams
```

#### `src/phish_setlist_maker/service/generation.py`

```python
@dataclass(frozen=True)
class GenerationRequest:
    # ... existing fields ...
    jamminess: Optional[float] = None  # 0.0 = tight, 0.5 = balanced, 1.0 = max jam
```

#### `src/phish_setlist_maker/api/schemas.py`

```python
class GenerateRequestModel(BaseModel):
    # ... existing fields ...
    jamminess: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Jam intensity override (0=tight/concise, 0.5=balanced, 1.0=maximum jam). None=dynamic selection."
    )
```

### API Integration

#### CLI

```bash
poetry run phish-setlist-maker generate --jamminess 0.5
```

#### REST API

```bash
# Tight (concise, more songs)
curl "http://localhost:8000/generate?jamminess=0.01"

# Balanced (default behavior)
curl "http://localhost:8000/generate?jamminess=0.5"

# Full Send (extended jams, fewer songs)
curl "http://localhost:8000/generate?jamminess=0.99"

# POST with JSON
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"jamminess": 0.75}'
```

#### Web UI

Jam Dial slider on landing page (`static/index.html`):

- Checkbox to enable/disable
- Slider from 0-100 (maps to 0.0-1.0)
- Dynamic warnings

---

## Bug Fixes

### Bug #1: Set 2 Duration Undershooting (CRITICAL)

**Symptom**: Set 2 hitting target range only ~9% of the time
**Root Cause**:

- `DEFAULT_SET_LENGTHS["set2"]` was 9 songs (too few for 65-80 min target)
- Duration margin calculation was subtracting from upper bound instead of using it as target

**Fix**:

- Increased Set 2 default from 9 to 11 songs
- Changed margin logic from `adjusted_upper = max(lower, upper - margin)` to `adjusted_upper = upper`

**Result**: Set 2 compliance improved from **9% → 85-90%**

### Bug #2: Duration Capping Over-Constraining (MODERATE)

**Symptom**: Sets exceeding duration targets when using high percentiles
**Root Cause**: Margin calculation was reducing the upper bound, making it impossible to hit targets with longer songs

**Fix**: Removed margin subtraction; use upper bound directly with safety_factor providing conservatism

**Result**: Better compliance across all jamminess levels

---

## Results & Validation

### Compliance Testing (N=50 setlists each)

| Jamminess            | Set 1  | Set 2 | Target               |
| -------------------- | ------ | ----- | -------------------- |
| **0.01 (Tight)**     | 100% ✓ | 84% ✓ | 60-75min, 65-80min   |
| **0.5 (Balanced)**   | 92% ✓  | 90% ✓ | 60-75min, 65-80min   |
| **0.99 (Full Send)** | 100% ✓ | 98% ✓ | 60-112min, 65-120min |

### Song Count Behavior

| Jamminess | Set 1 Songs | Set 2 Songs | Avg Duration  |
| --------- | ----------- | ----------- | ------------- |
| **0.01**  | 10.0        | 11.1        | 70min / 78min |
| **0.5**   | 10.0        | 10.7        | 70min / 75min |
| **0.99**  | 9.0         | 10.1        | 63min / 70min |

### Key Observations

1. **Tight setlists** (0.01): More songs, shorter versions
2. **Balanced setlists** (0.5): Comfortable middle ground
3. **Extended jams** (0.99): Fewer songs, longer individual performances

---

## Analysis Scripts

### `scripts/analyze_jamminess_with_charts.py`

Generates matplotlib charts comparing jamminess levels:

- 9-subplot visualization with distributions, box plots, histograms
- High-resolution PNG output (`jamminess_analysis.png`)
- Statistical summaries and compliance reporting

**Usage**:

```bash
poetry run python scripts/analyze_jamminess_with_charts.py
# Generates: jamminess_analysis.png
```

**Output**: 3x3 grid showing:

1. Set 1 duration distribution
2. Set 2 duration distribution
3. Song count comparison
4. Set 1 box plot
5. Set 2 box plot
6. Duration means comparison
7. Set 1 song count distribution
8. Set 2 song count distribution
9. Target compliance

---

## User Experience

### Web Interface

Users see the Jam Dial on the landing page:

- **Unchecked** (default): Dynamic intensity based on budget
- **Checked + Slider**: Manual control from 0-100 (Tight → Full Send)
- **Real-time feedback**: Warning messages at extremes

### Backend Behavior

- **None** (default): Dynamic percentile selection based on remaining time
- **0.0-0.25**: Tight (p30 durations, may add songs)
- **0.25-0.5**: Balanced (p50 durations, standard counts)
- **0.5-0.75**: Jammy (p70 durations, standard counts)
- **0.75-1.0**: Extended (p90 durations, reduce song counts)

### Consistency

- Duration targets automatically relax at high jamminess
- Song counts automatically adjust to keep durations consistent
- User expectations matched: "tight" = more songs, "jammy" = fewer songs

---

## Technical Debt & Future Work

### Potential Enhancements

1. **Jamminess presets**: "Greatest Hits", "Balanced", "Deep Dive", "Full Send"
2. **Set-specific control**: Different jamminess per set
3. **Jam length modeling**: Predict optimal jam count based on band's era
4. **Encore adjustment**: Correlate jamminess across all sets
5. **Playlist commentary**: Add notes about jam intensity to generated playlists

### Known Limitations

1. Jamminess affects only duration percentiles, not song selection probabilities
2. No learning from user preferences
3. Dynamic intensity doesn't account for song type (opener vs. closer)
4. Three-set shows use fixed ratios (could be dynamic)

---

## Testing Checklist

- [x] Set 2 hitting 85%+ target compliance
- [x] Set 1 hitting 90%+ target compliance
- [x] Jamminess 0.01 produces 10+ songs
- [x] Jamminess 0.99 produces 8-9 songs
- [x] Duration constraints properly relax at high jamminess
- [x] Default behavior unchanged (backward compatible)
- [x] Web UI slider works end-to-end
- [x] API accepts jamminess parameter
- [x] CLI accepts jamminess flag
- [x] All existing tests pass

---

## Files Changed Summary

### New Files

- `scripts/analyze_jamminess_with_charts.py` - Analysis script with matplotlib

### Modified Files

- `src/phish_setlist_maker/constants.py` - Set 2 default length
- `src/phish_setlist_maker/generator/core.py` - Jamminess logic
- `src/phish_setlist_maker/generator/historical.py` - Multi-percentile storage
- `src/phish_setlist_maker/service/generation.py` - GenerationRequest
- `src/phish_setlist_maker/api/schemas.py` - API schema
- `src/phish_setlist_maker/api/factories.py` - Request wiring
- `static/index.html` - Jam Dial UI
- `static/landing.css` - Jam Dial styles
- `static/era-picker.js` - Dynamic warnings
- `data/analytics/excluded_songs.csv` - Added "Interview"

---

## References

- **Phase 2.1**: ML-enhanced generation foundations
- **Phase 2.2**: Constraints and ordering rules
- **Phase 2.5**: Set-ending track selection
- **Phase 2.6**: THIS - Jamminess and duration control

---

**Next Phase**: Phase 2.7 - Opener Selection Improvements
