# ML & Data Analysis — Setup & Commands

**Last Updated**: November 7, 2025

---

## Quick Start: One Command

Generate all analytics and features:

```bash
poetry run python scripts/run_analytics_exports.py --use-primary
poetry run python scripts/build_features.py
```

This exports everything to `data/analytics/` and builds features in `data/analytics/features/`.

---

## Environment Setup

### Dependencies

All in `pyproject.toml`:

**Core**:
- `numpy` - Numerical arrays
- `pandas` - Tabular data manipulation
- `sqlalchemy` - Database ORM
- `fastparquet` - Parquet file format

**ML/Analytics**:
- `scikit-learn` - Classic ML algorithms
- `matplotlib` - Plotting
- `seaborn` - Statistical visualization

**Development**:
- `jupyterlab` - Interactive notebooks
- `pytest` - Testing

Install:
```bash
poetry install
```

### Database Configuration

**Two modes supported**:

1. **Primary** (production data):
   - `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT`, `DB_NAME`

2. **Analytics** (optional, for experimentation):
   - `ANALYTICS_DB_USER`, `ANALYTICS_DB_PASS`, etc.
   - Falls back to primary if not configured

### Bootstrap Scripts

```bash
# Create analytics database (separate DB)
poetry run python scripts/bootstrap_analytics_db.py --create

# Recreate from scratch
poetry run python scripts/bootstrap_analytics_db.py --drop --create

# Validate database structure
poetry run python scripts/audit_database.py
```

---

## Database Schema

### Core Performance Tables

**shows** (2,104 records)
- Span: 1983-09-21 to 2025-09-21
- Columns: id, date, venue_id, tour_id, duration, likes_count
- Unique constraint on date

**tracks** (39,244 records)
- All tracks across all shows
- Columns: id, show_id, title, position, duration, set, slug
- Unique on (show_id, position) and (show_id, slug)

**songs** (973 records)
- Repertoire songs
- Columns: id, title, slug, tracks_count, original, alias, lyrics, artist
- Some songs have aliases (e.g., "2001" → "Also Sprach Zarathustra")

**songs_tracks** (39,244 links)
- Association table
- Tracks: song_id, track_id, previous_performance_gap, next_performance_gap
- Records rotation and performance gaps

**venues** (764 records)
- Worldwide locations
- Columns: name, city, state, country, latitude, longitude, shows_count

**tours** (40+ records)
- Phish tours (e.g., "Summer 1994", "Fall 1995")

---

## Data Structure

### Analytics Exports

**Location**: `data/analytics/`

```
data/analytics/
├── tables/              # Core data
│   ├── shows.parquet
│   ├── tracks.parquet
│   ├── songs.parquet
│   ├── venues.parquet
│   ├── tours.parquet
│   └── ...
├── staging/             # Derived tables
│   ├── set_segments.parquet
│   ├── song_transitions.parquet
│   ├── song_set_frequencies.parquet
│   └── venue_tendencies.parquet
├── trends/              # Temporal patterns
│   ├── song_year_counts.parquet
│   ├── set_duration_summary.parquet
│   └── intro_outro_counts.parquet
└── features/            # ML features (built via build_features.py)
    ├── song_features.parquet
    ├── song_transitions.parquet
    ├── ordering_constraints.parquet
    ├── directional_transitions.parquet
    ├── cross_set_dependencies.parquet
    ├── set_ending_frequencies.parquet
    ├── set_ending_tracks.parquet
    ├── excluded_songs.csv
    └── ...
```

---

## Key Commands

### Export & Build

```bash
# Full analytics pipeline (ONE COMMAND)
poetry run python scripts/run_analytics_exports.py --use-primary

# Build ML features
poetry run python scripts/build_features.py

# Build visualizations
poetry run python scripts/visualize_analysis.py
```

### Analysis & Reports

```bash
# Set placement statistics
poetry run python scripts/report_set_placement.py --min-appearances 5

# Song transitions
poetry run python scripts/report_song_transitions.py --min-count 10

# Venue analysis
poetry run python scripts/report_venue_analysis.py --top-n 15

# Ordering constraints
poetry run python scripts/discover_ordering_constraints.py
```

### Testing

```bash
# All tests
poetry run pytest tests/ -v

# Generator tests only
poetry run pytest tests/test_generator.py -v

# Feature tests
poetry run python scripts/test_excluded_songs.py
poetry run python scripts/test_cross_set_dependency_unit.py
```

### Generation

```bash
# With ML features (default)
poetry run phish-setlist-maker generate --num-sets 2 --include-encore

# Legacy mode (heuristics only)
poetry run phish-setlist-maker generate --num-sets 2 --no-ml-features

# Era-specific
poetry run phish-setlist-maker generate --num-sets 2 --era 4.0
```

---

## Development Workflow

### Notebook Development

Work in `notebooks/ml/`:

```bash
poetry run jupyter lab
```

**Conventions**:
- Keep notebooks clean (limit stored outputs)
- Move reusable code to `src/phish_setlist_maker/analysis/`
- Use date prefixes: `20251022_feature_exploration.ipynb`
- Document findings in markdown cells

### Analysis Cycle

1. **Export fresh data**:
   ```bash
   poetry run python scripts/run_analytics_exports.py --use-primary
   ```

2. **Explore in notebook**:
   ```python
   import pandas as pd
   tracks = pd.read_parquet("data/analytics/tracks.parquet")
   # ... explore patterns
   ```

3. **Prototype features**:
   ```python
   def compute_feature(df):
       # ... logic
       return feature_df
   ```

4. **Migrate to production**:
   - Move to `src/phish_setlist_maker/analysis/features.py`
   - Add to `scripts/build_features.py`
   - Write tests
   - Document in reports

5. **Build features**:
   ```bash
   poetry run python scripts/build_features.py
   ```

6. **Integrate with generator**:
   - Load in `FeatureStore`
   - Apply constraints
   - Test with unit/integration tests

---

## Performance Profiling

```python
import time
import pandas as pd

# Time feature loading
start = time.time()
features = pd.read_parquet("data/analytics/features/song_features.parquet")
print(f"Load time: {time.time() - start:.3f}s")

# Memory usage
print(f"Memory: {features.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
```

---

## Next Steps

After setup, proceed to:

1. **[Feature Engineering](./02-FEATURES.md)** - Feature definitions and metrics
2. **[Constraints & Heuristics](./03-CONSTRAINTS-HEURISTICS.md)** - Generator rules
3. **[Project Roadmap](./04-ROADMAP.md)** - Future work

---

**Status**: Production Ready  
**Last Updated**: October 25, 2025
