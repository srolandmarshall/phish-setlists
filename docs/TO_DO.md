# Documentation Consolidation Plan
**Date**: 2025-11-07  
**Status**: PLANNING

---

## Phase 1: Root Docs Consolidation

### Current State (8 files)
1. **CODE_IMPROVEMENT_ROADMAP.md** (7.7K) - Prioritized dev improvements, CI/testing roadmap
2. **ERA-PICKER.md** (10K) - ⚠️ **FRONTEND** (UI feature, HTML, CSS, JavaScript) → DISCARD
3. **FLY-DEPLOYMENT.md** (5.2K) - Deployment guide (backend-relevant)
4. **FREQUENCY-CAP-SUMMARY.md** (6.4K) - Feature/heuristic documentation
5. **IMPLEMENTATION-SUMMARY.md** (6.5K) - Implementation notes (may contain UI)
6. **SESSION-SUMMARY.md** (8.3K) - Session notes (check for UI)
7. **SET-ENDING-TRACKS-SUMMARY.md** (8.2K) - Feature documentation
8. **TOOLTIP-FEATURE.md** (5.6K) - ⚠️ **FRONTEND** (UI tooltips) → DISCARD

### Consolidation Strategy

**Target**: Single `docs/BACKEND_REFERENCE.md`

**Steps**:
1. Read all 8 root docs for content inventory
2. Identify and remove all frontend references (UI, HTML, CSS, JS, landing page, buttons, forms)
3. Extract backend-relevant sections:
   - Development roadmap (from CODE_IMPROVEMENT_ROADMAP)
   - Deployment procedures (from FLY-DEPLOYMENT)
   - Core heuristics & features (from FREQUENCY-CAP-SUMMARY, SET-ENDING-TRACKS-SUMMARY, IMPLEMENTATION-SUMMARY, SESSION-SUMMARY)
4. Merge into single coherent document with clear sections
5. Delete originals after consolidation

---

## Phase 2: ML Docs Review & Condensing

### Current State (11 files in docs/ml/)

**Numbered Series** (likely sequential/related):
- 01-OVERVIEW-AND-SETUP.md (11K) - Setup, commands, db schema
- 02-FEATURE-ENGINEERING.md (15K) - Feature definitions and metrics
- 03-GENERATOR-INTEGRATION.md (18K) - How features integrate with core
- 04-CONSTRAINTS-SYSTEM.md (23K) - Ordering, dependencies, exclusions
- 05-ROADMAP-AND-FUTURE.md (23K) - Roadmap and strategic work
- 06-SET-ENDING-AND-FREQUENCY.md (13K) - Set-ending heuristics
- 06-JAMMINESS-AND-DURATION-CONTROL.md (13K) - ⚠️ **DUPLICATE NUMBER** (jamminess mechanics)
- 07-JAMMINESS-AND-DURATION-CONTROL.md (13K) - ⚠️ **DUPLICATE** (updated version?)

**Support Docs**:
- ml-libraries-cheatsheet.md (1.4K) - Pandas/numpy/sklearn patterns
- README.md (15K) - Entry point/overview
- schema-overview.md (5.0K) - Detailed table docs

### Consolidation Strategy

**Target**: Clean up to 5-6 focused documents

**Steps**:
1. Read all 11 files and scan for:
   - Frontend references (UI-specific ML features) → DISCARD
   - Duplicated sections across files → MERGE
   - Handle 06/07 duplicates (resolve which to keep)
2. Identify thematic groups:
   - **Setup & Infrastructure**: 01 + bootstrap/schema content
   - **Feature Engineering**: 02 + parts of 06/07
   - **Generator Integration**: 03 + 04 constraints
   - **Heuristics Deep Dives**: 06-SET-ENDING + 06/07-JAMMINESS
   - **Roadmap & Future Work**: 05
3. Condense without losing context:
   - Remove repetition
   - Consolidate related patterns
   - Keep key metrics and formulas
   - Keep decision rationale
4. Resulting structure:
   - `docs/ml/README.md` - High-level overview (freshened)
   - `docs/ml/01-SETUP.md` - Environment, commands, schema
   - `docs/ml/02-FEATURES.md` - Consolidated feature definitions
   - `docs/ml/03-CONSTRAINTS-HEURISTICS.md` - Generator constraints, jamminess, set-ending
   - `docs/ml/04-ROADMAP.md` - Strategic work
   - `docs/ml/CHEATSHEET.md` - Library patterns (keep as-is)

