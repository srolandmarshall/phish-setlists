# Phish Setlist Maker — Backend Reference

**Last Updated**: November 7, 2025  
**Scope**: Backend architecture, deployment, heuristics, and development roadmap

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Heuristics](#core-heuristics)
3. [Feature System](#feature-system)
4. [Deployment Guide](#deployment-guide)
5. [Development Roadmap](#development-roadmap)

---

## Architecture Overview

### Project Structure

**API & CLI**:
- `src/phish_setlist_maker/api/__init__.py` - FastAPI entry point
- `src/phish_setlist_maker/api/cli.py` - Command-line interface
- `src/phish_setlist_maker/api/{dependencies,factories,schemas,serializers}.py` - Request/response handling

**Generator Core**:
- `src/phish_setlist_maker/generator/core.py` - Main generation logic
- `src/phish_setlist_maker/generator/historical.py` - Historical analysis
- `src/phish_setlist_maker/generator/rules.py` - Generation rules
- `src/phish_setlist_maker/generator/html.py` - Output formatting

**Analysis & ML**:
- `src/phish_setlist_maker/analysis/feature_store.py` - Feature loading & caching
- `src/phish_setlist_maker/analysis/features.py` - Feature engineering
- `src/phish_setlist_maker/analysis/database.py` - Analytics exports

**Service Layer**:
- `src/phish_setlist_maker/service/generation.py` - Orchestration
- `src/phish_setlist_maker/service/playlist.py` - Playlist assembly
- `src/phish_setlist_maker/service/tracks.py` - Track selection
- `src/phish_setlist_maker/service/catalog.py` - Song catalog
- `src/phish_setlist_maker/service/segments.py` - Segment handling

**Database & Config**:
- `src/phish_setlist_maker/db.py` - Database connections
- `src/phish_setlist_maker/config.py` - Configuration & secrets
- `src/phish_setlist_maker/models/*.py` - ORM models

**Testing**:
- `tests/` - Pytest suite with in-memory SQLite fixtures
- `conftest.py` - Shared test configuration

### Data Flow

```
Database (Postgres/SQLite)
    ↓
Analytics Pipeline (scripts/)
    ↓
Parquet Exports (data/analytics/)
    ↓
Feature Store (In-Memory Cache)
    ↓
Generator (Core Logic)
    ↓
Service Layer (Orchestration)
    ↓
API Response
```

---

## Core Heuristics

### 1. Frequency Caps

**Problem**: Rare songs appearing too frequently in generation.

**Solution**: Weight scaling for songs with low historical appearance counts.

**Implementation**:
- Songs with <30 appearances: Weight × 0.25 (75% reduction)
- Songs with 30-49 appearances: Weight × 0.5 (50% reduction)
- Songs with 50+ appearances: No adjustment

**Location**: `src/phish_setlist_maker/generator/core.py` in `_weighted_pick()`

**Era-Aware Filtering**:
- "I Am the Walrus" only allowed in 4.0 era generation
- Prevents anachronistic song selection

### 2. Duration Budget Management

**Objective**: Generate setlists within realistic time constraints.

**Jamminess Control**:
- Uses percentiles: p30, p50, p70, p90 of historical duration
- Maps jamminess score (0.0-1.0) to duration multipliers
- Dynamically adjusts song pool based on remaining time

**Set Duration Targets**:
- Set 1: ~40-50 minutes
- Set 2: ~45-60 minutes
- Set 3: 0-25 minutes (rare)
- Encore: ~15-20 minutes

**Algorithm**:
1. Calculate remaining duration for set
2. Filter candidates to songs fitting remainder
3. Apply jamminess-based selection
4. Track cumulative duration in real-time

### 3. Set-Ending Selection

**Purpose**: Authentic set closers matching historical patterns.

**Mechanism**:
1. After filling set with songs, identify final track
2. Look up `set_ending_tracks.parquet` for that song
3. Filter by canonical set (set1, set2, set3, encore)
4. Weight by likes_count (popularity boost)
5. Randomly select from top performers

**Data**: `data/analytics/features/set_ending_tracks.parquet`
- 5,761 total set-ending tracks
- Set 1: 1,958 tracks (224 unique songs)
- Set 2: 1,771 tracks (199 unique songs)
- Set 3: 105 tracks (56 unique songs)
- Encore: 1,719 tracks (195 unique songs)

**Special Logic**:
- Set 2 and Encore share a combined pool (3,490 tracks)
- Set 1 and Set 3 use set-specific tracks only

### 4. Song Ordering Constraints

**Mandatory Pairings**: 686 discovered ordering rules

**Top Iconic Sequences**:
1. Mike's Song → Weekapaug Groove (511 times, 99.4%)
2. I Am Hydrogen → Weekapaug Groove (339 times, 97.9%)
3. Mike's Song → I Am Hydrogen (334 times, 98.6%)
4. The Oh Kee Pa Ceremony → Suzy Greenberg (133 times, 98.4%)
5. Colonel Forbin's Ascent → Fly Famous Mockingbird (124 times, 94.9%)

**Implementation**: `src/phish_setlist_maker/generator/core.py` tracks mandatory pairs and validates before song addition.

### 5. Cross-Set Dependencies

**Tweezer Reprise Rule**: Cannot appear in encore unless Tweezer was in Set 1, 2, or 3.

**Framework**:
```python
@dataclass
class CrossSetDependency:
    dependent_song: str        # "Tweezer Reprise"
    required_song: str         # "Tweezer"
    target_set: str           # "encore"
    required_sets: list[str]  # ["set1", "set2", "set3"]
    confidence: float         # 0.95
```

**Implementation**: Generator tracks completed sets and validates dependencies before adding candidates.

### 6. Excluded Songs Filter

**Rationale**: Remove non-musical or situational content.

**Excluded Categories** (12 songs total):
- **Meta** (6): Banter, Jam, Narration, Rhombus Narration, Intro, Outro
- **Situational** (4): Happy Birthday, Birthday, Audience Chess Move, Thanksgiving
- **Technical** (2): Soundcheck, Tuning

**Location**: `data/analytics/excluded_songs.csv`

**Implementation**: Applied universally in `_build_candidate_pool()` regardless of era or mode.

---

## Feature System

### Overview

ML features are **optional** and loaded from `data/analytics/features/*.parquet`. When unavailable, the generator falls back to heuristic-only mode.

### Core Feature Tables

| File | Records | Description |
|------|---------|-------------|
| `song_features.parquet` | 389 | Placement probabilities per set |
| `song_transitions.parquet` | 181 | High-confidence transitions |
| `ordering_constraints.parquet` | 686 | Mandatory song orderings |
| `directional_transitions.parquet` | 33 | Adjacent sequence rules |
| `cross_set_dependencies.parquet` | 1 | Cross-set rules |
| `set_ending_frequencies.parquet` | 650 | Set-ending probabilities |
| `set_ending_tracks.parquet` | 5,761 | Actual set-ending track IDs |

### Set Placement Probability

**Metric**: `P(song in setX) = appearances_in_setX / total_appearances`

**Usage**: Filter candidates to songs likely in specific set positions.

**Example**:
- Character Zero: Set 1 (34%), Set 2 (36%), Set 3 (0%), Encore (28%)
- Foam: Set 1 (86.5%), Set 2 (12.5%), Set 3 (0.6%), Encore (0.3%)

### Set Entropy (Versatility)

**What**: Shannon entropy measuring placement uncertainty.

**Formula**: `H = -Σ p_i * log2(p_i)` across all sets

**Interpretation**:
- High (>1.5 bits): Versatile across sets
- Low (<0.5 bits): Set-specific specialist

**Top Versatile Songs**: Icculus, Sanity, La Grange, Whipping Post, Contact

**Most Specialized**: Sleeping Monkey (0.0), Tweezer Reprise (0.0), Alumni Blues (0.078)

### Feature Store Loading

**Location**: `src/phish_setlist_maker/analysis/feature_store.py`

**Behavior**:
- Loads all parquet files on first access
- Caches in memory for subsequent calls
- Returns `None` if feature unavailable
- Falls back gracefully if parquet not found

**Graceful Fallback**:
- If features dir missing → Logs warning, continues with heuristics
- If individual parquet missing → Skips that feature, uses others
- No exceptions raised in production mode

---

## Deployment Guide

### Prerequisites

1. **Fly.io account**: https://fly.io/
2. **flyctl CLI**:
   ```bash
   # macOS
   brew install flyctl
   
   # Or use install script
   curl -L https://fly.io/install.sh | sh
   ```
3. **Login**: `flyctl auth login`

### Cost Breakdown (Free Tier)

- **3 shared-cpu VMs** (256MB RAM) - FREE
- **3GB persistent storage** - FREE
- **160GB bandwidth/month** - FREE
- **Expected total**: $0-5/month on free tier

### Quick Deploy (5 minutes)

#### Step 1: Create Postgres Database

```bash
cd /Users/smarshall/Development/phish-setlist-maker

flyctl postgres create \
  --name phish-setlist-db \
  --region iad \
  --initial-cluster-size 1 \
  --vm-size shared-cpu-1x \
  --volume-size 1
```

#### Step 2: Launch App

```bash
flyctl launch \
  --name phish-setlist-maker \
  --region iad \
  --no-deploy

flyctl postgres attach phish-setlist-db

flyctl deploy
```

**Result**: App live at `https://phish-setlist-maker.fly.dev`

### Manual Setup

```bash
flyctl apps create phish-setlist-maker
flyctl postgres create --name phish-setlist-db --region iad
flyctl postgres attach phish-setlist-db -a phish-setlist-maker
flyctl deploy
```

### Environment Variables

```bash
flyctl secrets set LOG_LEVEL=info
flyctl secrets set SOME_API_KEY=xxx
```

Database URL auto-set when attaching Postgres.

### Scale Configuration

**Free Tier Default** (in `fly.toml`):
- `auto_stop_machines`: Sleeps when idle (saves $)
- `auto_start_machines`: Wakes on request (~1s cold start)
- `min_machines_running = 0`: No always-on
- `256MB RAM`: Fits free tier

**Production Upgrade**:

```bash
# Always keep 1 machine running (no cold starts)
flyctl scale count 1 --yes

# Increase memory if needed
flyctl scale memory 512

# Add regions for redundancy
flyctl regions add ord lax
```

### Monitoring

```bash
# Live logs (streaming)
flyctl logs -a phish-setlist-maker

# Recent logs (no tail)
flyctl logs -a phish-setlist-maker --no-tail

# Check status
flyctl status -a phish-setlist-maker

# SSH access
flyctl ssh console -a phish-setlist-maker

# Metrics dashboard
flyctl dashboard metrics -a phish-setlist-maker
```

### Testing Deployment

```bash
# Get app URL
flyctl info

# Test endpoints
curl https://phish-setlist-maker.fly.dev/health
curl https://phish-setlist-maker.fly.dev/generate
curl https://phish-setlist-maker.fly.dev/docs
```

### Cost Optimization

1. Use auto-stop/start (default) - Sleeps when idle
2. Single region - Avoid multi-region unless needed
3. Shared CPU - Plenty fast for this app
4. 256MB RAM - Works fine for most requests
5. 1GB Postgres volume - DB is small

### Import Data

```bash
# Get DB connection
flyctl postgres connect -a phish-setlist-db

# Or proxy from local
flyctl proxy 5432 -a phish-setlist-db

# In another terminal, import
psql "postgres://postgres:PASSWORD@localhost:5432/phish_setlist_maker" < your_dump.sql
```

### Troubleshooting

**App won't start**:
```bash
flyctl logs  # Check for errors
flyctl secrets list  # Verify DATABASE_URL exists
```

**Database connection issues**:
```bash
flyctl postgres list  # Check if running
flyctl ssh console  # SSH in and verify
env | grep DATABASE_URL
```

**Out of memory**:
```bash
flyctl scale memory 512  # Increase to 512MB
```

**Slow cold starts**:
```bash
flyctl scale count 1  # Keep machine always running (~$2/month)
```

### Updates

```bash
# Make code changes, then deploy
flyctl deploy
# Zero-downtime deployment!
```

### Cleanup

```bash
flyctl apps destroy phish-setlist-maker
flyctl apps destroy phish-setlist-db
```

---

## Development Roadmap

### Phase 1: Quick Wins (0.5–2 days each)

#### ✅ CI/CD Pipeline
- **Goal**: Prevent regressions, ensure tests pass for PRs
- **What**: Add `.github/workflows/ci.yml`
- **What to run**: `poetry install` → `pytest -q` → `ruff check` → `black --check`
- **Est**: 2–4 hours

#### ✅ Pre-commit Hooks
- **Goal**: Keep style consistent across commits
- **What**: Add `.pre-commit-config.yaml` with ruff, black, isort
- **Est**: 1–2 hours

#### ✅ Generator Smoke Test
- **Goal**: Lightweight CI validation
- **What**: Leverage existing `tests/test_cli_smoke.py`
- **Est**: 1 hour

### Phase 2: Robustness & Error Handling (1–3 days)

#### FeatureStore Graceful Fallback
- **Problem**: Raises if features dir missing when `use_ml_features=True`
- **Solution**: Log warning, disable ML features, continue with heuristics
- **Files**: `feature_store.py`, `generator/core.py`
- **Est**: 6–12 hours

#### DB Config Security
- **Problem**: Passwords visible in debug logs via `DatabaseSettings.url()`
- **Solution**: Add `__str__` redaction, default to hiding passwords
- **Files**: `src/phish_setlist_maker/config.py`
- **Est**: 1–2 hours

### Phase 3: Tests & Coverage (2–5 days)

#### Unit Tests for Edge Cases
- **Targets**:
  - `FeatureStore.load()` with missing parquets → fallback state
  - `SetlistGenerator` jamminess boundaries (0.0, 0.5, 1.0)
  - Duration capping behavior
  - Ordering violations detection
- **Files**: New tests `test_feature_store.py`, `test_generator_jamminess.py`
- **Est**: 1–3 days

#### Integration Tests
- **Target**: Generate setlist, validate playlist assembly
- **Scope**: Cover negative flows (remote fetch fails, missing tracks)
- **Tools**: Leverage `responses` library already in use
- **Est**: 1–2 days

### Phase 4: Medium-Term (3–7 days)

#### Factor Generator Internals
- **Why**: `_select_with_duration_budget()` and `_weighted_pick()` are large
- **Goal**: Extract selection strategy and duration policy classes
- **Benefit**: Easier unit testing, enables future experimentation (ML policy, beam search)
- **Files**: Split `core.py` into `selection.py`, `duration_policy.py`, thin wrapper
- **Est**: 3–5 days

#### Stronger Typing
- **Why**: Many methods rely on untyped dicts/lists from parquet loads
- **Goal**: Add return types, Pydantic models, TypedDicts
- **Benefit**: Reduce reasoning overhead, simplify tests
- **Files**: `feature_store.py`, `generator/core.py`, `service/*.py`
- **Est**: 2–4 days

### Phase 5: Strategic / Long-Term (1–3+ weeks)

#### Lazy-Loading / Memory Optimization
- **When**: If parquet features grow large
- **Approach**: Consider Dask, on-disk querying, index column loading only
- **Files**: `feature_store.py`, data pipeline scripts
- **Est**: 1–3 weeks

#### Production DB Seed & E2E Tests
- **What**: Add `docker-compose.dev.yml` with lightweight Postgres
- **Benefit**: Deterministic tests, manual dev cycles
- **Files**: Dev docker config + init script + e2e tests
- **Est**: 2–5 days

### Recommended PR Order

1. **Add CI workflow** (small) - `poetry install` → `pytest` → `ruff`/`black`
2. **Add pre-commit config** (small) - `.pre-commit-config.yaml` + README docs
3. **FeatureStore graceful fallback** (medium) - Missing files → continue with heuristics
4. **Unit tests** (medium) - Edge cases for features/generator
5. **Extract duration_policy** (medium) - Jamminess decisions testable

**PR Target**: <200 LOC per PR for fast reviews

### Risk Notes

- Changing generator heuristics alters output behavior; maintain feature toggles
- ML features depend on external parquets; treat as optional
- Keep behavior defaults unchanged unless adding deprecation warnings

---

## Key Commands Reference

### Export & Analysis

```bash
# Full analytics pipeline
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

# Era-specific
poetry run phish-setlist-maker generate --num-sets 2 --era 4.0
```

---

## Performance Metrics

| Operation | Time | Memory | Notes |
|-----------|------|--------|-------|
| Feature loading | ~150ms (one-time) | ~100KB | Cached after first load |
| Cross-set dependency check | <1ms | ~2KB | Per candidate |
| Ordering constraints lookup | <1ms | Per song | Parquet indexed |
| Set-ending track query | <1ms | Per set | Pandas filter |
| Full generation (2 sets, 20 songs) | ~500ms | ~10MB | Includes all checks |

**Total overhead for ML features**: <1% performance impact

---

## Support & Resources

- **Documentation**: `docs/ml/` for detailed feature engineering
- **Pandas Guide**: https://pandas.pydata.org/docs/
- **Scikit-learn**: https://scikit-learn.org/stable/user_guide.html
- **Parquet Format**: https://parquet.apache.org/docs/
- **Fly.io Docs**: https://fly.io/docs
- **Fly.io Community**: https://community.fly.io

---

**Status**: Production Ready  
**Last Review**: October 25, 2025  
**Maintainer**: Development Team
