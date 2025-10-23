# ML & Data Analysis Documentation

**Last Updated**: 2025-10-23

---

## Quick Links

### Essential Reading (Start Here)

📚 **[01-OVERVIEW-AND-SETUP.md](./01-OVERVIEW-AND-SETUP.md)** - Setup, data pipeline, quick start  
🔬 **[02-FEATURE-ENGINEERING.md](./02-FEATURE-ENGINEERING.md)** - Features, insights, analysis  
⚙️ **[03-GENERATOR-INTEGRATION.md](./03-GENERATOR-INTEGRATION.md)** - ML-enhanced generation  
🔒 **[04-CONSTRAINTS-SYSTEM.md](./04-CONSTRAINTS-SYSTEM.md)** - Ordering rules, dependencies, exclusions  
🗺️ **[05-ROADMAP-AND-FUTURE.md](./05-ROADMAP-AND-FUTURE.md)** - Project roadmap, past/present/future

---

## Documentation Structure

### Core Guides (Read in Order)

These 5 comprehensive documents replace all previous scattered documentation:

#### 1. Overview and Setup

- Project mission and architecture
- Quick start (single-command data pipeline)
- Environment setup and dependencies
- Database schema overview
- Data export pipeline
- Development workflow

**Read this**: To get started with ML/analytics work

#### 2. Feature Engineering

