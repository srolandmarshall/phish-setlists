# ML & Data Analysis Documentation

**Last Updated**: 2025-10-24

---

## Recent Updates (October 24, 2025)

### Phase 2.6: Jamminess & Duration Control ✅

**Completed comprehensive jamminess system** giving users fine-grained control over setlist intensity:

#### Major Achievements
1. **Multi-Percentile Duration System** - Replaced single p80 with p30/p50/p70/p90 selection
2. **Fixed Critical Set 2 Bug** - Duration compliance improved from **9% → 85-90%**
3. **Dynamic Percentile Selection** - Intelligently chooses song durations based on remaining time or user preference
4. **Jamminess Parameter** - 0.0 (tight) to 1.0 (extended) with constraint relaxation
5. **Dynamic Song Count Adjustment** - High jamminess reduces song count (8-9 vs 10-11) to maintain consistent duration
6. **Matplotlib Analysis Script** - 9-subplot comparison of jamminess levels

#### Key Results
- **Tight (0.01)**: 100% Set 1, 84% Set 2 compliance ✓
- **Balanced (0.5)**: 92% Set 1, 90% Set 2 compliance ✓
- **Full Send (0.99)**: 100% Set 1, 98% Set 2 compliance ✓

#### Files
- **New**: `docs/ml/07-JAMMINESS-AND-DURATION-CONTROL.md` - Complete phase documentation
- **New**: `scripts/analyze_jamminess_with_charts.py` - Analysis with matplotlib
- **Modified**: `core.py`, `constants.py`, `schemas.py`, etc. - Implementation

#### What's New in This Phase
- **Jamminess Control**: Web UI slider, API parameter, CLI flag
- **Multi-Percentile Durations**: Different song lengths based on intensity level
- **Constraint Relaxation**: Duration targets scale from 60-75min (normal) to 60-112min (0.99)
- **Smart Song Counts**: 9-10 songs at high jamminess, 10-11 at default/tight
- **Balanced Playlist Sampling**: Landing-page playlists now choose uniformly from *all* recordings, not just the top 50 liked versions, so low jamminess surfaces concise takes instead of defaulting to legendary 25-minute jams.
- **Analysis Tools**: Matplotlib charts for validation and visualization

---

## Recent Updates (October 23, 2025)

### Set-Ending Track Selection & Frequency Analysis

**Phase 2.5 Enhancements** - Today we completed major improvements to setlist generation quality:

#### 1. Set-Ending Track Selection ✅
- **Problem**: Songs chosen as set closers weren't always using actual set-ending performances
- **Solution**: Created `set_ending_tracks.parquet` with 3,490 authentic closer track IDs
- **Implementation**:
  - Set 1 closers weighted by historical ending probability (Character Zero 48.6%, David Bowie 36.9%)
  - Track selector picks from actual set-ending versions for authentic energy/duration
  - Set 2 and Encore closers share a pool of 3,490 performances
  - Bidirectional: Set 2 can use Encore versions, Encore can use Set 2 versions
- **Impact**: Set closers now have authentic show-ending vibes and proper track selection

#### 2. Frequency Analysis & Outlier Detection ✅
- **Problem**: Rare songs appearing too frequently in generated setlists
- **Analysis**: `analyze_generation_frequency.py` - generates N setlists and compares to historical rates
- **Findings**: 
  - Songs with <50 appearances were showing up 75-80% too often
  - Alumni Blues > Letter to Jimmy Page > Alumni Blues causing issues (handled by rules)
  - "I Am the Walrus" appearing in non-4.0 eras (should be 4.0 only)
- **Solution**: `RareSongFrequencyCapRule` in `generator/rules.py`
  - Downweights songs with <50 historical appearances
  - Era-aware exclusions (e.g., "I Am the Walrus" only in 4.0)
  - Integrated into existing rules engine
- **Impact**: Rare song appearances reduced by 75-80% to realistic historical levels

#### 3. Era Picker UI Enhancement ✅
- **Feature**: Optional era filter on landing page with checkbox + dropdown
- **Implementation**:
  - Checkbox toggle: "Filter by Era" (unchecked by default = all eras)
  - Dropdown with 5 options: All Eras, 1.0, 2.0, 3.0, 4.0
  - Updates `/generate?era=X.X` URL parameter
  - 280px width matching Generate Show button
  - Purple brand colors with smooth animations
- **Files**:
  - `static/index.html` - Checkbox + dropdown UI
  - `static/landing.css` - Styling with hover/focus states
  - `static/era-picker.js` - Extracted JavaScript logic
- **Note**: Backend era filtering already existed; we just added the UI layer

#### 4. Code Cleanup ✅
- **Moved HTML to static**: `index.html` now served from `static/` folder (140 lines reduced from API code)
- **Extracted inline CSS**: `landing.css` now separate file (118 lines)
- **Extracted inline JS**: `era-picker.js` now separate file (35 lines)
- **Added Phish.in attribution**: Footer acknowledgment on landing page
- **Fixed Known Issues styling**: Red X bullets (✗) instead of checkmarks

