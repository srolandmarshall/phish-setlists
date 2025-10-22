# Phase 1 Analysis Report: Feature Engineering & Exploratory Analysis

**Date**: 2025-10-22  
**Status**: ✅ Complete

## Overview

Phase 1 focused on extracting meaningful features from historical setlist data to enable smarter generation and future ML modeling. We computed entropy metrics, identified transition patterns, and built a feature store ready for integration with the generator.

## What Was Built

### 1. Feature Engineering Library (`src/phish_setlist_maker/analysis/features.py`)

Four core functions:

#### `compute_set_entropy()`
Calculates Shannon entropy for song set placement:
- **High entropy** (>1.5 bits): Versatile songs that appear across multiple sets
- **Low entropy** (<0.5 bits): Set-specific songs with predictable placement

Example: Icculus (1.894 bits) appears nearly equally across all sets, while Tweezer Reprise (~0 bits) is almost exclusively an encore song.

#### `compute_transition_lift()`
Measures how much more likely a transition is than random chance:
- **Lift = P(A→B) / (P(A) × P(B))**
- Lift > 1 indicates a meaningful association
- Lift >> 100 suggests a "composed" transition (nearly always together)

Top lift scores:
- **Swept Away → Steep**: 473.6× (virtually always paired)
- **Colonel Forbin's → Mockingbird**: 393.4×
- **TMWSIY → Avenu Malkenu**: 223.1×

#### `identify_multi_home_songs()`
Finds songs that appear in multiple sets with significant probability (≥15%).

Result: **246 songs** (63% of repertoire) are multi-home, making them flexible placement options for the generator.

#### `build_song_features()`
Consolidates all features into a single wide-format table with columns:
- `song_effective_title`
- `set1`, `set2`, `set3`, `encore` (probabilities)
- `set_entropy`
- `total_appearances`

### 2. Feature Generation Script (`scripts/build_features.py`)

Single command to build all feature tables:
```bash
poetry run python scripts/build_features.py
```

Outputs to `data/analytics/features/`:
- `song_features.parquet` (389 songs × 7 features)
- `song_set_entropy.parquet`
- `multi_home_songs.parquet`
- `transition_lift.parquet`

### 3. Visualization Script (`scripts/visualize_analysis.py`)

Generates Phase 1 figures saved to `docs/figures/`:

#### Set Placement Heatmap
Shows top 30 songs with their probability distribution across sets. Reveals clear patterns like:
- YEM and Possum are versatile (appear in multiple sets)
- Tweezer Reprise strongly favors encore
- Mike's Song and Weekapaug dominate Set 2

#### Entropy Distribution
Histogram of set entropy scores plus top/bottom 10 songs by versatility.

#### Transition Network
Arrow diagram showing top 20 transitions by lift. Arrow thickness represents lift strength.

#### Temporal Trends
Line plot of top 10 songs' popularity over time (1983-2025), revealing:
- Era-specific song rotation
- Peak popularity periods
- Modern staples vs. retired classics

## Key Insights

### Set Placement Patterns

**Set 1 Specialists** (>80% probability):
- Stash (81.8%)
- Divided Sky (82.7%)
- Foam (86.5%)

**Set 2 Specialists**:
- Also Sprach Zarathustra (82.9%)
- Hold Your Head Up (85.0%)
- Tweezer (78.0%)

**Encore Lock-ins**:
- Tweezer Reprise (62.6%)
- Sleeping Monkey (76.0%)
- Rocky Top (57.5%)

**Most Versatile Songs** (high entropy):
1. Icculus (1.894 bits) - equally likely in any set
2. Sanity (1.848 bits)
3. La Grange (1.846 bits)
4. Whipping Post (1.807 bits)
5. Banter (1.774 bits)

### Transition Strength

**Composed Sequences** (lift >200):
- Swept Away → Steep (473.6)
- Colonel Forbin's Ascent → Fly Famous Mockingbird (393.4)
- TMWSIY → Avenu Malkenu (223.1)
- The Horse → Silent in the Morning (213.8)
- Letter to Jimmy Page → Alumni Blues (211.1)

