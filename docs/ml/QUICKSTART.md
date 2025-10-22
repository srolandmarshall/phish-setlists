# Quick Start: Analytics & ML

**Last updated**: 2025-10-22

## TL;DR - Single Command
```bash
poetry run python scripts/run_analytics_exports.py --use-primary
```
This exports **everything** to `data/analytics/`:
- Core tables: shows, tracks, songs, venues, tours
- Staging tables: set_segments, song_transitions, song_set_frequencies, venue_tendencies
- Trend tables: song_year_counts, set_duration_summary, intro_outro_counts

## View Reports
```bash
# Set placement probabilities
poetry run python scripts/report_set_placement.py

# Song transitions
poetry run python scripts/report_song_transitions.py

# Venue tendencies
poetry run python scripts/report_venue_analysis.py
```

## What You Get

### Core Data (from database)
- **2,104 shows** (1983-2025)
- **39,244 tracks** across all shows
- **973 songs** in the repertoire
- **764 venues** worldwide
- **124 tours**

### Derived Analytics
- **Set segments**: 5,469 set-level summaries with song lists & durations
- **Song transitions**: 181 high-confidence pairs (min 10 occurrences)
- **Set frequencies**: 825 song-set probabilities for placement logic
- **Venue tendencies**: 723 venues with show counts, avg durations, top songs

### Trend Tables
- Song popularity by year
- Set duration patterns over time
- Common openers/closers per set

## Using the Data

### In Notebooks
```python
import pandas as pd

# Load any table
tracks = pd.read_parquet("data/analytics/tracks.parquet")
venues = pd.read_parquet("data/analytics/venues.parquet")
tendencies = pd.read_parquet("data/analytics/venue_tendencies.parquet")

# Join and analyze
merged = tracks.merge(venues, on="venue_id")
```

### For Generator Enhancement
The staging tables are designed to feed smarter generation logic:
- `song_set_frequencies.parquet` → weight songs by historical set placement
- `song_transitions.parquet` → nudge common pairings (Mike's → Hydrogen)
- `venue_tendencies.parquet` → venue-specific openers or duration targets

## Documentation

- **Full roadmap**: `AGENTS-ml.md`
- **Environment setup**: `docs/ml/analytics-workspace.md`
- **Set placement**: `docs/ml/set-placement-report.md`
- **Transitions**: `docs/ml/song-transitions-report.md`
- **Venues**: `docs/ml/venue-analysis.md`
- **Trends**: `docs/ml/trend-analysis.md`

## Next Steps

**Phase 0 (Foundations)** ✅ **COMPLETE**

**Phase 1 (Analysis)** - Ready for deeper exploration:
- Notebook experiments in `notebooks/ml/`
- Era-specific patterns
- Temporal trends
- Association rule mining

**Phase 2 (Models)** - Not yet started:
- Feature store for ML
- Sequence modeling (Markov chains, RNNs)
- `/predict` endpoint

Start exploring with:
```bash
poetry run jupyter lab
# Open notebooks/ml/ and load the Parquet files
```