#### Key Files Created/Modified

**New Files**:
- `data/analytics/features/set_ending_tracks.parquet` - 3,490 authentic closer track IDs
- `scripts/analyze_generation_frequency.py` - Frequency analysis CLI tool
- `static/era-picker.js` - Era picker functionality
- `ERA-PICKER.md` - Complete era picker documentation

**Modified Files**:
- `src/phish_setlist_maker/generator/picker.py` - Set-ending track selection logic
- `src/phish_setlist_maker/generator/rules.py` - Added `RareSongFrequencyCapRule`
- `src/phish_setlist_maker/generator/core.py` - Integrated frequency caps
- `static/index.html` - Era picker UI, Phish.in attribution, Known Issues styling
- `static/landing.css` - Era picker styles, attribution styles, issue bullets
- `README.md` - Documented recent improvements

**Analysis Output**:
- `data/analytics/frequency_analysis/historical_comparison.parquet` - Frequency analysis results

#### Documentation Created

**`ERA-PICKER.md`**:
- Complete feature documentation
- Technical implementation details
- Design specifications
- Testing checklist
- API examples
- Future enhancements

**`SET-ENDING-TRACKS-SUMMARY.md`**:
- Set-ending track selection strategy
- Data analysis and insights
- Implementation details

**`FREQUENCY-CAP-SUMMARY.md`**:
- Frequency analysis methodology
- Statistical findings
- Rule implementation

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
- `set_ending_tracks.parquet` - **NEW** 3,490 authentic set-ending track IDs
- `ordering_constraints.parquet` - 686 ordering rules
- `directional_transitions.parquet` - 33 directional rules
- `cross_set_dependencies.parquet` - 1 cross-set rule
- `excluded_songs.csv` - 12 excluded songs

**Core Code**:

- `src/phish_setlist_maker/analysis/features.py` - Feature engineering
- `src/phish_setlist_maker/analysis/feature_store.py` - Feature loading
- `src/phish_setlist_maker/generator/core.py` - ML-enhanced generation
- `src/phish_setlist_maker/generator/picker.py` - **NEW** Set-ending track selection
- `src/phish_setlist_maker/generator/rules.py` - **NEW** Frequency cap rules

---

## Project Status

### What's Complete ✅

- **Phase 0**: Foundations (data pipeline, analytics workspace)
- **Phase 1**: Feature engineering (389 songs, 181 transitions)
- **Phase 2.1**: Generator integration (ML-enhanced generation)
- **Phase 2.2**: Constraints system (686 ordering rules, cross-set deps)
- **Phase 2.5**: Set-ending track selection & frequency caps
- **Phase 2.6**: **NEW** Jamminess & duration control (multi-percentile durations, dynamic song counts, constraint relaxation)

### What's Next 🔄

- **Phase 2.7**: Opener selection improvements
- **Phase 2.8**: Encore opener modeling
- **Phase 3**: Song similarity & substitution
- **Phase 4**: Automated testing, monitoring, production ops

### Overall Progress

```
Phase 0: ████████████████████ 100% Complete
Phase 1: ████████████████████ 100% Complete
Phase 2: ██████████████████░░  90% In Progress (NEW: jamminess + duration)
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
- 3,490 set-ending track performances **NEW**
- 686 ordering constraints discovered
- 246 multi-home songs identified (63% of repertoire)
- Frequency caps for rare songs (<50 appearances) **NEW**

**Performance**:

- Feature loading: <100ms
- Generation overhead: ~20ms (20% increase)
- Memory footprint: +2MB

**Quality**:

- ✅ All 28 existing tests pass
- ✅ Zero constraint violations in 100 generated setlists
- ✅ Zero breaking changes to API
- ✅ Rare song frequency reduced by 75-80% **NEW**
- ✅ Authentic set-ending track selection **NEW**

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

### 2025-10-23 (Evening - Phase 2.5)

- ✅ **Set-Ending Track Selection**: 3,490 authentic closer performances
  - Weighted by historical ending probability (Character Zero 48.6%, Bowie 36.9%)
  - Bidirectional Set 2/Encore track sharing
  - Creates `set_ending_tracks.parquet`
- ✅ **Frequency Analysis & Caps**: Rare song outlier detection
  - Analysis tool: `analyze_generation_frequency.py`
  - `RareSongFrequencyCapRule` downweights songs <50 appearances
  - Era-aware exclusions (I Am the Walrus only in 4.0)
  - Rare songs reduced by 75-80%
- ✅ **Era Picker UI**: Optional era filter on landing page
  - Checkbox + dropdown (defaults to all eras)
  - Extracted to `era-picker.js`
  - Full documentation in `ERA-PICKER.md`
- ✅ **Code Cleanup**: HTML/CSS/JS separation
  - Moved landing page to `static/index.html`
  - Extracted CSS to `landing.css`
  - Added Phish.in attribution
  - Fixed Known Issues styling (red X bullets)

### 2025-10-23 (Morning)

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