- Song placement features (set probabilities, entropy)
- Transition analysis (lift scores, Mike's Groove)
- Temporal patterns (trends, openers/closers)
- Venue tendencies (location-specific patterns)
- Complete feature catalog

**Read this**: To understand what features exist and their insights

#### 3. Generator Integration

- FeatureStore architecture (in-memory caching)
- Generator enhancements (placement blending, transition bonuses)
- API integration (parameters, endpoints)
- Usage examples (CLI, API, scripts)
- Performance metrics and testing

**Read this**: To understand how ML features drive generation

#### 4. Constraints System

- Ordering constraints (686 rules, Mike's → Weekapaug)
- Cross-set dependencies (Tweezer Reprise needs Tweezer)
- Directional transitions (one-way sequences)
- Excluded songs (non-musical content filter)
- Implementation details and testing

**Read this**: To understand the constraint enforcement system

#### 5. Roadmap and Future

- Completed phases (Phase 0-2.2 done)
- Current status and capabilities
- Future work (Phase 2.3-4, optional stretch goals)
- Success metrics and decision log
- Contributing guidelines

**Read this**: To understand project history and future direction

---

## Quick Reference

### Common Commands

**Export all data**:

```bash
poetry run python scripts/run_analytics_exports.py --use-primary
```

**Build all ML features**:

```bash
poetry run python scripts/build_features.py
```

**Generate setlist (ML-enhanced)**:

```bash
poetry run phish-setlist-maker generate --num-sets 2 --include-encore
```

**Run all tests**:

```bash
poetry run pytest tests/ -v
```

**View reports**:

```bash
# Set placement
poetry run python scripts/report_set_placement.py

# Transitions
poetry run python scripts/report_song_transitions.py

# Venues
poetry run python scripts/report_venue_analysis.py
```

### Key Files

**Feature Data** (`data/analytics/features/`):

- `song_features.parquet` - 389 songs with placement probabilities
- `song_transitions.parquet` - 181 high-confidence transitions
- `ordering_constraints.parquet` - 686 ordering rules
- `directional_transitions.parquet` - 33 directional rules
- `cross_set_dependencies.parquet` - 1 cross-set rule
- `excluded_songs.csv` - 12 excluded songs

**Core Code**:

- `src/phish_setlist_maker/analysis/features.py` - Feature engineering
- `src/phish_setlist_maker/analysis/feature_store.py` - Feature loading
- `src/phish_setlist_maker/generator/core.py` - ML-enhanced generation

---

## Project Status

### What's Complete ✅

- **Phase 0**: Foundations (data pipeline, analytics workspace)
- **Phase 1**: Feature engineering (389 songs, 181 transitions)
- **Phase 2.1**: Generator integration (ML-enhanced generation)
- **Phase 2.2**: Constraints system (686 ordering rules, cross-set deps)

### What's Next 🔄

- **Phase 2.3**: Song similarity & substitution
- **Phase 2.4**: `/predict` endpoint for next-show forecasting
- **Phase 3**: Automated testing, monitoring, production ops

### Overall Progress

```
Phase 0: ████████████████████ 100% Complete
Phase 1: ████████████████████ 100% Complete
Phase 2: ████████████░░░░░░░░  70% In Progress
Phase 3: ░░░░░░░░░░░░░░░░░░░░   0% Planned
Phase 4: ░░░░░░░░░░░░░░░░░░░░   0% Optional
```

---

## Key Statistics

**Data Coverage**:

- 2,104 shows (1983-2025)
- 39,244 tracks
- 973 songs
- 764 venues
- 124 tours

**ML Features**:

- 389 songs with complete features (top 40% by frequency)
- 181 high-confidence transitions (lift > 1.0)
- 686 ordering constraints discovered
- 246 multi-home songs identified (63% of repertoire)

**Performance**:

- Feature loading: <100ms
- Generation overhead: ~20ms (20% increase)
- Memory footprint: +2MB

**Quality**:

- ✅ All 28 existing tests pass
- ✅ Zero constraint violations in 100 generated setlists
- ✅ Zero breaking changes to API

---

## Getting Help

### For Setup Issues

→ Read **[01-OVERVIEW-AND-SETUP.md](./01-OVERVIEW-AND-SETUP.md)** Section 3 (Environment Setup)

### For Feature Questions

→ Read **[02-FEATURE-ENGINEERING.md](./02-FEATURE-ENGINEERING.md)** Section 6 (Feature Catalog)

### For Generator Integration

→ Read **[03-GENERATOR-INTEGRATION.md](./03-GENERATOR-INTEGRATION.md)** Section 5 (Usage Examples)

### For Constraint Rules

→ Read **[04-CONSTRAINTS-SYSTEM.md](./04-CONSTRAINTS-SYSTEM.md)** relevant section

### For Project Direction

→ Read **[05-ROADMAP-AND-FUTURE.md](./05-ROADMAP-AND-FUTURE.md)** Section 3 (Future Work)

### Still Stuck?

- Check main project `README.md`
- Review test files in `tests/`
- Examine scripts in `scripts/`
- Consult `AGENTS-ml.md` for high-level roadmap

---

## Contributing

### To Add Features

1. Prototype in `notebooks/ml/`
2. Migrate to `src/phish_setlist_maker/analysis/features.py`
3. Add to `scripts/build_features.py`
4. Update relevant guide (02-FEATURE-ENGINEERING.md)

### To Add Constraints

1. Discover rules (analysis or manual)
2. Export to `data/analytics/features/`
3. Load in `FeatureStore`
4. Enforce in `SetlistGenerator`
5. Update 04-CONSTRAINTS-SYSTEM.md

### To Improve Docs

- Keep core guides up-to-date (01-05)
- Archive obsolete legacy docs
- Add examples and visualizations
- Link between related sections

---

## Changelog

### 2025-10-23

- ✅ Created 5 comprehensive documentation guides
- ✅ Consolidated 19 legacy docs into organized structure
- ✅ Added this README as documentation index
- ✅ All core features documented

### 2025-10-22

- ✅ Completed Phase 2.1 (generator integration)
- ✅ Completed Phase 1 (feature engineering)

### 2025-10-20

- ✅ Completed Phase 0 (foundations)
- ✅ Initial documentation structure

---

## License

Same as main project (see root LICENSE file).

---

**For questions or issues**: File a GitHub issue or consult main project documentation.

**Project**: Phish Setlist Maker  
**ML Documentation**: Comprehensive guides for ML/data analysis work  
**Status**: Production Ready (Phase 0-2.2 complete)
