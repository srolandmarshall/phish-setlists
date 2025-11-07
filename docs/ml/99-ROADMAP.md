# ML & Data Analysis — Roadmap & Future Work

**Last Updated**: November 7, 2025

---

## Completed Features

### Phase 1: Foundation (2025-10)
- ✅ Historical analysis (2,104+ shows)
- ✅ Feature engineering (song placement, transitions)
- ✅ Generator integration
- ✅ Set placement probabilities
- ✅ Transition patterns

### Phase 2: Constraints & Rules (2025-10)
- ✅ 686 ordering constraints
- ✅ Cross-set dependencies (Tweezer/Reprise)
- ✅ Excluded songs filter (12 songs)
- ✅ Set-ending selection
- ✅ Frequency caps for rare songs

### Phase 3: Jamminess & Duration (2025-10)
- ✅ Multi-percentile duration system (p30/p50/p70/p90)
- ✅ User jamminess parameter (0.0-1.0)
- ✅ Dynamic song count adjustment
- ✅ Constraint relaxation per jamminess
- ✅ 85-98% duration compliance

### Phase 4: Quality Analysis (2025-10)
- ✅ Frequency analysis tool
- ✅ Set-ending track selection
- ✅ Outlier detection
- ✅ Historical comparison

---

## Current Capabilities

### Core ML Features
- Song placement probabilities (389 songs × 4 sets)
- High-confidence transitions (181 rules)
- Mandatory song orderings (686 rules)
- Cross-set dependencies (Tweezer rule)
- Frequency caps (rare song protection)
- Set-ending selection (5,761 authentic tracks)
- Era-aware filtering (4 eras supported)

### Accuracy
- Set 1 duration compliance: 100%
- Set 2 duration compliance: 98%
- Ordering rule adherence: 99%+
- Transition authenticity: 95%+

---

## Planned Enhancements

### Short-Term (1–3 weeks)

#### 1. Opener Selection
**Goal**: Authentic set openers (opposite of set-ending)

**Approach**: Similar to set-ending selection
- Build `set_opening_frequencies.parquet`
- Create `set_opening_tracks.parquet` lookup
- Weight by historical opening probability

**Expected Impact**: Set 1 openers now data-driven

**Est**: 2–3 days

#### 2. Position-Specific Modeling
**Goal**: Mid-set jammers, set peaks, etc.

**Approach**: 
- Analyze song positions within sets (1st, 2nd, ..., last)
- Build position probability tables
- Guide candidate selection per position

**Expected Impact**: More realistic song flow

**Est**: 3–5 days

#### 3. Venue-Specific Preferences
**Goal**: Location-influenced setlist patterns

**Approach**:
- Analyze 764 venues for local patterns
- Build venue-affinity scores per song
- Apply light weighting during generation

**Expected Impact**: Geographically-aware sets

**Est**: 2–4 days

---

### Medium-Term (3–7 weeks)

#### 4. Configurable Constraints
**Goal**: Allow users to tune heuristics

**Approach**:
- Expose frequency cap thresholds (currently 30/50)
- Allow era-specific constraints
- Enable/disable per-rule filters

**Expected Impact**: Power users can customize

**Est**: 1 week

#### 5. Stronger Typing & Refactoring
**Goal**: Reduce technical debt, improve maintainability

**What**:
- Add return types to feature functions
- Use Pydantic models for feature data
- Extract selection strategy classes
- Add type annotations throughout

**Expected Impact**: Cleaner code, fewer bugs

**Est**: 2 weeks

#### 6. Enhanced Testing
**Goal**: Edge case coverage and regression prevention

**What**:
- Unit tests for feature loading edge cases
- Integration tests with mocked API
- Jamminess boundary tests (0.0, 0.5, 1.0)
- Ordering violation detection

**Expected Impact**: Confidence in changes

**Est**: 1–2 weeks

---

### Long-Term (2–8 weeks)

#### 7. ML-Based Duration Prediction
**Goal**: Machine-learned duration models per song

**Approach**:
- Train regression models on historical track durations
- Factor era, venue, season, jamminess
- More accurate duration estimates

**Expected Impact**: Tighter duration control

**Tools**: scikit-learn RandomForest or XGBoost

**Est**: 3–5 weeks

#### 8. Song Recommender System
**Goal**: Predict "next likely song" given history

**Approach**:
- Build transition probability matrices
- Train Markov chain or neural model
- Use for weighted random selection

**Expected Impact**: More coherent setlist flow

**Est**: 3–5 weeks

#### 9. Production Readiness
**Goal**: Robust, observable, scalable ML pipeline

**What**:
- Docker compose with seed data
- Deterministic E2E tests
- Metrics/monitoring for feature staleness
- Database versioning for features
- CI/CD for feature rebuilds

**Expected Impact**: Production-grade reliability

**Est**: 2–5 weeks

#### 10. Lazy-Loading & Memory Optimization
**Goal**: Handle larger feature sets efficiently

**Approach**:
- Index parquet files for quick filtering
- Use Dask for out-of-core processing
- Cache only hot features in memory

**Expected Impact**: Scales to 10K+ songs

**Est**: 2–4 weeks

---

## Research Opportunities

### Exploration Ideas

#### A. Setlist Grammar
**Q**: Do Phish setlists follow a grammar? (e.g., narrative arc?)

**Approach**:
- Analyze successful setlist structures
- Discover opening → mid-set → closing patterns
- Build context-free grammar

