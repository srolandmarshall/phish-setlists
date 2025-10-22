# Analytics Workspace Setup

Updated: 2025-10-20

## Environment
- Dependencies for analytics work are captured in `pyproject.toml`:
  - `numpy`, `pandas`, `matplotlib`, `seaborn`, `scikit-learn`, `sqlalchemy-utils`
  - Developer extras include `jupyterlab` alongside the existing `notebook` package
- Install/update via `poetry install`.

## Database configuration
- Primary credentials: `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT`, `DB_NAME`
- Analytics workspace (optional): `ANALYTICS_DB_USER`, `ANALYTICS_DB_PASS`, `ANALYTICS_DB_HOST`, `ANALYTICS_DB_PORT`, `ANALYTICS_DB_NAME`
  - If analytics variables are absent, the helpers fall back to the primary database.
- Utility scripts:
  - `poetry run python scripts/bootstrap_analytics_db.py --create` to create the analytics database (uses `sqlalchemy_utils.create_database`).
  - `poetry run python scripts/bootstrap_analytics_db.py --drop --create` to recreate it from scratch.
  - `poetry run python scripts/audit_database.py` (with `ANALYTICS_DB_*` exported) to validate a fresh clone.
  - **`poetry run python scripts/run_analytics_exports.py --use-primary`** - **ONE-STEP export of all tables** (shows, tracks, songs, set segments, transitions, frequencies, trends, venues, tours).
  - `poetry run python scripts/export_analysis.py --table set_segments --out data/analytics/set_segments.parquet` to dump individual staging datasets.
  - `poetry run python scripts/report_set_placement.py --min-appearances 5` to emit per-set appearance stats.
  - `poetry run python scripts/report_song_transitions.py --min-count 10` to list high-confidence transitions.
  - `poetry run python scripts/report_venue_analysis.py --top-n 15` to display venue tendencies and tour stats.
  - `poetry run python scripts/build_trend_tables.py --tracks data/analytics/tracks.parquet --out-dir data/analytics/trends` for time-series tables (or use run_analytics_exports.py).
  - `poetry run python scripts/build_venue_tour_analysis.py` for venue/tour-specific exports (or use run_analytics_exports.py).

**Reminder:** populating the analytics database with data still requires running `pg_dump`/`pg_restore` or your preferred migration/process outside these scripts.

## Notebook workflow
- Notebooks live under `notebooks/ml/`; see the README in that directory for conventions.
- Launch Jupyter Lab with `poetry run jupyter lab`.
- Keep notebooks clean (limit stored outputs) and move reusable code into `src/phish_setlist_maker/analysis/`.
- Cheatsheet for the main libraries: `docs/ml/ml-libraries-cheatsheet.md`.

## Next steps
- Build shared analysis helpers (`src/phish_setlist_maker/analysis/database.py`, etc.) per Roadmap Step 0.3.
- Capture new audit snapshots in `docs/ml/schema-overview.md` whenever the data refreshes.
