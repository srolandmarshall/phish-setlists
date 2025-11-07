# ML & Data Analysis — Feature Engineering

**Last Updated**: November 7, 2025

---

## Overview

Feature engineering transforms raw setlist data into meaningful patterns for intelligent generation.

### Generated Features

| File | Records | Description |
|------|---------|-------------|
| `song_features.parquet` | 389 | Placement probabilities per set |
| `song_transitions.parquet` | 181 | High-confidence song transitions |
| `ordering_constraints.parquet` | 686 | Mandatory song orderings |
| `directional_transitions.parquet` | 33 | Adjacent sequence rules |
| `cross_set_dependencies.parquet` | 1 | Cross-set rules (Tweezer/Reprise) |
| `set_ending_frequencies.parquet` | 650 | Set-ending selection probabilities |
| `set_ending_tracks.parquet` | 5,761 | Actual set-ending track IDs |
| `excluded_songs.csv` | 12 | Non-musical content |

---

## Song Placement Features

### Set Placement Probability

**Metric**: `P(song in setX) = appearances_in_setX / total_appearances`

**Example**:
```python
{
    "song": "Tweezer Reprise",
    "set1": 0.184,      # 18.4% in Set 1
    "set2": 0.189,      # 18.9% in Set 2
    "set3": 0.000,      # Never in Set 3
    "encore": 0.626     # 62.6% in encore (primary home)
}
```

### Set Entropy (Versatility)

**Formula**: `H = -Σ p_i * log2(p_i)` across all sets

**Interpretation**:
- **High (>1.5 bits)**: Versatile across sets
- **Low (<0.5 bits)**: Set-specific specialist

**Top Versatile**: Icculus (1.894), Sanity (1.848), La Grange (1.846)

**Specialists**: Sleeping Monkey (0.0), Tweezer Reprise (0.0), Alumni Blues (0.078)

### Multi-Home Classification

**Songs appearing in 2+ sets with ≥15% probability**: 246 songs (63% of active repertoire)

**Examples**:

| Song | Set 1 | Set 2 | Set 3 | Encore | Status |
|------|-------|-------|-------|--------|--------|
| Harry Hood | 48.0% | 74.3% | 3.4% | 6.7% | Multi |
| Character Zero | 34.5% | 36.6% | 0.7% | 28.0% | Multi |
| Foam | 86.5% | 12.5% | 0.6% | 0.3% | Specialist |

---

## Transition Analysis

### Song Transition Patterns

**181 high-confidence transitions** discovered with lift analysis.

**Top 5 Iconic Sequences**:
1. Mike's Song → Weekapaug Groove (511 times, 99.4%)
2. I Am Hydrogen → Weekapaug Groove (339 times, 97.9%)
3. Mike's Song → I Am Hydrogen (334 times, 98.6%)
4. The Oh Kee Pa Ceremony → Suzy Greenberg (133 times, 98.4%)
5. Colonel Forbin's Ascent → Fly Famous Mockingbird (124 times, 94.9%)

**Pattern Types**:
- **Sandwich Suites**: Mike's → Hydrogen → Weekapaug
- **Story Songs**: Forbin's → Mockingbird
- **Jam Chains**: Tweezer → YEM, Tweezer → Harry Hood
- **Classic Pairs**: Horse → Silent, Oh Kee Pa → Suzy

---

## Ordering Constraints

### Mandatory Pairings (686 rules)

When certain songs appear together in a set, one must precede the other.

**Set 1 Specialists** (>80% probability):
- Foam (86.5%)
- Divided Sky (82.7%)
- Stash (81.8%)

**Set 2 Specialists**:
- Hold Your Head Up (85.0%)
- Also Sprach Zarathustra (82.9%)
- Tweezer (78.0%)

**Encore Lock-ins**:
- Sleeping Monkey (76.0%)
- Tweezer Reprise (62.6%)
- Rocky Top (57.5%)
- Fire (52.9%)

---

