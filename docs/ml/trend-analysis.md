# Temporal Trends Roadmap

Initial deliverables for Phase 1.3:

- Time-series exports showing song play counts per year/era.
- Duration trends per set (validate runtime constraints against history).
- Notebooks exploring rolling popularity and intro/outro tendencies.

## Generating the tables

After exporting `tracks.parquet`, run:

```bash
poetry run python scripts/build_trend_tables.py --tracks data/analytics/tracks.parquet --out-dir data/analytics/trends
```

This produces:

- `song_year_counts.parquet`
- `set_duration_summary.parquet`
- `intro_outro_counts.parquet`

These tables feed upcoming notebooks (e.g., `notebooks/ml/20251020_trend_exploration.ipynb`).

Notebook starter: `notebooks/ml/20251020_trend_exploration.ipynb` loads the exported tables and sketches a few baseline plots (top songs per year, set duration trends, common openers). Use it as the jumping-off point for deeper analysis.
