# ML Notebook Workspace

This folder hosts exploratory notebooks that drive the analytics/ML roadmap.

- Launch with `poetry run jupyter lab` (preferred) or `poetry run jupyter notebook`.
- Stick to lightweight outputs; clear large cells before committing.
- Expect notebooks to rely on either the primary DB credentials (`DB_*`) or the analytics clone (`ANALYTICS_DB_*`). Use the helper in `scripts/bootstrap_analytics_db.py` to prepare the latter.
- Common helpers (query utilities, plotting styles) should live in Python modules under `src/phish_setlist_maker/analysis/` so they are importable from both notebooks and tests.

Notebook naming convention: `YYYYMMDD_<short-topic>.ipynb` to keep chronological order.