## Temporal Patterns

### Song Popularity Trends

Songs rise and fall in frequency over different eras:

**Era Definitions**:
- **1.0** (1983-1999): Classic - Foundation era
- **2.0** (2000-2004): Return - Transition after breakup
- **3.0** (2009-2021): Modern - Digital era
- **4.0** (2021+): Current - Recent shows

**Era-Specific Availability**:
- "I Am the Walrus" (Beatles cover) - Primarily 4.0 era
- Classic originals available across all eras
- Recent songs limited to 3.0/4.0

### Venue Tendencies

**764 venues** analyzed for location-specific patterns:
- Some venues favor particular song types
- Geography influences setlist composition
- Venue history affects band decisions

---

## Set-Ending Analysis

### Set-Ending Frequencies

**650 song-set combinations** with ending probabilities.

**Top Set 1 Enders**:
1. Run Like an Antelope: 192 times
2. David Bowie: 156 times
3. Cavern: 100 times
4. Possum: 89 times
5. Golgi Apparatus: 86 times

**Set-Ending Track Selection**:
- 5,761 total set-ending tracks
- Set 1: 1,958 tracks (224 unique songs)
- Set 2: 1,771 tracks (199 unique songs)
- Encore: 1,719 tracks (195 unique songs)
- **Set 2 ↔ Encore**: Bidirectional pool (3,490 shared)

---

## Cross-Set Dependencies

### Tweezer Reprise Rule

**Rule**: Tweezer Reprise cannot appear in encore unless Tweezer was in Set 1, 2, or 3.

**Confidence**: 0.95 (95% of performances follow this)

**Framework**:
```python
@dataclass
class CrossSetDependency:
    dependent_song: str        # "Tweezer Reprise"
    required_song: str         # "Tweezer"
    target_set: str           # "encore"
    required_sets: list[str]  # ["set1", "set2", "set3"]
    confidence: float         # 0.95
```

---

## Excluded Songs

### 12 Non-Musical Entries

Filtered from generation:

**Meta** (6): Banter, Jam, Narration, Rhombus Narration, Intro, Outro

**Situational** (4): Happy Birthday, Birthday, Audience Chess Move, Thanksgiving

**Technical** (2): Soundcheck, Tuning

---

## Feature Loading & Caching

### FeatureStore Architecture

**Location**: `src/phish_setlist_maker/analysis/feature_store.py`

**Behavior**:
- Loads all parquets on first access
- Caches in memory for subsequent calls
- Returns `None` if feature unavailable
- Graceful fallback if parquet missing

**Graceful Fallback**:
- Features dir missing → Warning log, continue with heuristics
- Individual parquet missing → Skip that feature, use others
- No exceptions in production

### Integration with Generator

Generator accesses features through `FeatureStore`:

```python
features = self._feature_store.get_song_features(song_title)
if features:
    # Use feature data
    set_placement = features.set_placement_probability
else:
    # Fall back to heuristics
    pass
```

---

## Building Features

```bash
# One-time build (or after database updates)
poetry run python scripts/build_features.py
```

**Output**:
```
Building features...
  → song_features.parquet
  → song_transitions.parquet
  → ordering_constraints.parquet
  → cross_set_dependencies.parquet
  → set_ending_frequencies.parquet
  → set_ending_tracks.parquet
  ✅ Complete
```

---

## Validation

### Frequency Analysis Tool

```bash
# Generate 200 setlists and analyze
poetry run python scripts/analyze_generation_frequency.py -n 200 --compare-historical
```

**Reports**:
- Song appearance rates
- Deviation from historical baseline
- Outlier detection
- Set-closer statistics

---

## Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Feature loading | ~150ms (one-time) | Cached after first load |
| Song lookup | <1ms | Parquet indexed |
| Transition check | <1ms | Per candidate |
| Full generation (2 sets) | ~500ms | Includes all checks |

---

**Status**: Production Ready  
**Last Updated**: October 24, 2025