**Strong Associations** (lift 50-200):
- Mike's Song → I Am Hydrogen (varies by set)
- I Am Hydrogen → Weekapaug Groove
- The Oh Kee Pa Ceremony → Suzy Greenberg

### Multi-Home Songs

**246 songs** (63% of active repertoire) appear in 2+ sets with ≥15% probability. Examples:
- **A Day in the Life**: 3 sets (encore, set1, set2)
- **Harry Hood**: Strong in both set1 and set2
- **Character Zero**: Appears in set1, set2, and encore

These are ideal candidates for "wildcard" slots in generation where placement flexibility is desired.

## Generator Integration Opportunities

### Immediate Use Cases

1. **Set Placement Filtering**
   - Use `song_features.parquet` probabilities to weight song selection per set
   - Reject songs with <5% historical probability in the target set (configurable threshold)
   - Example: Don't place Tweezer Reprise in Set 1

2. **Transition Nudges**
   - Load `transition_lift.parquet` at startup
   - Apply soft bonus to high-lift transitions (e.g., +0.1 weight if lift >50)
   - Hard-code lift >200 transitions as mandatory sequences (already implemented for Mike's > Hydrogen)

3. **Entropy-Based Flexibility**
   - Use high-entropy songs as "gap fillers" when duration targets are tight
   - Reserve low-entropy songs for their canonical sets only

4. **Multi-Home Awareness**
   - Tag songs as "flexible" vs. "set-specific" in the generator
   - Use flexible songs when balancing set durations across the show

### Configuration Flags (Proposed)

Add to generator CLI/API:
```python
--use-ml-features          # Enable feature-based weighting
--transition-lift-threshold 50.0  # Minimum lift for auto-pairing
--entropy-threshold 1.0    # Songs above this are "versatile"
--strict-placement         # Reject songs outside their primary set
```

## Phase 1 Completion Checklist

✅ **1.1 Set Placement Profiling**
- Histograms/heatmaps generated
- Multi-home songs identified
- Entropy metrics computed
- Features saved to `song_features.parquet`

✅ **1.2 Transition & Dependency Mining**
- Lift metrics computed for all transitions
- Top transitions documented
- `transition_lift.parquet` ready for generator consumption

✅ **1.3 Temporal Trend Analysis**
- Trend tables built in Phase 0
- Temporal visualization created
- Song popularity trends documented

## Artifacts Generated

### Feature Tables
```
data/analytics/features/
├── song_features.parquet          (389 songs, comprehensive)
├── song_set_entropy.parquet       (entropy scores)
├── multi_home_songs.parquet       (246 flexible songs)
└── transition_lift.parquet        (181 transitions)
```

### Visualizations
```
docs/figures/
├── set_placement_heatmap.png      (top 30 songs by set)
├── entropy_distribution.png       (versatility analysis)
├── transition_network.png         (top 20 transitions)
└── temporal_trends.png            (top 10 songs over time)
```

### Scripts
```
scripts/
├── build_features.py              (feature generation)
└── visualize_analysis.py          (Phase 1 figures)
```

## Statistics Summary

- **389 songs** with complete feature vectors
- **246 multi-home songs** (63% of repertoire)
- **181 transitions** with lift >1.0 (min count 10)
- **Entropy range**: 0.0 to 1.894 bits
- **Top lift**: 473.6 (Swept Away → Steep)

## Next Steps: Phase 2

Phase 1 provides the foundation for Phase 2 work:

1. **Feature Store Integration**
   - Lazy-load features in FastAPI app (`app.state.features`)
   - Add feature version tracking

2. **Generator Heuristics Upgrade**
   - Implement probability-weighted sampling
   - Add transition lift bonuses
   - Introduce entropy-based flexibility logic

3. **Sequence Modeling** (optional)
   - Train Markov chains per era
   - Experiment with RNN/LSTM for next-song prediction
   - Build `/predict` endpoint prototype

4. **A/B Testing Framework**
   - Generate setlists with/without ML features
   - Collect user feedback
   - Measure "realism" via perplexity/likelihood

**Phase 1 is complete. Phase 2 (Models & Integration) is ready to begin.**
