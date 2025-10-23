# Project Roadmap: Past, Present, and Future

**Last Updated**: 2025-10-23  
**Current Phase**: Phase 2 In Progress

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Completed Phases](#completed-phases)
3. [Current Status](#current-status)
4. [Future Work](#future-work)
5. [Success Metrics](#success-metrics)

---

## Executive Summary

### Project Mission

Build a robust data + ML layer that:
1. Deepens understanding of historical Phish setlist construction
2. Drives smarter, more authentic setlist generation
3. Enables predictive capabilities for next-show forecasting

### Overall Progress

```
Phase 0: Foundations          ✅ Complete (2025-10-20)
Phase 1: Feature Engineering  ✅ Complete (2025-10-22)
Phase 2: Generator Enhancement 🔄 In Progress (2025-10-23)
  ├─ 2.1: Feature Integration  ✅ Complete
  ├─ 2.2: Constraints System   ✅ Complete
  ├─ 2.3: Similarity Models    ⏳ Future
  └─ 2.4: Predictive API       ⏳ Future
Phase 3: Tooling & Operations ⏳ Planned
Phase 4: Advanced Models      ⏳ Optional Stretch
```

### Key Achievements

- **2,104 shows** analyzed (1983-2025)
- **389 songs** with ML features
- **686 ordering constraints** discovered
- **181 high-confidence transitions** identified
- **Zero breaking changes** to existing API
- **All tests passing** (28/28)

---

## Completed Phases

### Phase 0: Foundations & Data Contracts (Oct 2025)

**Goal**: Establish reproducible analytics infrastructure

#### 0.1 Data Audit ✅

**What**: Inventory and validate source data

**Deliverables**:
- `docs/ml/schema-overview.md` - Complete schema documentation
- Database audit script with coverage metrics
- ORM/schema drift documentation

**Metrics**:
- 2,104 shows (1983-2025)
- 39,244 tracks
- 973 songs
- 764 venues
- 124 tours

#### 0.2 Analytics Workspace ✅

**What**: Set up reproducible Python environment

**Deliverables**:
- Updated `pyproject.toml` with ML dependencies
- Database configuration (primary + analytics)
- Bootstrap scripts for DB setup
- Notebook conventions documentation

**Tools Added**:
- pandas, numpy (data manipulation)
- scikit-learn (ML algorithms)
- matplotlib, seaborn (visualization)
- jupyterlab (interactive development)
- fastparquet (efficient storage)

#### 0.3 Data Extraction Utilities ✅

**What**: Build reusable exporters and staging tables

**Deliverables**:

**Core Exporters** (`src/phish_setlist_maker/analysis/database.py`):
- `load_show_dataframe()`
- `load_track_dataframe()`
- `load_song_dataframe()`
- `load_venue_dataframe()`
- `load_tour_dataframe()`

**Staging Tables**:
- `build_set_segments()` - 5,469 set summaries
- `build_song_transitions()` - 181 high-confidence pairs
- `build_song_set_frequencies()` - 825 placement probabilities
- `build_venue_tendencies()` - 723 venue statistics

**CLI Tools**:
- `scripts/run_analytics_exports.py` - ONE-COMMAND pipeline
- `scripts/report_set_placement.py` - Placement stats
- `scripts/report_song_transitions.py` - Transition analysis
- `scripts/report_venue_analysis.py` - Venue tendencies

**Runtime**: ~30 seconds for full export

---

### Phase 1: Exploratory Analysis & Feature Engineering (Oct 2025)

**Goal**: Extract meaningful features from historical data

#### 1.1 Set Placement Profiling ✅

**What**: Quantify per-set appearance rates for all songs

**Key Functions** (`src/phish_setlist_maker/analysis/features.py`):
- `compute_set_entropy()` - Placement versatility (Shannon entropy)
- `identify_multi_home_songs()` - Flexible placement detection

**Discoveries**:
- **246 multi-home songs** (63% of repertoire)
- **Top entropy**: Icculus (1.894 bits) - most versatile
- **Set 1 specialists**: Foam (86.5%), Divided Sky (82.7%)
- **Set 2 specialists**: Hold Your Head Up (85.0%), Also Sprach (82.9%)
- **Encore lock-ins**: Sleeping Monkey (76.0%), Tweezer Reprise (62.6%)

**Outputs**:
- `song_features.parquet` - 389 songs with probabilities
- `song_set_entropy.parquet` - Versatility scores
- `multi_home_songs.parquet` - Flexible songs
- `docs/figures/set_placement_heatmap.png`
- `docs/figures/entropy_distribution.png`

#### 1.2 Transition & Dependency Mining ✅

**What**: Compute lift metrics for song-to-song transitions

**Key Functions**:
- `compute_transition_lift()` - Association strength
- Bidirectional vs. directional pattern detection

**Discoveries**:
- **Top lift**: Swept Away → Steep (473.6×)
- **Mike's Groove**: Mike's → Hydrogen (79.0×), Hydrogen → Weekapaug (113.8×)
- **Story sequences**: Colonel Forbin's → Mockingbird (393.4×)
- **Composed pairs**: The Horse → Silent Morning (213.8×)

**Outputs**:
- `song_transitions.parquet` - 181 transitions
- `transition_lift.parquet` - Lift scores with support
- `docs/figures/transition_network.png`

#### 1.3 Song Profile Summaries ✅

**What**: Consolidate all features into wide-format table

**Schema**:
- Song title (normalized)
- Set probabilities (set1, set2, set3, encore)
- Entropy score
- Total appearances
- Multi-home flag
- Debut year, last played

**Output**: `song_features.parquet` - Master feature table

#### 1.4 Temporal Trend Analysis ✅

**What**: Track song popularity over time, identify opener/closer patterns

**Key Scripts**:
- `scripts/build_trend_tables.py` - Time-series exports

**Outputs**:
- `song_year_counts.parquet` - Yearly play counts
- `set_duration_summary.parquet` - Duration patterns by era
- `intro_outro_counts.parquet` - Common openers/closers
- `docs/figures/temporal_trends.png`

**Insights**:
- Era-specific rotation patterns (1.0, 2.0, 3.0)
- Set 2 durations increased in 3.0 era (longer jams)
- Top Set 1 opener: AC/DC Bag (145 times)
- Top Set 2 opener: Also Sprach Zarathustra (200 times)

#### Phase 1 Summary

**Completion Date**: 2025-10-22

**Artifacts**:
- 4 feature tables (389 songs, 181 transitions)
- 4 visualization figures
- 2 comprehensive reports
- Single-command workflow (`scripts/build_features.py`)

**Runtime**: ~10-15 seconds for full feature rebuild

---

### Phase 2: Generator Enhancements (Oct 2025)

**Goal**: Integrate ML features into `/generate` endpoint

#### 2.1 Feature Integration into Generator Logic ✅

**Completion Date**: 2025-10-22

**What**: Load features and apply to song selection

**Deliverables**:

**FeatureStore Module** (`src/phish_setlist_maker/analysis/feature_store.py`):
- In-memory feature cache (<100ms load time)
- Fast lookup methods (O(1) dict access)
- ~2MB memory footprint

**Generator Enhancements** (`src/phish_setlist_maker/generator/core.py`):
- `use_ml_features` parameter (default: True)
- `ml_placement_weight` parameter (default: 0.3)
- `ml_transition_bonus` parameter (default: 0.1)
- Placement probability blending (30% ML, 70% historical)
- Transition lift bonuses (up to 10% boost)

**API Integration**:
- `GenerateRequestModel` exposes ML toggles
- Full backward compatibility maintained
- All 28 existing tests pass

**Performance**:
- Initialization: +100ms (one-time)
- Per-generation: +20ms (~20% overhead)
- Memory: +2MB

**Status**: ✅ Complete, production ready

#### 2.2 Directional Sequence Rules & Ordering Constraints ✅

**Completion Date**: 2025-10-23

**What**: Enforce song ordering and adjacency rules

**Deliverables**:

**2.2a: Ordering Constraints**
- `compute_set_ordering_constraints()` function
- 686 mandatory ordering rules discovered
- Mike's Song → Weekapaug Groove (99.4%, n=511) - THE RULE
- Applies to songs in same set, any distance apart

**2.2b: Excluded Songs Filter**
- `excluded_songs.csv` - 12 non-musical entries
- Universal application (all modes, all sets)
- Categories: meta, situational, technical
- Examples: Banter, Soundcheck, Happy Birthday

**2.2c: Directional Transitions**
- `compute_directional_transitions()` function
- 33 directional transition rules
- Mandatory forwards: Hydrogen → Weekapaug, Swept Away → Steep
- Forbidden reverses: Weekapaug → Hydrogen (never)

**2.2d: Cross-Set Dependencies**
- `cross_set_dependencies.parquet` - 1 rule
- Tweezer Reprise (encore) requires Tweezer in Set 1/2/3
- 95% confidence from historical data
- Prevents "orphan reprise" songs

**Testing**:
- All unit tests pass (ordering, cross-set, exclusions)
- Integration tests: 100 generated setlists, zero violations
- No regressions (28/28 tests pass)

**Status**: ✅ Complete, all constraints enforced

---

## Current Status

### What Works Today (2025-10-23)

#### ML-Enhanced Generation

**Default Behavior** (ML enabled):
```bash
poetry run phish-setlist-maker generate --num-sets 2 --include-encore
```

**Features Active**:
- ✅ Placement probability blending (30% ML)
- ✅ Transition lift bonuses (10% boost for high-lift pairs)
- ✅ 686 ordering constraints enforced
- ✅ Cross-set dependencies checked
- ✅ 33 directional transitions enforced
- ✅ 12 excluded songs filtered

**Result**: More authentic Phish-like setlists

#### Legacy Mode

**Disable ML**:
```python
generator = SetlistGenerator(session, use_ml_features=False)
```

**Result**: Exact pre-ML behavior (no constraints, pure historical frequency)

#### API Endpoints

**Current**:
- `POST /generate` - Generate setlist (ML-enhanced by default)
- Query parameters: `use_ml_features`, `ml_placement_weight`, `ml_transition_bonus`

**Future** (not yet implemented):
- `GET /predict` - Forecast next show
- `POST /predict` - Scenario evaluation
- `GET /features/{song}` - Feature inspection

### Data Coverage

**Songs with Features**: 389 / ~973 (40%)
- Covers most popular/frequently-played songs
- Rare songs fall back to historical-only

**Transitions Tracked**: 181 high-confidence pairs
- Minimum 10 occurrences, lift > 1.0
- Focused on meaningful associations

**Ordering Constraints**: 686 rules
- Covers major sequences (Mike's Groove, composed pairs, story songs)
- High-confidence only (≥90% ordering ratio)

**Cross-Set Rules**: 1 rule (Tweezer Reprise)
- Framework supports expansion
- Easy to add new rules via parquet file

### System Health

**Test Coverage**:
- ✅ 28/28 existing tests pass (0 regressions)
- ✅ 5/5 cross-set dependency tests pass
- ✅ 10/10 exclusion verification tests pass
- ✅ 100 generated setlists validated (zero constraint violations)

**Performance**:
- Feature loading: <100ms (one-time)
- Per-generation overhead: ~20ms (~20% increase)
- Memory footprint: +2MB (negligible)

**Production Readiness**: ✅ Ready for deployment
- Zero breaking changes
- Backward compatible
- Graceful degradation (missing features → historical fallback)
- Comprehensive error handling

---

## Future Work

### Phase 2 Remaining

#### 2.3 Song Similarity & Substitution (Not Started)

**Goal**: Enable "songs like X" recommendations and substitutions

**Approach**:
- Cluster songs by co-occurrence patterns
- Set placement profile similarity
- Duration/tempo/energy matching
- Node2Vec embeddings on transition graph

**Use Cases**:
- When constraints are tight, suggest similar songs
- "If you like X, you might like Y"
- Substitute for unavailable songs in generator

**Estimated Effort**: 4-6 hours

**Priority**: Medium (nice-to-have enhancement)

#### 2.4 `/predict` Endpoint Prototype (Not Started)

**Goal**: Forecast next show or evaluate user scenarios

**Features**:
- `GET /predict?date=YYYY-MM-DD&tour_id=X` - Next show prediction
- `POST /predict` - Custom scenario (forced opener, expected set count)
- Top-N probability-ranked predictions per set
- Confidence intervals

**Approach**:
- Baseline: Recency-adjusted frequency model
- Advanced: Markov chains with tour context
- Validation: Back-test on historical shows

**Success Metric**: >30% hit rate @ top-10 for next-show prediction

**Estimated Effort**: 6-8 hours

**Priority**: High (valuable user-facing feature)

---

### Phase 3: Tooling, Ops, and UX Integration (Planned)

**Goal**: Production-ready ML pipeline with monitoring and automation

#### 3.1 Notebook-to-Code Migration

**Status**: 🔄 Partially complete

**Done**:
- ✅ Feature builders migrated to `analysis/features.py`
- ✅ CLI commands for feature generation
- ✅ Documentation in `docs/ml/`

**TODO**:
- Expand test coverage for feature engineering modules
- Add property-based tests (hypothesis library)
- Continuous integration for feature pipelines

#### 3.2 Automation & Testing

**TODO**:
- Data quality tests (pytest fixtures)
  - Placement probabilities sum to ~1.0
  - No negative durations
  - Ordering constraints are acyclic
- Model validation harness
  - Nightly recomputation of metrics
  - Drift detection alerts
- Sample predictions (regression tests)
  - Known historical shows → verify predictions
- Performance benchmarks
  - Track generation speed over time
  - Alert on >10% degradation

**Priority**: High (production reliability)

#### 3.3 Application Integration

**TODO**:
- Lazy-loading features in FastAPI (`app.state.feature_store`)
- Config flags for toggling ML features
- Monitoring hooks
  - Log prediction confidence
  - Track feature timestamps
  - Record generation heuristics used
- Feature versioning
  - Track which feature version generated each setlist
  - A/B testing infrastructure

**Priority**: Medium (operational excellence)

---

### Phase 4: Future Enhancements (Optional Stretch)

**Goal**: Advanced ML techniques for creative generation

#### 4.1 Advanced Sequence Models

**Options**:

**Markov Chains**:
- Multi-song context (A, B → C prediction)
- Set-level flow modeling
- Era-specific transition matrices
- **Estimated Effort**: 4-6 hours
- **Priority**: Medium

**Recurrent Neural Networks (RNNs/LSTMs)**:
- Learn long-range dependencies
- Capture set "narrative arc"
- Requires more data and compute
- **Estimated Effort**: 20-40 hours
- **Priority**: Low (research project)

**Transformer Models**:
- Sequence-to-sequence generation
- Attention mechanisms for context
- State-of-the-art but complex
- **Estimated Effort**: 40+ hours
- **Priority**: Very Low (academic exercise)

#### 4.2 User Feedback Loop

**Goal**: Learn from user preferences

**Approach**:
- Collect thumbs up/down on generated setlists
- Feed into reinforcement learning system
- Active learning for hard-to-generate scenarios

**Techniques**:
- Collaborative filtering (user preferences)
- Thompson sampling (exploration vs. exploitation)
- Multi-armed bandits (optimize generation parameters)

**Estimated Effort**: 20-30 hours

**Priority**: Low (requires user base and data collection)

#### 4.3 External Data Integration

**Goal**: Incorporate show context beyond setlist

**Data Sources**:
- Venue size/capacity
- Festival vs. regular show
- Webcast/stream presence
- Tour position (opener, closer, mid-tour)
- Weather data (outdoor venues)
- Setlist.fm ratings/comments

**Use Cases**:
- Adjust song selection for venue size
- Festival-specific patterns
- Opening night vs. closing night dynamics

**Estimated Effort**: 10-20 hours (per data source)

**Priority**: Low (marginal gains)

#### 4.4 Visualization Portal

**Goal**: Public-facing insights dashboard

**Features**:
- Song popularity trends over time
- Transition network explorer (interactive)
- Venue tendency maps (geographic)
- "What if" scenario simulator
- Compare generated vs. historical setlists

**Tech Stack**:
- Streamlit (quick prototyping)
- Plotly/Dash (interactive charts)
- Static site (minimal maintenance)

**Estimated Effort**: 20-30 hours

**Priority**: Low (nice demo, not core functionality)

---

## Success Metrics

### Phase 0-2 (Current)

**Data Foundation**:
- ✅ 100% schema coverage documented
- ✅ <30 second full export pipeline
- ✅ <100ms feature loading

**Feature Quality**:
- ✅ 389 songs with complete features (top 40% by frequency)
- ✅ 181 high-confidence transitions (lift > 1.0, support ≥ 10)
- ✅ 686 ordering constraints discovered
- ✅ Zero false positives in constraint rules (manual validation)

**Generator Quality**:
- ✅ All tests pass (28/28)
- ✅ Zero constraint violations in 100 generated setlists
- ✅ <20% performance overhead
- ✅ Backward compatible (zero breaking changes)

**Production Readiness**:
- ✅ Feature flags for gradual rollout
- ✅ Graceful degradation on missing features
- ✅ Comprehensive documentation (5 detailed guides)

### Phase 3-4 (Future)

**Prediction Accuracy**:
- Target: >30% hit rate @ top-10 for next-show prediction
- Target: >50% hit rate @ top-20
- Target: >70% hit rate @ top-50

**User Satisfaction** (if feedback collected):
- Target: >70% thumbs up on ML-generated setlists
- Target: <10% complaints about "unrealistic" songs
- Target: >50% users prefer ML mode over legacy

**System Reliability**:
- Target: 99.9% uptime for `/generate` endpoint
- Target: <500ms p95 latency
- Target: Zero production incidents from ML code

---

## Timeline

### Completed Work

| Phase | Tasks | Duration | Dates |
|-------|-------|----------|-------|
| Phase 0 | Foundations | 1 week | Oct 13-20, 2025 |
| Phase 1 | Feature Engineering | 2 days | Oct 21-22, 2025 |
| Phase 2.1 | Generator Integration | 1 day | Oct 22, 2025 |
| Phase 2.2 | Constraints System | 1 day | Oct 23, 2025 |

**Total**: ~10 days of focused work

### Remaining Work (Estimates)

| Phase | Tasks | Estimated Duration |
|-------|-------|-------------------|
| Phase 2.3 | Song Similarity | 4-6 hours |
| Phase 2.4 | `/predict` Endpoint | 6-8 hours |
| Phase 3.1 | Testing Expansion | 4-6 hours |
| Phase 3.2 | Automation | 6-8 hours |
| Phase 3.3 | Monitoring | 4-6 hours |

**Total**: ~3-4 additional days of work for Phase 2-3 completion

**Phase 4**: Optional stretch goals, no timeline set

---

## Decision Log

### Key Decisions Made

#### 1. Parquet Format for Features

**Decision**: Use Parquet instead of CSV or database tables

**Rationale**:
- 10× smaller than CSV
- Fast loading (<100ms)
- Preserves data types
- Portable across tools

**Date**: 2025-10-20

#### 2. ML Features Default On

**Decision**: Enable ML features by default (`use_ml_features=True`)

**Rationale**:
- Better user experience out-of-box
- Backward compatibility maintained via flag
- Gradual rollout still possible

**Date**: 2025-10-22

#### 3. Soft Constraints (Blending) vs. Hard Constraints

**Decision**: Use 30% ML / 70% historical blending for placement

**Rationale**:
- Respects historical frequency (conservative)
- Nudges toward ML patterns (improvement)
- Avoids overfitting to small samples

**Alternatives Considered**:
- 100% ML (too aggressive, ignores context)
- 10% ML (too conservative, barely perceptible)

**Date**: 2025-10-22

#### 4. Ordering Constraints Threshold (90%)

**Decision**: Require ≥90% ordering ratio for mandatory rules

**Rationale**:
- High confidence (few false positives)
- Captures major patterns
- Avoids overfitting to noise

**Alternatives Considered**:
- 80% threshold (too noisy, many weak patterns)
- 95% threshold (too strict, misses real patterns)

**Date**: 2025-10-23

#### 5. Exclusions Applied Universally

**Decision**: Excluded songs filtered in all modes (not just ML)

**Rationale**:
- Simplicity over conditional logic
- Clearly non-musical content
- No valid use case for generation

**Date**: 2025-10-23

---

## Open Questions

### Technical

1. **Era-Specific Models**: Should we build separate feature sets for 1.0, 2.0, 3.0, 4.0 eras?
   - **Tradeoff**: Accuracy vs. complexity
   - **Decision**: Deferred to Phase 4

2. **Real-Time Feature Updates**: How to incrementally update features with new shows?
   - **Options**: Nightly batch, on-demand rebuild, streaming updates
   - **Decision**: TBD (not critical yet)

3. **Feature Versioning**: How to track which feature version generated each setlist?
   - **Approach**: Add `feature_version` field to generation metadata
   - **Decision**: Phase 3.3

### Product

1. **Predictive Accuracy Target**: What's "good enough" for `/predict` endpoint?
   - **Current Target**: >30% @ top-10
   - **Open**: Is this realistic? Useful?

2. **User Control**: How much ML parameter tuning should be exposed to users?
   - **Current**: 3 parameters (on/off, placement weight, transition bonus)
   - **Open**: Too complex? Too simple?

3. **Feature Discovery UI**: Should users see which features influenced generation?
   - **Example**: "Tweezer selected for Set 2 (78% ML probability)"
   - **Decision**: Phase 4.4 (visualization portal)

---

## Contributing

### How to Extend This Work

#### Add New Features

1. **Prototype in notebook** (`notebooks/ml/`)
2. **Migrate to** `src/phish_setlist_maker/analysis/features.py`
3. **Add to** `scripts/build_features.py`
4. **Test and document**
5. **Integrate with** `FeatureStore`
6. **Apply in** `SetlistGenerator`

#### Add New Constraints

1. **Discover rules** (scripts or manual analysis)
2. **Export to parquet** (`data/analytics/features/`)
3. **Load in** `FeatureStore`
4. **Enforce in** `SetlistGenerator._weighted_pick()`
5. **Test thoroughly** (unit + integration)
6. **Document in** `docs/ml/`

#### Improve Documentation

- Keep `AGENTS-ml.md` updated (high-level roadmap)
- Update detailed guides (`01-OVERVIEW`, `02-FEATURE-ENGINEERING`, etc.)
- Add examples and use cases
- Include visualizations/diagrams

---

## Resources

### Documentation

**Overview Guides** (this directory):
- `01-OVERVIEW-AND-SETUP.md` - Setup and data pipeline
- `02-FEATURE-ENGINEERING.md` - Features and insights
- `03-GENERATOR-INTEGRATION.md` - ML integration
- `04-CONSTRAINTS-SYSTEM.md` - Ordering and dependencies
- `05-ROADMAP-AND-FUTURE.md` - This document

**Legacy Docs** (still useful):
- `QUICKSTART.md` - Single-command getting started
- `schema-overview.md` - Database schema details
- `phase1-report.md` - Feature engineering results

### Code

**Key Modules**:
- `src/phish_setlist_maker/analysis/` - Feature engineering
- `src/phish_setlist_maker/generator/` - Setlist generation
- `src/phish_setlist_maker/api/` - REST API

**Scripts**:
- `scripts/build_features.py` - Rebuild all features
- `scripts/run_analytics_exports.py` - Export all data
- `scripts/discover_ordering_constraints.py` - Find ordering rules

### External Resources

- [Pandas User Guide](https://pandas.pydata.org/docs/user_guide/)
- [Scikit-learn Documentation](https://scikit-learn.org/stable/)
- [Phish.net API](https://api.phish.net/docu/) (data source)
- [Shannon Entropy](https://en.wikipedia.org/wiki/Entropy_(information_theory)) (versatility metric)
- [Association Rule Learning](https://en.wikipedia.org/wiki/Association_rule_learning) (transition mining)

---

## Conclusion

The ML & Data Analysis layer has successfully delivered:

✅ **Solid foundation** (Phase 0-1 complete)  
✅ **Production-ready features** (Phase 2.1-2.2 complete)  
✅ **Authentic generation** (686 constraints + 181 transitions)  
✅ **Zero regressions** (all tests pass)  
✅ **Extensible architecture** (easy to add features/constraints)

**Next priorities**:
1. **Phase 2.4**: Build `/predict` endpoint (high user value)
2. **Phase 3.2**: Add automated testing/monitoring (reliability)
3. **Phase 2.3**: Song similarity (nice-to-have enhancement)

**Long-term vision**: A data-driven setlist system that captures the essence of Phish's performance patterns while enabling creative exploration and prediction.

---

*For questions or contributions, see main project README or file issues on GitHub.*

**Project**: Phish Setlist Maker  
**ML Lead**: (TBD)  
**Last Major Update**: 2025-10-23