---

## Phase 3: ML Summary Doc (Root Level)

### New Document: `docs/ML-OVERVIEW.md`

**Purpose**: High-level birds-eye view of ML process for root docs

**Structure** (similar to 01-OVERVIEW-AND-SETUP but updated):
- **Objective**: Why ML exists (deepens setlist understanding, drives generation)
- **High-Level Architecture**: Data → Export → Features → Generator integration flow
- **Core Capabilities**: What the ML layer enables
- **Quick Start**: Main commands (run_analytics_exports, build_features)
- **Key Concepts** (concise):
  - Feature types (placement, transitions, constraints)
  - Jamminess & duration control
  - Set-ending & frequency rules
- **Integration Points**: How ML feeds into generation
- **Next Steps**: Link to detailed docs in ml/
- **Key Files Reference**: Important scripts and modules

**Length Target**: ~2K words (condensed from ~11K of scattered docs)

---

## Deliverables Summary

### To Be Created
- ✅ `docs/BACKEND_REFERENCE.md` (merged root docs, no frontend)
- ✅ `docs/ML-OVERVIEW.md` (new birds-eye ML summary)
- ✅ `docs/ml/README.md` (freshened, references consolidated docs)
- ✅ `docs/ml/01-SETUP.md` (setup & commands)
- ✅ `docs/ml/02-FEATURES.md` (feature engineering consolidated)
- ✅ `docs/ml/03-CONSTRAINTS-HEURISTICS.md` (constraints, jamminess, set-ending)
- ✅ `docs/ml/04-ROADMAP.md` (future work)

### To Be Deleted
- ❌ `docs/ERA-PICKER.md` (frontend)
- ❌ `docs/TOOLTIP-FEATURE.md` (frontend)
- ❌ `docs/01-OVERVIEW-AND-SETUP.md` (content moved to 01-SETUP)
- ❌ `docs/02-FEATURE-ENGINEERING.md` (content merged into 02-FEATURES)
- ❌ `docs/03-GENERATOR-INTEGRATION.md` (content merged into 03-CONSTRAINTS-HEURISTICS)
- ❌ `docs/04-CONSTRAINTS-SYSTEM.md` (content merged into 03-CONSTRAINTS-HEURISTICS)
- ❌ `docs/05-ROADMAP-AND-FUTURE.md` (content moved to 04-ROADMAP)
- ❌ `docs/06-SET-ENDING-AND-FREQUENCY.md` (content merged into 03-CONSTRAINTS-HEURISTICS)
- ❌ `docs/06-JAMMINESS-AND-DURATION-CONTROL.md` (duplicate, merge into 03)
- ❌ `docs/07-JAMMINESS-AND-DURATION-CONTROL.md` (likely duplicate, merge into 03)

### Kept As-Is
- ✅ `docs/ml/CHEATSHEET.md` (support reference)
- ✅ `docs/ml/schema-overview.md` (detail reference)
- ✅ `docs/FLY-DEPLOYMENT.md` → `docs/BACKEND_REFERENCE.md` (merged)
- ✅ `docs/CODE_IMPROVEMENT_ROADMAP.md` → `docs/BACKEND_REFERENCE.md` (merged)
- ✅ `docs/FREQUENCY-CAP-SUMMARY.md` → `docs/BACKEND_REFERENCE.md` (merged)
- ✅ `docs/IMPLEMENTATION-SUMMARY.md` → `docs/BACKEND_REFERENCE.md` (merged)
- ✅ `docs/SESSION-SUMMARY.md` → `docs/BACKEND_REFERENCE.md` (merged)
- ✅ `docs/SET-ENDING-TRACKS-SUMMARY.md` → `docs/BACKEND_REFERENCE.md` (merged)

---

## ✅ COMPLETION STATUS

### Phase 1: Root Docs Consolidation ✅ COMPLETE
- ✅ Created `docs/BACKEND_REFERENCE.md` (17K)
  - Merged CODE_IMPROVEMENT_ROADMAP.md
  - Merged FLY-DEPLOYMENT.md
  - Merged FREQUENCY-CAP-SUMMARY.md
  - Merged IMPLEMENTATION-SUMMARY.md
  - Merged SESSION-SUMMARY.md
  - Merged SET-ENDING-TRACKS-SUMMARY.md
  - **Excluded**: ERA-PICKER.md (frontend), TOOLTIP-FEATURE.md (frontend)
  
