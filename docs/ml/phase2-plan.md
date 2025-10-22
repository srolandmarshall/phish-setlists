# Phase 2 Implementation Plan

**Started**: 2025-10-22  
**Goal**: Integrate ML features into `/generate` endpoint and build foundational prediction models

---

## Phase 2.1: Feature Integration into Generator Logic

### Step 1: Feature Store Module ✅ NEXT
Create `src/phish_setlist_maker/analysis/feature_store.py` to:
- Load parquet files from `data/analytics/features/`
- Provide fast lookup for song placement probabilities and transition lifts
- Cache features in memory for performance

### Step 2: Generator Enhancement
Modify `src/phish_setlist_maker/generator/core.py` to:
- Add optional `use_ml_features` flag to `SetlistGenerator.__init__`
- Inject placement probability soft constraints into song selection
- Apply transition lift bonuses to historically-paired songs
- Maintain backward compatibility (default: `use_ml_features=False`)

### Step 3: API Integration
Update `src/phish_setlist_maker/api/schemas.py`:
- Add `use_ml_features: bool = False` to `GenerateRequestModel`
- Pass through to generator initialization

### Step 4: Testing & Validation
- Generate sample setlists with/without ML features
- Document differences in generation metadata
- Add unit tests for feature loading

---

## Phase 2.2: Markov Chain Sequence Model

### Step 1: Model Builder
Create `scripts/build_markov_model.py`:
- Load transition data from Phase 1
- Build transition probability matrices per set type
- Serialize to `data/analytics/models/markov_chain.pkl`

### Step 2: Model Integration
Create `src/phish_setlist_maker/analysis/sequence_models.py`:
- Load Markov chain model
- Provide `predict_next_song(current_song, set_type)` function
- Return probability-ranked candidates

### Step 3: Generator Hook
Add optional Markov-based song ordering to generator:
- After selecting songs, optionally reorder using transition probabilities
- Toggle via `use_sequence_model` flag

---

## Phase 2.4: `/predict` Endpoint (Basic)

### Step 1: Prediction Engine
Create `src/phish_setlist_maker/service/prediction.py`:
- Combine song features (set placement probs) with recency penalties
- Use Markov model to suggest likely sequences
- Return top-N predictions per set

### Step 2: API Endpoint
Add to `src/phish_setlist_maker/api/__init__.py`:
- `GET /predict?date=YYYY-MM-DD&tour_id=X`
- `POST /predict` with override payload
- Return JSON with probability-ranked songs

### Step 3: Validation
Create `notebooks/ml/phase2_model_validation.ipynb`:
- Back-test predictions on historical shows
- Measure hit rate @ top-5, top-10, top-20
- Document accuracy metrics

---

## Success Criteria

- ✅ Feature store loads Phase 1 data in <100ms
- ✅ Generator produces valid setlists with ML features enabled
- ✅ `/predict` endpoint returns sensible probability rankings
- ✅ Back-test hit rate > 30% @ top-10 for next-show prediction
- ✅ All existing tests pass (no regressions)

---

## Timeline Estimate

- **2.1 Feature Integration**: 2-3 hours
- **2.2 Markov Model**: 1-2 hours  
- **2.4 /predict Endpoint**: 2-3 hours
- **Testing & Validation**: 1-2 hours

**Total**: 6-10 hours of focused work
