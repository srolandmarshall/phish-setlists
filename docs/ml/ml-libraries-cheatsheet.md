# ML & Data Tooling Cheatsheet

Quick reminders for the Python stack used in this project.

## Core data handling
- **pandas** – tabular data manipulation (`DataFrame`). Use `read_parquet`, `groupby`, `merge`, `pivot`, etc. Built on NumPy.
- **fastparquet** – Parquet reader/writer used by pandas. Already wired via `to_parquet` / `read_parquet`.
- **NumPy** – numerical arrays; pandas relies heavily on it. Most math/array operations come from here.

## Visualization
- **matplotlib** – base plotting library. Direct control with `plt.figure`, `plt.plot`, etc.
- **seaborn** – statistical plots on top of matplotlib (e.g., `sns.lineplot`, `sns.barplot`). Automatically uses pandas DataFrames.

## Analytics / ML
- **scikit-learn** – classic ML algorithms and transformers. Use for clustering, regression, classification, model evaluation.
- **SQLAlchemy + pandas** – our pipelines pull data from Postgres into DataFrames (`analysis/database.py` helpers).

## Why this stack?
- Everything runs locally, no cloud dependencies.
- Works seamlessly inside notebooks (JupyterLab installed via Poetry).
- Parquet keeps analytics exports compact and fast to load.

For getting started:
1. Run `poetry run python scripts/run_analytics_exports.py --use-primary` to refresh Parquet datasets.
2. Open `notebooks/ml/20251020_trend_exploration.ipynb` in JupyterLab.
3. Use pandas + seaborn to explore; bring in scikit-learn once you’re ready for modeling.
