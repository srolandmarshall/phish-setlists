# Venue & Tour Analysis Implementation Summary

**Date**: 2025-10-22  
**Status**: ✅ Complete

## What Was Built

### New Functions in `src/phish_setlist_maker/analysis/database.py`
1. **`load_venue_dataframe()`** - Exports venue metadata (name, location, coordinates, show counts)
2. **`load_tour_dataframe()`** - Exports tour metadata with date ranges and durations
3. **`build_venue_tendencies()`** - Aggregates per-venue statistics:
   - Show count
   - Total track count
   - Average show duration
   - Top 5 most-played songs

### New Scripts

#### `scripts/build_venue_tour_analysis.py`
Standalone script to generate venue/tour exports:
```bash
poetry run python scripts/build_venue_tour_analysis.py
```
Outputs:
- `data/analytics/venues.parquet` (764 venues)
- `data/analytics/tours.parquet` (124 tours)
- `data/analytics/venue_tendencies.parquet` (723 venues with stats)

#### `scripts/report_venue_analysis.py`
Human-readable report of venue tendencies:
```bash
poetry run python scripts/report_venue_analysis.py --top-n 15
```
Shows:
- Top venues by show count with location, stats, and top songs
- Notable tours with date ranges and show counts

### Updated Scripts

**`scripts/run_analytics_exports.py`** now includes venue/tour exports in the single-command pipeline:
```bash
poetry run python scripts/run_analytics_exports.py --use-primary
```

## Data Generated

### Core Exports
- **764 venues** with full metadata
- **124 tours** with date ranges
- **723 venue tendencies** (41 venues excluded due to no show data)

### Key Insights
- **Most played venue**: Madison Square Garden (87 shows, avg 178.5 min)
- **Longest average shows**: Ian McLean's Farm (340.9 min - festival), Big Cypress (327.1 min - millennium)
- **Era coverage**: 1.0 (23,273 tracks), 2.0 (2,121), 3.0 (9,759), 4.0 (4,091)

### Data Quality Notes
- 42 venues have zero average duration (early shows with missing duration metadata)
- All venues have at least one show
- Top songs list contains up to 5 most frequently played songs per venue

## Documentation

### New Files
- **`docs/ml/venue-analysis.md`** - Full report with snapshot data and use cases
- **`docs/ml/QUICKSTART.md`** - Single-page getting started guide

### Updated Files
- **`docs/ml/analytics-workspace.md`** - Added venue/tour script references
- **`AGENTS-ml.md`** - Marked Phase 0.3 as complete with venue/tour additions

## Testing

Created and ran integration test verifying:
- All parquet files load correctly
- Venue tendencies join properly with venue metadata
- Data quality constraints are met
- Sample analyses produce expected results

## Usage Examples

### In Python/Notebooks
```python
import pandas as pd

venues = pd.read_parquet("data/analytics/venues.parquet")
tendencies = pd.read_parquet("data/analytics/venue_tendencies.parquet")

# Find venues with most shows
top_venues = tendencies.nlargest(10, "show_count")

# Get venue details
merged = tendencies.merge(venues, on="venue_id")
msg_stats = merged[merged["venue_name"] == "Madison Square Garden"]
```

### For Generator Enhancement
Potential uses:
1. Weight song selection based on `top_songs` for specific venues
2. Target `avg_show_duration` when generating for known venues
3. Apply regional preferences by grouping venues by state/country
4. Use tour context to model song rotation within a tour

## Next Steps (Future Work)

### Analysis Opportunities
- Venue type classification (arena vs. theater vs. outdoor)
- Era-specific venue tendencies (how venues evolve over time)
- Geographic clustering of song preferences
- Tour momentum modeling (song rotation patterns)

### Generator Integration
- Add `--venue` flag to generator CLI
- Implement venue-aware song weighting
- Add tour context to `/generate` API endpoint
- Create venue recommendation system based on setlist preferences

## Phase 0.3 Completion Status

All items from AGENTS-ml.md Phase 0.3 are now complete:
- ✅ Core exporters (shows, tracks, songs)
- ✅ Venue exporters
- ✅ Tour exporters
- ✅ Staging tables (set_segments, song_transitions, song_set_frequencies)
- ✅ Venue tendencies aggregation
- ✅ CLI entrypoints
- ✅ Single-command pipeline
- ✅ Report scripts
- ✅ Documentation

**Phase 0 (Foundations) is complete. Ready for Phase 1 (Exploratory Analysis).**
