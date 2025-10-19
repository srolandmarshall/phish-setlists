# Phish Setlist Maker

A small, opinionated learning project for exploring Phish setlists and experimenting with automated setlist generation.

This repository contains utilities, a small generator, and notebooks used while learning Python, SQLAlchemy, and data-driven heuristics for assembling setlists. It is intentionally lightweight and best-suited for local experimentation.

## Highlights

- Generate synthetic setlists and companion playlists (M3U) and HTML summaries.
- Local-first: uses a Postgres database dump / local DB for historical data.
- Includes notebooks for interactive exploration and a handful of small utilities and models.

## Quick start

Requirements

- Python 3.13 (project is developed against CPython 3.13)
- Poetry (dependency manager used for this project)
- A local Postgres database or SQL dump if you want to load historical data

Recommended quick setup

1. Install dependencies with Poetry:

```bash
poetry install
```

2. Copy environment example and update Postgres credentials:

```bash
cp .env.example .env
# edit .env to point to your local Postgres instance
```

3. Generate a setlist (writes to the `data/` folder):

```bash
poetry run python scripts/generate_setlist.py --playlist --html
```

Command flags

- `--playlist` — produce an M3U playlist alongside the setlist
- `--html` — produce an HTML summary (tables + embedded player)
- `--allow-previous-show` — include songs from the most recent show when allowed by rules

Outputs

Generated artifacts land in the `data/` directory by default (HTML, M3U, markdown summaries, and optional SQL dumps).

## Project layout

- `scripts/` — thin CLI scripts (e.g., `generate_setlist.py`)
- `src/phish_setlist_maker/` — core package
  - `generator/` — setlist generation logic, rules, and HTML renderers
  - `models/` — SQLAlchemy models for shows, tracks, songs, venues, etc.
  - `db.py` — DB helpers and connection wiring
  - `config.py` / `constants.py` — configuration values
- `notebooks/` — interactive notebooks used during exploration
- `data/` — generated output and local SQL dumps (not all files are tracked in git)

## Development notes

- Coding style: idiomatic modern Python (PEP 8). Prefer small pure functions, dataclasses, and type hints.
- Tests: `pytest` is configured but the repo currently has minimal test coverage. Run tests with:

```bash
poetry run pytest
```

- Notebooks: use the project's Poetry environment when running notebooks:

```bash
poetry run jupyter notebook
```

Practical tips

- If you add or change DB-related code, prefer fixtures or temporary schemas for tests rather than touching production dumps.
- Keep large data files out of version control; use `data/` for local artifacts.

## Contributing

This is a small personal project, but contributions are welcome. A few guidelines:

- Open an issue to discuss larger changes before submitting a PR.
- Use imperative, concise commit messages (e.g. `Add random set-length sampler`).
- Reference related issues in PRs with `Refs #NN` or `Fixes #NN`.

## License

No license file is present in this repository. If you want to reuse code from here, please ask or add an explicit license.

---

If anything in this README should be expanded (examples, more usage notes, CI instructions), say which section and I'll add it.
