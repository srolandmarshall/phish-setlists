# ML & Data Analysis: Overview and Setup

**Last Updated**: 2025-10-23  
**Project**: Phish Setlist Maker

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [Quick Start](#quick-start)
3. [Environment Setup](#environment-setup)
4. [Database Schema](#database-schema)
5. [Data Pipeline](#data-pipeline)
6. [Development Workflow](#development-workflow)

---

## Project Overview

### Objective

Build a robust data + ML layer that:
1. **Deepens understanding** of historical set construction patterns
2. **Drives smarter generation** heuristics for realistic setlists
3. **Enables predictive capabilities** for forecasting and scenario evaluation

### Core Capabilities

The system provides:
- **Historical analysis** of 2,104+ shows spanning 1983-2025
- **Feature engineering** for song placement, transitions, and dependencies
- **ML-enhanced generation** with data-driven constraints
- **Predictive modeling** (future) for next-show forecasting

### Architecture

```
Data Sources (Postgres)
    ↓
Analytics Exports (Parquet)
    ↓
Feature Engineering (Python/Pandas)
    ↓
Feature Store (In-Memory Cache)
    ↓
Generator Integration (ML Constraints)
```

---

## Quick Start

### TL;DR - Single Command

Generate all analytics data:
```bash
poetry run python scripts/run_analytics_exports.py --use-primary
```

This exports **everything** to `data/analytics/`:
- Core tables: shows, tracks, songs, venues, tours
- Staging tables: set_segments, song_transitions, song_set_frequencies, venue_tendencies
- Trend tables: song_year_counts, set_duration_summary, intro_outro_counts
- Feature tables: song_features, ordering_constraints, cross_set_dependencies

### Generate ML Features

Build all Phase 1 feature tables:
```bash
poetry run python scripts/build_features.py
```

Outputs to `data/analytics/features/`:
- `song_features.parquet` - 389 songs with placement probabilities
- `song_transitions.parquet` - 181 high-confidence transitions
- `ordering_constraints.parquet` - 686 mandatory song orderings
- `cross_set_dependencies.parquet` - Cross-set rules (Tweezer Reprise, etc.)

### View Reports

```bash
# Set placement probabilities
poetry run python scripts/report_set_placement.py

# Song transitions
poetry run python scripts/report_song_transitions.py

# Venue tendencies
poetry run python scripts/report_venue_analysis.py

# Ordering constraints
poetry run python scripts/discover_ordering_constraints.py
```

---

## Environment Setup

### Dependencies

All analytics dependencies are in `pyproject.toml`:

**Core Libraries**:
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

Install with:
```bash
poetry install
```

### Database Configuration

Two database modes supported:

**Primary Database** (production data):
- `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT`, `DB_NAME`

**Analytics Database** (optional, for experimentation):
- `ANALYTICS_DB_USER`, `ANALYTICS_DB_PASS`, etc.
- Falls back to primary if not configured

### Bootstrap Scripts

```bash
# Create analytics database (if using separate DB)
poetry run python scripts/bootstrap_analytics_db.py --create

# Recreate from scratch
poetry run python scripts/bootstrap_analytics_db.py --drop --create

# Validate database structure
poetry run python scripts/audit_database.py
```

---

## Database Schema

### Core Performance Tables

#### shows
- **2,104 shows** (1983-09-21 to 2025-09-21)
- Columns: id, date, venue_id, tour_id, duration, likes_count, etc.
- Unique constraint on `date`
- Links to venues and tours

#### tracks
- **39,244 tracks** across all shows
- Columns: id, show_id, title, position, duration, set, slug, etc.
- Unique on `(show_id, position)` and `(show_id, slug)`
- Links to songs via `songs_tracks`

#### songs
- **973 songs** in the repertoire
- Columns: id, title, slug, tracks_count, original, alias, lyrics, artist
- Some songs have aliases (e.g., "2001" → "Also Sprach Zarathustra")

#### songs_tracks (association)
- **39,244 song-track links**
- Columns: id, song_id, track_id, previous_performance_gap, next_performance_gap
- Tracks song rotation and gaps between performances

### Supporting Tables

#### venues
- **764 venues** worldwide
- Columns: name, city, state, country, latitude, longitude, shows_count

#### tours
- **124 tours**
- Columns: name, starts_on, ends_on, shows_count

### Data Quality Metrics

From database audit (2025-10-20):
```
Total shows             : 2,104
Date range              : 1983-12-02 → 2025-09-21
Total tracks            : 38,499
Tracks w/ zero duration : 1,794 (4.66%)
Tracks missing set label: 0 (0.00%)
Total songs             : 973
Songs with alias        : 13 (1.34%)
Song↔Track links        : 39,244
```

### Schema Notes

**ORM/Schema Drift**:
- Some fields exist in Rails schema but not Python ORM (timestamps, audio_status)
- Some fields exist in Python ORM but not Rails schema (metadata_cache, waveform_png_data)
- This is documented but doesn't impact analytics work

---

## Data Pipeline

### Export Flow

```
Postgres Database
    ↓
[SQLAlchemy Exporters]
    ↓
Core Tables (Parquet)
    ↓
[Materialized Views]
    ↓
Staging Tables (Parquet)
    ↓
[Feature Engineering]
    ↓
Feature Tables (Parquet)
```

### Core Exporters

Located in `src/phish_setlist_maker/analysis/database.py`:

**Base Tables**:
- `load_show_dataframe()` - Show metadata
- `load_track_dataframe()` - Track details with songs
- `load_song_dataframe()` - Song catalog
- `load_venue_dataframe()` - Venue metadata
- `load_tour_dataframe()` - Tour information

**Staging Tables**:
- `build_set_segments()` - Set-level summaries (5,469 sets)
- `build_song_transitions()` - Song-to-song pairs (181 high-confidence)
- `build_song_set_frequencies()` - Placement probabilities (825 entries)
- `build_venue_tendencies()` - Venue statistics (723 venues)

**Trend Tables**:
- `build_song_year_counts()` - Popularity over time
- `build_set_duration_summary()` - Duration patterns
- `build_intro_outro_counts()` - Common openers/closers

### Output Format

All exports use **Parquet** format:
- Compact storage (~10% of CSV size)
- Fast loading (<100ms for most tables)
- Preserves data types
- Compatible with pandas, Spark, DuckDB

### Directory Structure

```
data/analytics/
├── shows.parquet           # Base data
├── tracks.parquet
├── songs.parquet
├── venues.parquet
├── tours.parquet
├── set_segments.parquet    # Staging
├── song_transitions.parquet
├── song_set_frequencies.parquet
├── venue_tendencies.parquet
├── trends/                 # Temporal analysis
│   ├── song_year_counts.parquet
│   ├── set_duration_summary.parquet
│   └── intro_outro_counts.parquet
└── features/               # ML features
    ├── song_features.parquet
    ├── song_transitions.parquet
    ├── ordering_constraints.parquet
    ├── directional_transitions.parquet
    ├── cross_set_dependencies.parquet
    └── excluded_songs.csv
```

---

## Development Workflow

### Notebook Development

Notebooks live in `notebooks/ml/`:
```bash
poetry run jupyter lab
```

**Conventions**:
- Keep notebooks clean (limit stored outputs)
- Move reusable code to `src/phish_setlist_maker/analysis/`
- Use clear date prefixes: `20251022_feature_exploration.ipynb`
- Document key findings in markdown cells

### Analysis Workflow

Typical development cycle:

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
   # In notebook, test new feature logic
   def compute_new_feature(df):
       # ... feature logic
       return feature_df
   ```

4. **Migrate to production**:
   - Move function to `src/phish_setlist_maker/analysis/features.py`
   - Add to `scripts/build_features.py`
   - Add tests
   - Document in reports

5. **Generate features**:
   ```bash
   poetry run python scripts/build_features.py
   ```

6. **Integrate with generator**:
   - Load features in `FeatureStore`
   - Apply constraints in generator
   - Test with unit/integration tests

### Testing

```bash
# Run all tests
poetry run pytest tests/ -v

# Run specific test
poetry run pytest tests/test_generator.py -v

# Test feature loading
poetry run python scripts/test_cross_set_dependency_unit.py

# Generate test setlists
poetry run phish-setlist-maker generate --num-sets 2 --include-encore
```

### Performance Profiling

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

## Key Commands Reference

### Export & Analysis
```bash
# Full analytics pipeline (ONE COMMAND)
poetry run python scripts/run_analytics_exports.py --use-primary

# Build ML features
poetry run python scripts/build_features.py

# Build visualizations
poetry run python scripts/visualize_analysis.py
```

### Reports
```bash
# Set placement stats
poetry run python scripts/report_set_placement.py --min-appearances 5

# Transition analysis
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

# Generator tests
poetry run pytest tests/test_generator.py -v

# Feature tests
poetry run python scripts/test_excluded_songs.py
poetry run python scripts/test_cross_set_dependency_unit.py
```

### Generation
```bash
# Generate with ML features (default)
poetry run phish-setlist-maker generate --num-sets 2 --include-encore

# Legacy mode (no ML)
poetry run phish-setlist-maker generate --num-sets 2 --no-ml-features
```

---

## Next Steps

After setup, proceed to:

1. **[Feature Engineering Guide](./02-FEATURE-ENGINEERING.md)** - Deep dive into ML features
2. **[Generator Integration](./03-GENERATOR-INTEGRATION.md)** - How features drive generation
3. **[Constraints System](./04-CONSTRAINTS-SYSTEM.md)** - Ordering, dependencies, exclusions
4. **[Project Roadmap](./05-ROADMAP-AND-FUTURE.md)** - Past, present, and future work

---

## Resources

### Documentation
- **ML cheatsheet**: Common pandas/numpy/sklearn patterns
- **Schema overview**: Detailed table documentation
- **Phase reports**: Feature engineering results and insights

### External Links
- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [Scikit-learn Guide](https://scikit-learn.org/stable/user_guide.html)
- [Parquet Format](https://parquet.apache.org/docs/)

---

*This documentation is maintained alongside the codebase. For updates, see `AGENTS-ml.md` or individual feature documents.*
