## Phish Setlist Maker — Personal Code Improvement Roadmap

This mini-roadmap is tailored to your repository state (Oct 25, 2025). I read the core codebase (API, generator, historical analysis, feature store, service orchestration, ORM models, and tests) and created prioritized, actionable improvements with file pointers and time estimates so you can open small, reviewable PRs.

---

## Quick context (what I inspected)

- API entry: `src/phish_setlist_maker/api/__init__.py`, `api/cli.py`, `api/{dependencies,factories,schemas,serializers}.py`
- Generator: `src/phish_setlist_maker/generator/core.py`, `historical.py`, `rules.py`, `html.py`
- Feature store & FE: `src/phish_setlist_maker/analysis/feature_store.py`, `analysis/features.py`
- Service orchestration & playlists: `src/phish_setlist_maker/service/generation.py`, `playlist.py`, `tracks.py`, `catalog.py`, `segments.py`
- DB/config/models: `src/phish_setlist_maker/db.py`, `config.py`, `models/*.py`
- Tests: `tests/` (pytest configured via `pyproject.toml`), fixtures use in-memory SQLite.

Key notes: ML features are optional and loaded from `data/analytics/features/*.parquet`. The generator uses jamminess percentiles (p30/p50/p70/p90). Many heuristics exist (frequency caps, duration budget, adjacency/transition boosts). The codebase is overall well-organized and idiomatic.

---

## Prioritized improvements (small → medium → strategic)

Priority explains impact and gives exact edits to make.

### 1) Quick wins (0.5–2 days each)

- Add CI that runs pytest and a basic lint/typecheck: create `.github/workflows/ci.yml`.

  - Why: Prevents regressions, ensures tests pass for PRs. Repo already uses Poetry and pytest.
  - What to run: `poetry install` then `poetry run pytest -q` and `ruff check .` or `black --check` and optionally `mypy`.
  - Files: add `/.github/workflows/ci.yml`.
  - Est: 2–4 hours.

- Add `pre-commit` with `ruff`, `black`, and `isort` to keep style consistent.

  - Files: add `.pre-commit-config.yaml` and update `pyproject.toml` (optional docs entry).
  - Est: 1–2 hours.

- Add a minimal CI test that runs a lightweight generator smoke test (already in `tests/test_cli_smoke.py`). Ensure `pytest` workflow picks it up. If DB env required, keep tests using in-memory SQLite (they already do via `conftest.py`).
  - Files: existing tests + CI config.
  - Est: 1 hour.

### 2) Robustness & error-handling (1–3 days)

- Make `FeatureStore` and `SetlistGenerator` more forgiving when feature tables missing.

  - Problem: `SetlistGenerator.__init__` currently raises if the features dir doesn't exist when `use_ml_features=True`. In many local runs you'd prefer graceful fallback (warnings and disable ML features) instead of an exception.
  - Change: In `src/phish_setlist_maker/generator/core.py` and `src/phish_setlist_maker/analysis/feature_store.py`, add clearer logging and fallback behavior; expose a small helper `FeatureStore.missing()` or `FeatureStore.try_load()` that returns success boolean.
  - Files: `analysis/feature_store.py`, `generator/core.py`.
  - Est: 6–12 hours.

- Improve DB-config security in `config.py`.
  - Problem: `DatabaseSettings.url()` renders with password visible (hide_password=False). Avoid accidentally logging credentials in production flows; prefer optional param for hide password when printing.
  - Change: set default to hide password in render_as_string or only reveal for debug. Add a `__str__` that redacts password.
  - Files: `src/phish_setlist_maker/config.py`.
  - Est: 1–2 hours.

### 3) Tests and coverage (2–5 days)

