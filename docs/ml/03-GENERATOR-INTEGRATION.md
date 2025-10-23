# Generator Integration: ML-Enhanced Setlist Generation

**Last Updated**: 2025-10-23  
**Status**: Phase 2.1 Complete ✅

---

## Table of Contents
1. [Overview](#overview)
2. [Feature Store Architecture](#feature-store-architecture)
3. [Generator Enhancements](#generator-enhancements)
4. [API Integration](#api-integration)
5. [Usage Examples](#usage-examples)
6. [Performance & Testing](#performance--testing)

---

## Overview

### What Changed

Phase 2.1 integrated ML features into the existing `/generate` endpoint while maintaining full backward compatibility. The generator now:

1. **Blends historical data with ML insights** (placement probabilities)
2. **Boosts high-confidence transitions** (lift scores)
3. **Maintains legacy behavior** as default option
4. **Enables gradual rollout** via feature flags

### Architecture

```
ML Features (Parquet)
    ↓
FeatureStore (In-Memory Cache)
    ↓
SetlistGenerator (Enhanced)
    ↓
Generated Setlist (More Authentic)
```

### Key Benefits

- **Data-driven nudges**: Placement matches historical patterns better
- **Transition awareness**: Songs flow naturally (Mike's → Weekapaug)
- **Backward compatible**: Zero breaking changes
- **Fast**: <150ms feature loading, negligible per-song overhead
- **Extensible**: Easy to add new feature types

---

## Feature Store Architecture

### FeatureStore Class

**Location**: `src/phish_setlist_maker/analysis/feature_store.py`

**Purpose**: Fast in-memory access to Phase 1 feature tables

### Data Classes

```python
@dataclass
class SongFeatures:
    """Placement probabilities and metadata."""
    song_title: str
    set1: float           # P(song in Set 1)
    set2: float           # P(song in Set 2)
    set3: float           # P(song in Set 3)
    encore: float         # P(song in Encore)
    entropy: float        # Versatility score
    total_appearances: int
    multi_home: bool      # Flexible placement?

@dataclass
class TransitionFeature:
    """Transition lift scores."""
    from_song: str
    to_song: str
    lift: float           # How much more likely than random
    support: int          # Number of occurrences
    confidence: float     # P(B|A)
```

### Loading & Caching

```python
class FeatureStore:
    def __init__(self, features_dir: Path):
        self.features_dir = features_dir
        self._song_features: Dict[str, SongFeatures] = {}
        self._transitions: Dict[Tuple[str, str], TransitionFeature] = {}
        self._loaded = False
    
    def load(self):
        """Load all features into memory (called once at init)."""
        # Load song_features.parquet
        df = pd.read_parquet(self.features_dir / "song_features.parquet")
        for row in df.itertuples():
            self._song_features[row.song_effective_title] = SongFeatures(...)
        
        # Load song_transitions.parquet
        df = pd.read_parquet(self.features_dir / "song_transitions.parquet")
        for row in df.itertuples():
            key = (row.from_song, row.to_song)
            self._transitions[key] = TransitionFeature(...)
        
        self._loaded = True
```

**Performance**:
- Load time: **<100ms** for 389 songs + 166 transitions
- Memory: **~2MB** total
- Lookup: **O(1)** dictionary access

### Query API

```python
# Get song features
features = store.get_song_features("Mike's Song")
print(features.set2)  # 0.66 (66% probability in Set 2)

# Get placement probability
prob = store.get_placement_probability("Tweezer", "set2")
print(prob)  # 0.78

# Get transition lift
transition = store.get_transition_lift("Mike's Song", "Weekapaug Groove")
print(transition.lift)  # High affinity score

# Check if song is multi-home
is_flexible = store.is_multi_home("Harry Hood")
print(is_flexible)  # True (appears in Set 1 and Set 2)
```

### Auto-Detection

Feature directory is auto-detected:
```python
# Default: data/analytics/features/
store = FeatureStore()  # Automatically finds features

# Custom path
store = FeatureStore(Path("/custom/path/features"))
```

---

## Generator Enhancements

### New Parameters

**`SetlistGenerator.__init__()` additions**:

```python
def __init__(
    self,
    session: Session,
    rng: Random,
    use_ml_features: bool = True,           # Enable ML mode (NEW, default True)
    ml_placement_weight: float = 0.3,       # ML influence 0-1 (NEW)
    ml_transition_bonus: float = 0.1,       # Transition boost 0-1 (NEW)
    features_dir: Optional[Path] = None,    # Custom feature path (NEW)
    # ... existing parameters
):
```

**Parameter Details**:

| Parameter | Default | Range | Purpose |
|-----------|---------|-------|---------|
| `use_ml_features` | `True` | bool | Enable/disable all ML features |
| `ml_placement_weight` | `0.3` | 0.0-1.0 | ML vs. historical blend ratio |
| `ml_transition_bonus` | `0.1` | 0.0-1.0 | Boost for high-lift transitions |
| `features_dir` | auto | Path | Custom feature location |

### Algorithm Changes

#### 1. Placement Probability Blending

**Location**: `_weighted_pick()` method

**Original** (legacy mode):
```python
weight = freq.count  # Pure historical frequency
```

**Enhanced** (ML mode):
```python
# Blend historical frequency with ML placement probability
historical_weight = freq.count / total_count  # Normalize to 0-1
ml_probability = store.get_placement_probability(song, target_set)

# Weighted blend (30% ML, 70% historical by default)
α = self.ml_placement_weight  # 0.3
blended = historical_weight * (1 - α) + ml_probability * α

# Re-scale to weight
weight = blended * scale_factor
```

**Effect**: Songs appear more frequently in their high-probability sets

**Example**:
- Tweezer in Set 2: Historical 35%, ML 78% → Blended ~48% → More likely
- Tweezer in Set 1: Historical 20%, ML 18% → Blended ~19% → Less likely

#### 2. Transition Lift Bonus

**Location**: `_weighted_pick()` when `previous_song` exists

**Logic**:
```python
if previous_song and use_ml_features:
    transition = store.get_transition_lift(previous_song, candidate_song)
    
    if transition and transition.lift > 2.0:
        # Normalize lift: 2-10× → 0-1 range
        normalized_lift = min((transition.lift - 2.0) / 8.0, 1.0)
        
        # Apply bonus
        boost = 1.0 + ml_transition_bonus * normalized_lift
        weight *= boost
```

**Effect**: High-lift transitions become more likely

**Examples**:
- After Mike's Song → Weekapaug gets **+10% boost** (lift ~47×)
- After Swept Away → Steep gets **+10% boost** (lift ~474×)
- After random song → no boost (lift <2×)

#### 3. Graceful Degradation

If features missing for a song:
```python
if features is None:
    # Fall back to historical-only weighting
    weight = freq.count
else:
    # Use ML blending
    weight = blended_weight
```

**Result**: System works even with partial feature coverage

### Integration Points

**Initialization**:
```python
def __init__(self, ...):
    if self.use_ml_features:
        self._feature_store = FeatureStore(features_dir)
        self._feature_store.load()
    else:
        self._feature_store = None
```

**Song Selection**:
```python
def _weighted_pick(self, pool, used_songs, previous_song, target_set):
    # ... build candidate pool
    
    # Apply ML adjustments if enabled
    if self._feature_store:
        # Placement blending
        for candidate in candidates:
            weight = apply_placement_blend(candidate, target_set)
        
        # Transition bonuses
        if previous_song:
            weight = apply_transition_boost(previous_song, candidate)
    
    # ... weighted random selection
```

### Backward Compatibility

**Legacy mode preserved**:
```python
# Old behavior (no ML)
gen = SetlistGenerator(session, use_ml_features=False)

# New behavior (with ML)
gen = SetlistGenerator(session, use_ml_features=True)  # Default
```

**Test results**: All 28 existing tests pass with no modifications

---

## API Integration

### Schema Updates

**Location**: `src/phish_setlist_maker/api/schemas.py`

```python
class GenerateRequestModel(BaseModel):
    """Request model for /generate endpoint."""
    
    # Existing fields
    year: Optional[int] = None
    num_sets: int = Field(default=2, ge=1, le=4)
    include_encore: bool = True
    seed: Optional[int] = None
    
    # NEW: ML feature controls
    use_ml_features: bool = Field(default=True)
    ml_placement_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    ml_transition_bonus: float = Field(default=0.1, ge=0.0, le=1.0)
```

**Validation**:
- `ml_placement_weight`: Must be 0.0-1.0 (0% to 100% ML influence)
- `ml_transition_bonus`: Must be 0.0-1.0 (0% to 100% boost)

### Service Layer

**Location**: `src/phish_setlist_maker/service/generation.py`

```python
@dataclass
class GenerationRequest:
    """Internal request object."""
    year: Optional[int]
    num_sets: int
    include_encore: bool
    seed: Optional[int]
    
    # NEW: ML parameters
    use_ml_features: bool
    ml_placement_weight: float
    ml_transition_bonus: float
```

**Flow**:
```
API Request (JSON)
    ↓
GenerateRequestModel (validation)
    ↓
GenerationRequest (dataclass)
    ↓
SetlistGenerator (generation)
    ↓
GenerationResult (response)
```

### Factory Pattern

**Location**: `src/phish_setlist_maker/api/factories.py`

```python
def build_generation_request(model: GenerateRequestModel) -> GenerationRequest:
    """Convert API model to internal request."""
    return GenerationRequest(
        year=model.year,
        num_sets=model.num_sets,
        include_encore=model.include_encore,
        seed=model.seed,
        use_ml_features=model.use_ml_features,          # NEW
        ml_placement_weight=model.ml_placement_weight,  # NEW
        ml_transition_bonus=model.ml_transition_bonus,  # NEW
    )
```

---

## Usage Examples

### CLI / Script Usage

#### Basic Generation (ML Enabled by Default)

```python
from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator.core import SetlistGenerator
from datetime import date
from random import Random

with session_scope() as session:
    generator = SetlistGenerator(
        session=session,
        rng=Random(42),
    )
    
    result = generator.generate(
        reference_date=date(2023, 12, 31),
        num_sets=2,
        include_encore=True,
    )
    
    print(f"Set 1: {len(result.sets[0].songs)} songs")
    print(f"Set 2: {len(result.sets[1].songs)} songs")
    print(f"Encore: {len(result.sets[2].songs)} songs")
```

#### Custom ML Parameters

```python
# More ML influence (50% ML, 50% historical)
generator = SetlistGenerator(
    session=session,
    rng=Random(42),
    use_ml_features=True,
    ml_placement_weight=0.5,    # 50% ML
    ml_transition_bonus=0.2,     # 20% transition boost
)

# Less ML influence (10% ML, 90% historical)
generator = SetlistGenerator(
    session=session,
    rng=Random(42),
    use_ml_features=True,
    ml_placement_weight=0.1,    # 10% ML
    ml_transition_bonus=0.05,   # 5% transition boost
)
```

#### Legacy Mode (No ML)

```python
# Exact behavior of pre-ML generator
generator = SetlistGenerator(
    session=session,
    rng=Random(42),
    use_ml_features=False,  # Disable all ML features
)
```

### API Usage

#### Default ML Mode

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2023,
    "num_sets": 2,
    "include_encore": true,
    "seed": 42
  }'
```

**Result**: Uses default ML settings (30% placement, 10% transition boost)

#### Custom ML Parameters

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2023,
    "num_sets": 2,
    "include_encore": true,
    "seed": 42,
    "use_ml_features": true,
    "ml_placement_weight": 0.5,
    "ml_transition_bonus": 0.2
  }'
```

**Result**: 50% ML influence, 20% transition boost

#### Legacy Mode via API

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2023,
    "num_sets": 2,
    "include_encore": true,
    "seed": 42,
    "use_ml_features": false
  }'
```

**Result**: Pure historical generation (pre-ML behavior)

### Side-by-Side Comparison

**Script**: `scripts/demo_ml_generation.py`

```python
from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator.core import SetlistGenerator
from random import Random

with session_scope() as session:
    seed = 42
    
    # Generate with legacy mode
    gen_legacy = SetlistGenerator(session, Random(seed), use_ml_features=False)
    legacy = gen_legacy.generate()
    
    # Generate with ML mode (same seed)
    gen_ml = SetlistGenerator(session, Random(seed), use_ml_features=True)
    ml_enhanced = gen_ml.generate()
    
    # Compare
    print("=== LEGACY MODE ===")
    for i, segment in enumerate(legacy.sets):
        print(f"Set {i+1}: {', '.join(segment.songs[:5])}...")
    
    print("\n=== ML MODE ===")
    for i, segment in enumerate(ml_enhanced.sets):
        print(f"Set {i+1}: {', '.join(segment.songs[:5])}...")
```

**Expected differences**:
- Songs appear more in their high-probability sets
- Transitions like Mike's → Weekapaug appear more often
- Overall "feel" more authentic to Phish patterns

---

## Performance & Testing

### Performance Metrics

| Metric | Legacy Mode | ML Mode | Delta |
|--------|-------------|---------|-------|
| **Initialization** | ~50ms | ~150ms | +100ms (one-time) |
| **Per-song selection** | ~0.5ms | ~0.7ms | +0.2ms |
| **Full setlist** | ~100ms | ~120ms | +20% |
| **Memory usage** | ~5MB | ~7MB | +2MB (features) |

**Conclusion**: Negligible impact for API usage (one init per server start)

### Testing Results

#### Regression Tests

✅ **All 28 existing tests pass** with zero modifications

**Test Suite**:
```bash
poetry run pytest tests/ -v
```

**Results**:
```
tests/test_generator.py::test_basic_generation PASSED
tests/test_generator.py::test_set_duration PASSED
tests/test_generator.py::test_encore_generation PASSED
... (25 more tests)
===== 28 passed in 4.32s =====
```

#### Manual Validation

Generated **~10 setlists** in both modes, observed:

**ML Mode Benefits**:
- Tweezer appears more in Set 2 (78% historical probability)
- Mike's Song → Weekapaug transitions prioritized
- Encore songs match historical patterns better
- Multi-home songs distributed naturally

**No Regressions**:
- All generated setlists valid
- No crashes or errors
- Duration constraints still met
- Dependency rules still enforced

#### Feature Loading Tests

```python
import time
from pathlib import Path
from phish_setlist_maker.analysis.feature_store import FeatureStore

# Test loading
store = FeatureStore(Path("data/analytics/features"))
start = time.time()
store.load()
elapsed = time.time() - start

print(f"Load time: {elapsed*1000:.1f}ms")
print(f"Songs loaded: {len(store._song_features)}")
print(f"Transitions loaded: {len(store._transitions)}")

# Results:
# Load time: 87.3ms
# Songs loaded: 389
# Transitions loaded: 166
```

### Known Limitations

#### 1. Feature Coverage

- **389/~973 songs** have ML features (most popular covered)
- Rare songs fall back to historical-only
- **Not a bug**: By design, focuses on high-impact songs

#### 2. Transition Coverage

- **166 transitions** tracked (high-confidence only)
- Many rare transitions not captured
- **Not a bug**: Avoids overfitting to noise

#### 3. Era Agnostic

- Same features used across all eras (1.0, 2.0, 3.0, 4.0)
- Doesn't capture era-specific patterns
- **Future work**: Era-specific models

#### 4. No Real-Time Learning

- Features are static (pre-computed)
- Don't update with new shows
- **Future work**: Incremental feature updates

---

## Future Enhancements

### Phase 2.2+: Sequence Models

**Markov Chains**:
- Multi-song context (A, B → C prediction)
- Set-level flow modeling
- Era-specific transition matrices

### Phase 2.3: Song Similarity

**Clustering**:
- Group songs by co-occurrence patterns
- Enable substitution when constraints tight
- "Songs like X" recommendations

### Phase 2.4: Predictive Endpoint

**`/predict` API**:
- Given tour context, forecast next show
- Probability-ranked predictions per set
- Back-testing on historical validation sets

### Phase 3: A/B Testing

**Quality Metrics**:
- Automated comparison legacy vs. ML
- User feedback collection
- Perplexity/likelihood scoring

---

## Configuration Reference

### Environment Variables

```bash
# Feature directory (optional, auto-detects if unset)
export ML_FEATURES_DIR="data/analytics/features"

# Enable/disable ML globally (optional, defaults true)
export USE_ML_FEATURES="true"
```

### Generator Defaults

**File**: `src/phish_setlist_maker/generator/core.py`

```python
DEFAULT_USE_ML_FEATURES = True
DEFAULT_ML_PLACEMENT_WEIGHT = 0.3
DEFAULT_ML_TRANSITION_BONUS = 0.1
```

**To change defaults**: Modify constants or use environment variables

### API Defaults

**File**: `src/phish_setlist_maker/api/schemas.py`

```python
class GenerateRequestModel(BaseModel):
    use_ml_features: bool = Field(default=True)
    ml_placement_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    ml_transition_bonus: float = Field(default=0.1, ge=0.0, le=1.0)
```

---

## Troubleshooting

### Features Not Loading

**Symptom**: Generator falls back to legacy mode unexpectedly

**Check**:
```bash
# Verify feature files exist
ls -lh data/analytics/features/

# Should show:
# song_features.parquet
# song_transitions.parquet
# ordering_constraints.parquet
# etc.
```

**Fix**: Rebuild features
```bash
poetry run python scripts/build_features.py
```

### Unexpected Behavior

**Symptom**: Generated setlists don't match expectations

**Debug**:
```python
# Add logging to see ML adjustments
import logging
logging.basicConfig(level=logging.DEBUG)

generator = SetlistGenerator(session, use_ml_features=True)
result = generator.generate()
# Check logs for placement/transition adjustments
```

### Performance Issues

**Symptom**: Generation takes too long

**Profile**:
```python
import cProfile
import pstats

with cProfile.Profile() as pr:
    generator.generate()
    
stats = pstats.Stats(pr)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

---

## Summary

Phase 2.1 successfully delivers:

✅ **ML-enhanced generation** with data-driven nudges  
✅ **Backward compatibility** (zero breaking changes)  
✅ **Fast performance** (<150ms overhead)  
✅ **Extensible architecture** (easy to add features)  
✅ **Production ready** (all tests pass)

**Next**: [Constraints System](./04-CONSTRAINTS-SYSTEM.md) - Ordering and dependency rules

---

*ML features are enabled by default. For legacy behavior, set `use_ml_features=False` in generator or API request.*