**Expected Insight**: Automated structure validation

#### B. Era Transitions
**Q**: How did songs migrate between eras?

**Approach**:
- Track song frequency trends across eras
- Identify new songs per era
- Model retirement patterns

**Expected Insight**: Better era-specific constraints

#### C. Tour Effects
**Goal**: Do songs appear more frequently during same tour?

**Approach**:
- Analyze play frequency by tour
- Detect tour-specific patterns
- Model "tour rotation" effect

**Expected Insight**: Tour-aware generation

#### D. Venue Clustering
**Goal**: Group venues by setlist patterns

**Approach**:
- Clustering analysis of venue setlist types
- Geographic + content-based grouping
- Venue similarity metrics

**Expected Insight**: Venue-class-aware generation

#### E. Acoustic vs Electric Variations
**Goal**: Model song variations (acoustic, sit-ins, etc.)

**Approach**:
- Track song aliases and variations
- Build variation frequency tables
- Weight by era/venue

**Expected Insight**: More setlist diversity

---

## Metrics & Success Criteria

### Current KPIs

| Metric | Target | Current |
|--------|--------|---------|
| Set 1 duration compliance | 100% | ✅ 100% |
| Set 2 duration compliance | 95%+ | ✅ 98% |
| Rare song frequency | <5% | ✅ <2% |
| Ordering rule adherence | 99%+ | ✅ 99%+ |
| Excluded songs | 0% | ✅ 0% |

### Future KPIs

| Metric | Proposed |
|--------|----------|
| Setlist authenticity score | 85%+ (expert validation) |
| Transition naturalness | 90%+ (user feedback) |
| Era specificity | 95%+ (era-appropriate songs) |
| Venue relevance | 75%+ (venue-specific patterns) |
| Feature staleness | <30 days |

---

## Architecture Roadmap

### Phase A: Consolidation (Now)
- Merge duplicate docs
- Condense 11 ML docs → 5 focused docs
- Create unified backend reference

### Phase B: Refactoring (Q1)
- Extract strategy classes from generator
- Add comprehensive type hints
- Modernize feature loading

### Phase C: Scale (Q2)
- Implement lazy-loading for large feature sets
- Add database versioning for features
- Build CI/CD for feature rebuilds

### Phase D: Capabilities (Q2-Q3)
- Opener selection
- Position-specific modeling
- Venue-aware generation
- Tour-aware effects

### Phase E: Intelligence (Q3+)
- ML-based duration prediction
- Song recommender (next-song prediction)
- Setlist grammar extraction
- Multi-objective optimization

---

## Dependencies & Blockers

### Current
- None - system fully functional

### Potential
- **Large feature sets**: Requires lazy-loading (Phase C)
- **Real-time performance**: May need caching layer (Phase C)
- **User customization**: Requires API extensions (Phase B)

---

## Contributing

### Adding a New Heuristic

1. **Prototype in notebook**: `notebooks/ml/`
2. **Extract to feature function**: `src/phish_setlist_maker/analysis/features.py`
3. **Build feature table**: `scripts/build_features.py`
4. **Add to FeatureStore**: `feature_store.py`
5. **Integrate to generator**: `generator/core.py`
6. **Write unit tests**: `tests/`
7. **Document**: Update `docs/ml/`

### Adding a New Constraint

1. **Define in dataclass**: `src/phish_setlist_maker/models/`
2. **Load in generator**: Constructor
3. **Apply in logic**: `_build_candidate_pool()` or `_select_with_duration_budget()`
4. **Validate in tests**: Test both compliance and edge cases
5. **Document**: Add to `03-CONSTRAINTS-HEURISTICS.md`

### Testing New Features

```bash
# Unit test
poetry run pytest tests/test_your_feature.py -v

# Integration test (generate 100 setlists)
poetry run python -c "
from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator.core import SetlistGenerator

with session_scope() as s:
    gen = SetlistGenerator(s, use_ml_features=True)
    for i in range(100):
        result = gen.generate(num_sets=2)
        # Validate your constraint here
"

# Frequency analysis
poetry run python scripts/analyze_generation_frequency.py -n 100
```

---

## Known Limitations

1. **Feature staleness**: Parquet files not auto-rebuilt (requires manual script run)
2. **No user preferences**: Can't currently save user preferences for future generations
3. **Limited era coverage**: Only 4 eras defined; pre-1983 unavailable
4. **No setlist explanations**: Can't explain why certain songs appear
5. **No multi-show context**: Can't prevent same setlist across consecutive shows

---

## Performance Baselines

| Operation | Time | Memory |
|-----------|------|--------|
| Load all features | ~150ms | ~100MB |
| Generate 1 setlist | ~500ms | ~10MB |
| Generate 100 setlists | ~50s | ~15MB |
| Analyze frequency (100) | ~2m | ~50MB |

**Hardware**: MacBook Pro M1, 16GB RAM

---

## Support & Questions

- **Documentation**: See `01-SETUP.md`, `02-FEATURES.md`, `03-CONSTRAINTS-HEURISTICS.md`
- **Code**: `src/phish_setlist_maker/analysis/`, `generator/`
- **Scripts**: `scripts/build_features.py`, `scripts/analyze_generation_frequency.py`
- **Tests**: `tests/test_generator.py`, `tests/test_feature_store.py`

---

**Status**: In Active Development  
**Next Review**: Q1 2026  
**Maintainer**: Development Team
