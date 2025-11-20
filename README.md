# Phish Setlist Maker

## A Python Backend

A small, opinionated learning project for exploring Phish setlists and experimenting with automated setlist generation, now enhanced with ML-driven features.

This repository contains utilities, a smart generator, and notebooks used while learning Python, SQLAlchemy, and data-driven heuristics for assembling setlists. It is intentionally lightweight and best-suited for local experimentation.

**Data Attribution**: All Phish show and setlist data is sourced from [Phish.in](https://phish.in/), a comprehensive archive of Phish recordings and setlists. This project would not be possible without their incredible work maintaining this community resource. Phish.in data is provided under the MIT License.

## Features

For a complete list of features and recent improvements, see [docs/TOOLTIP-FEATURE.md](docs/TOOLTIP-FEATURE.md) and other documentation in the [docs/](docs/) directory.

**Highlights:**

- 🎸 **ML-Enhanced Generation** - Historical placement probabilities and transition patterns
- 🎵 **Interactive Tooltips** - Click songs for performance details from Phish.in (NEW!)
- 📱 **Mobile-Friendly** - Fully responsive design with touch-optimized UI
- 🎚️ **Jamminess Control** - Dial up or down jam intensity (0.0-1.0)
- 🎯 **Weighted Set Closers** - Authentic set-ending selections
- 📊 **40+ Years of Data** - Powered by comprehensive Phish.in archive
- 🔗 **Phish.in Integration** - Direct links to full shows
- 🎭 **Era-Aware** - Filter by 1.0, 2.0, 3.0, or 4.0 eras

Visit `/features` when running the app to see the complete feature list.

## Quick start

### Requirements

- Python 3.13 (project is developed against CPython 3.13)
- Poetry (dependency manager used for this project)
- A local Postgres database or SQL dump if you want to load historical data

### Setup

1. **Install dependencies with Poetry**:

```bash
poetry install
```

2. **Copy environment example and update Postgres credentials**:

```bash
cp .env.example .env
# edit .env to point to your local Postgres instance
```

3. **Verify ML features are available** (optional, for ML-enhanced mode):

```bash
ls -lh data/analytics/features/
# Should show: song_features.parquet, transition_lift.parquet, multi_home_songs.parquet
```

### Usage Options

#### Option 1: Run the FastAPI Server

Start the local development server:

```bash
# Simple start (http://localhost:8000)
poetry run server

# Or use the alias
poetry run http-start

# Custom host/port
poetry run server --port=8080
poetry run server --host=0.0.0.0 --port=3000

# Legacy/manual way (still works)
poetry run uvicorn phish_setlist_maker.api:app --reload
```

Then visit:

- **Interactive API docs**: http://localhost:8000/docs
- **Generate HTML setlist**: http://localhost:8000/generate
- **Health check**: http://localhost:8000/health

Example API requests:

```bash
# Generate with ML features (default behavior)
# Note: allow_previous_show=true by default (songs from last show allowed)
curl http://localhost:8000/generate

# Control jamminess (intensity): 0.0=tight/concise, 0.5=balanced, 1.0=extended jams
curl "http://localhost:8000/generate?jamminess=0.01"   # Tight (more songs, shorter versions)
curl "http://localhost:8000/generate?jamminess=0.99"   # Full Send (fewer songs, extended jams)

# Exclude songs from previous show
curl "http://localhost:8000/generate?allow_previous_show=false&seed=42"

# Disable ML features (legacy mode)
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"year": 2023, "num_sets": 2, "use_ml_features": false}'

# Generate with custom ML weights and jamminess
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2023,
    "num_sets": 2,
    "ml_placement_weight": 0.5,
    "ml_transition_bonus": 0.2,
    "jamminess": 0.75
  }'
```

#### Option 2: CLI Script (Legacy)

Generate a setlist directly (writes to `data/` folder):

```bash
poetry run python scripts/generate_setlist.py --playlist --html
```

**Command flags**:

- `--playlist` — produce an M3U playlist alongside the setlist
- `--html` — produce an HTML summary (tables + embedded player)
- `--allow-previous-show` — include songs from the most recent show when allowed by rules

#### Option 3: Demo ML Features

Compare legacy vs. ML-enhanced generation side-by-side:

```bash
poetry run python scripts/demo_ml_generation.py
```

### Outputs

Generated artifacts land in the `data/` directory by default (HTML, M3U, markdown summaries, and optional SQL dumps).

## Project layout

```
phish-setlist-maker/
├── scripts/               # CLI scripts and utilities
│   ├── generate_setlist.py         # Legacy CLI generator
│   ├── build_features.py           # Rebuild Phase 1 ML features
│   └── demo_ml_generation.py       # ML comparison demo
├── src/phish_setlist_maker/        # Core package
│   ├── api/                        # FastAPI application
│   │   ├── __init__.py             # Main app + routes
│   │   ├── schemas.py              # Pydantic request/response models
│   │   └── factories.py            # Request builders
│   ├── generator/                  # Setlist generation engine
│   │   ├── core.py                 # Main generator with ML integration
│   │   ├── rules.py                # Hard-coded rules & constraints
│   │   ├── historical.py           # Historical frequency queries
│   │   └── html.py                 # HTML rendering
│   ├── analysis/                   # ML & analytics modules
│   │   ├── feature_store.py        # Phase 2: Feature loading
│   │   ├── features.py             # Phase 1: Feature engineering
│   │   └── database.py             # Data extraction utilities
│   ├── service/                    # Business logic layer
│   │   ├── generation.py           # Orchestration for generation
│   │   └── playlist.py             # M3U playlist building
│   ├── models/                     # SQLAlchemy ORM models
│   ├── db.py                       # Database connection helpers
│   ├── config.py / constants.py    # Configuration values
│   └── static/                     # CSS/JS for HTML output
├── notebooks/                      # Jupyter notebooks
│   └── ml/                         # ML exploration notebooks
├── docs/                           # Documentation
│   ├── ml/                         # ML roadmap & reports
│   │   ├── phase1-report.md        # Phase 1 summary
│   │   ├── phase2-1-summary.md     # Phase 2.1 summary
│   │   └── phase2-plan.md          # Phase 2 implementation plan
│   └── figures/                    # Generated visualizations
├── data/                           # Generated artifacts & features
│   ├── analytics/features/         # Phase 1 ML feature tables
│   └── (various generated files)
└── tests/                          # Pytest test suite
```

## ML Features (Phase 1 & 2)

This project includes ML-enhanced generation capabilities based on historical analysis:

### Phase 1: Feature Engineering (Complete)

- **Song placement probabilities**: Per-set appearance rates for 389 songs
- **Transition lift scores**: 166 high-confidence song pairs (e.g., Mike's > Weekapaug)
- **Multi-home classification**: 246 songs with flexible set placement
- **Visualizations**: Heatmaps, entropy scores, temporal trends

Run feature engineering:

```bash
poetry run python scripts/build_features.py
```

### Phase 2: Generator Integration (Phase 2.1 Complete)

- **ML-enhanced mode**: Blends ML probabilities with historical weights (**enabled by default**)
- **Configurable**: Tune placement weight (default 30%) and transition bonus (default 10%)
- **Backward compatible**: Can disable with `use_ml_features=false`

See full ML roadmap: [`AGENTS-ml.md`](AGENTS-ml.md)

## Development notes

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=phish_setlist_maker

# Run specific test file
poetry run pytest tests/test_generator_duration.py -v
```

### Notebooks

Use the project's Poetry environment when running notebooks:

```bash
poetry run jupyter notebook

# Or JupyterLab
poetry run jupyter lab
```

### Code Style

- **Style**: Idiomatic modern Python (PEP 8)
- **Prefer**: Small pure functions, dataclasses, and type hints
- **Testing**: Add tests for new features; maintain 100% pass rate
- **DB Changes**: Use fixtures or temporary schemas for tests

### Practical Tips

- Keep large data files out of version control; use `data/` for local artifacts
- Regenerate ML features after significant data updates
- Check API docs at `/docs` when developing new endpoints

## Contributing

This is a small personal project, but contributions are welcome. A few guidelines:

- Open an issue to discuss larger changes before submitting a PR.
- Use imperative, concise commit messages (e.g. `Add random set-length sampler`).
- Reference related issues in PRs with `Refs #NN` or `Fixes #NN`.

## Data Sources & Attribution

This project relies on data from **[Phish.in](https://phish.in/)**, which provides comprehensive Phish setlist and performance information through their API.

- **Phish.in API**: https://phish.in/api-docs
- **License**: MIT License
- **Copyright**: © Phish.in contributors

We are deeply grateful to the Phish.in community for maintaining this invaluable resource. All setlist data, show dates, venue information, and song metadata used in this project originates from their archive.

## License

This project code is provided as-is for educational and personal use. The underlying data is provided by Phish.in under the MIT License.

**MIT License (Phish.in Data)**

Copyright (c) Phish.in contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