### Phase 2: ML Docs Condensing ✅ COMPLETE
- ✅ Created `docs/ml/01-SETUP.md` (6.4K) - Setup, commands, schema
- ✅ Created `docs/ml/02-FEATURES.md` (6.8K) - Feature engineering
- ✅ Created `docs/ml/03-CONSTRAINTS-HEURISTICS.md` (8.6K) - All constraints merged
  - Merged: 03-GENERATOR-INTEGRATION.md
  - Merged: 04-CONSTRAINTS-SYSTEM.md
  - Merged: 06-SET-ENDING-AND-FREQUENCY.md
  - Merged: 06-JAMMINESS-AND-DURATION-CONTROL.md (old)
  - Merged: 07-JAMMINESS-AND-DURATION-CONTROL.md (new)
- ✅ Created `docs/ml/04-ROADMAP.md` (9.8K) - Future work
  - Replaces: 05-ROADMAP-AND-FUTURE.md

### Phase 3: ML Summary Doc (Root) ✅ COMPLETE
- ✅ Created `docs/ML-OVERVIEW.md` (9.2K)
  - Birds-eye view of ML process
  - Architecture overview
  - Quick start guide
  - Integration points
  - For backend developers

---

## Ready for Deletion

**Root docs** (8 files to delete):
- docs/ERA-PICKER.md
- docs/TOOLTIP-FEATURE.md
- docs/CODE_IMPROVEMENT_ROADMAP.md
- docs/FLY-DEPLOYMENT.md
- docs/FREQUENCY-CAP-SUMMARY.md
- docs/IMPLEMENTATION-SUMMARY.md
- docs/SESSION-SUMMARY.md
- docs/SET-ENDING-TRACKS-SUMMARY.md

**ML docs** (9 files to delete):
- docs/ml/01-OVERVIEW-AND-SETUP.md
- docs/ml/02-FEATURE-ENGINEERING.md
- docs/ml/03-GENERATOR-INTEGRATION.md
- docs/ml/04-CONSTRAINTS-SYSTEM.md
- docs/ml/05-ROADMAP-AND-FUTURE.md
- docs/ml/06-SET-ENDING-AND-FREQUENCY.md
- docs/ml/06-JAMMINESS-AND-DURATION-CONTROL.md (duplicate)
- docs/ml/07-JAMMINESS-AND-DURATION-CONTROL.md (duplicate)

**Status**: Ready to clean up old docs

---

## CRITICAL DISCOVERY: Ordering Rules Implementation Gap

**Found**: `docs/figures/README.md` + CSV data + visualizations

### Current State
- ✅ 686 ordering constraints discovered & documented
- ✅ 3 CSV files with constraint data:
  - `famous_song_sequences.csv` (36 sequences, >95% confidence)
  - `top_50_ordering_rules.csv` (50 rules by set type)
  - `top_50_song_pairs.csv` (50 pairs across all sets)
- ✅ Visualizations (4 PNG files):
  - `entropy_distribution.png`
  - `set_placement_heatmap.png`
  - `temporal_trends.png`
  - `transition_network.png`
- ❌ **NOT FULLY INTEGRATED** - Rules exist but may not be properly enforced in generator

### What Needs to Be Done (NEXT PRIORITY)

This is identified as the next critical work item. The ordering rules need to be:

1. **Verified in Generator**: Check if 686 rules are actually being applied during generation
2. **Integration Testing**: Generate 100+ setlists and validate rule compliance
3. **Performance Analysis**: Measure overhead of constraint checking
4. **Documentation**: Cross-link constraint system with actual CSV data

### Integration Notes

The ordering rules data should be incorporated into:
- `docs/ml/03-CONSTRAINTS-HEURISTICS.md` → Add reference to CSV files
- `docs/ml/02-FEATURES.md` → Link to constraint data source
- New section: "Ordering Rules Data Reference"

### CSV Data Structure

Each CSV contains critical metadata:
- **famous_song_sequences.csv**: 36 iconic sequences (>50 plays, >95% consistent)
- **top_50_ordering_rules.csv**: Most frequent pairs by set type
- **top_50_song_pairs.csv**: Top pairs across all sets

Example top rule:
```
Mike's Song → Weekapaug Groove: 511 times (99.4% consistency)
```

**Action**: Verify these are all enforced in `generator/core.py` ordering validation logic