- Add unit tests for edge cases in generator and feature store.

  - Targets:
    - `FeatureStore.load()` when some parquet files are missing → assert fallback state.
    - `SetlistGenerator` jamminess boundaries (0.0, 0.5, 1.0) and duration capping behavior.
    - Ordering/mandatory transition behavior (mock small transition table) to confirm violations are detected.
  - Files: new tests under `tests/test_feature_store.py`, `tests/test_generator_jamminess.py`.
  - Est: 1–3 days.

- Add integration test that generates a setlist and validates playlist artifact assembly using mocked `requests` (like existing tests). Expand to cover negative flows (remote fetch fails, missing tracks lookup).
  - Files: `tests/...` (leverage `responses` library already used).
  - Est: 1–2 days.

### 4) Medium-term improvements (3–7 days)

- Factor the generator internals into smaller, testable strategies.

  - Rationale: `SetlistGenerator._select_with_duration_budget` and `_weighted_pick` are large; extracting selection strategy and duration policy classes makes unit testing and future experimentation (bandit, beam search or ML policy) easier.
  - Files: split `src/phish_setlist_maker/generator/core.py` into `selection.py`, `duration_policy.py`, and thin `core.py` wrapper.
  - Est: 3–5 days.

- Add stronger typing across analysis/feature_store and generator interfaces.
  - Why: Many methods rely on untyped dicts/lists (parquet loads). Adding return types and Pydantic models (or TypedDicts) will reduce reasoning overhead and simplify tests.
  - Files: `analysis/feature_store.py`, `generator/core.py`, `service/*.py`.
  - Est: 2–4 days.

### 5) Strategic / long-term (1–3+ weeks)

- Lazy-loading / memory optimization for parquet features.

  - If features get larger, consider only loading index columns or using Dask / on-disk querying rather than reading all into memory.
  - Files: `src/phish_setlist_maker/analysis/feature_store.py` and data pipeline scripts.
  - Est: 1–3 weeks, depending on approach.

- Production readiness: containerized dev DB seed + e2e tests.
  - Add `docker-compose.dev.yml` with a lightweight Postgres and init script that loads a small sample dataset to run deterministic tests and manual dev cycles.
  - Est: 2–5 days.

---

## Low-risk concrete PRs (recommended order)

1. Add CI workflow that runs `poetry install` and `pytest` + `ruff` and `black` checks. (small)
2. Add `pre-commit` config + docs in README with local dev steps. (small)
3. Make `FeatureStore.load()` tolerant to missing files and return a `loaded` flag. Update `SetlistGenerator` to log and continue when ML assets are missing (fall back to heuristic-only mode). (medium)
4. Add unit tests for the above behavior. (medium)
5. Extract a small `duration_policy.py` with unit tests covering jamminess decisions. (medium)

Each PR should be small and focused—aim for <200 LOC changes per PR so reviews are fast.

---

## Suggested file-change checklist (exact files to edit)

- CI and formatting:
  - Add: `.github/workflows/ci.yml`, `.pre-commit-config.yaml`
- FeatureStore / generator fallbacks:
  - `src/phish_setlist_maker/analysis/feature_store.py`
  - `src/phish_setlist_maker/generator/core.py`
- DB redaction:
  - `src/phish_setlist_maker/config.py`
- Tests (new):
  - `tests/test_feature_store.py`
  - `tests/test_generator_jamminess.py`

---

## Risks & notes

- Changing generator heuristics can alter output behavior; keep behavior flags (feature toggles) and defaults unchanged. Add deprecation notes when modifying defaults.
- ML features depend on external parquet assets; treat them as optional inputs in both tests and runtime.

---

## Closing & next immediate step I can take for you

Pick one of the first three PR ideas and I will implement it in a branch and open a small patch:

- "Add CI + pytest workflow" (fast) — I can add the YAML and confirm it runs locally.
- "Make FeatureStore graceful on missing files" — I can implement the fallback and a unit test.
- "Add pre-commit config" — I can add config and a short README update.

Tell me which one to implement and I'll create the branch and PR-style patch here.

— Roadmap generated from direct inspection of source files on Oct 25, 2025.
