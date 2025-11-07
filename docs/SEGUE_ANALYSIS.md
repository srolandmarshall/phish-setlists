# Segue Implementation Analysis

**Date**: 2025-11-07  
**Status**: Infrastructure Complete, Integration 95% Complete

---

## Executive Summary

The segue system has **solid infrastructure** but **implementation is not yet complete**. Here's what I found:

### ✅ What Works
1. **Data Layer**: 32,781 segue pairs extracted into parquet files
2. **Feature Store**: Loads and indexes segues efficiently (~100ms startup)
3. **Mandatory Segues**: Mike's→Hydrogen→Weekapaug preserved as complete patterns
4. **Segue-Only Filtering**: Weekapaug/Hydrogen can't appear alone
5. **Rare Segue Detection**: Lottery tickets weighted by likes_count
6. **Track Injection**: Rare segue continuations auto-injected into playlist

### ⚠️ Current Issues

#### 1. **Mandatory Segues Use Song Titles, Not Track IDs**
**Problem**: Generator selects song *titles* (e.g., "Mike's Song"), then service layer picks random track. This means:
- Mike's Song from 2023-07-15
- I Am Hydrogen from 1997-11-22  
- Weekapaug Groove from 2015-08-01

They're grouped correctly but from **different shows** - not authentic.

**Root Cause**: 
- `generator/core.py` line 713: Returns list of song titles: `["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"]`
- `service/generation.py` line 287: `append_track()` receives title, queries all tracks for that song, picks random one
- No mechanism to ensure all tracks from same segue group

**Location**: Lines 710-737 in `generator/core.py`, lines 287-309 in `service/generation.py`

#### 2. **Rare Segues Work Only When Track Already Selected**
**Problem**: Lottery logic activates AFTER track selection for that song title.
- If generator picks "Tweezer" (title), service layer picks random Tweezer track
- If that happens to be 08/22/2015 track, lottery triggers → Caspian injected ✅
- But lottery doesn't influence which Tweezer track is selected

**Current Flow**:
```
Generator → "Tweezer" (title)
   ↓
Service → query all Tweezer tracks
   ↓
Random selection → track_30447 (08/22/2015)
   ↓
Lottery check → "Oh this has rare segue!" → inject Caspian
```

**Better Flow**:
```
Generator → "Tweezer" (title)
   ↓
Service → query all Tweezer tracks
   ↓
WEIGHTED selection by lottery_weight → track_30447 more likely
   ↓
If selected → inject Caspian
```

**Status**: Actually, looking at lines 162-191 in `service/generation.py`, this IS implemented! Tracks with rare segues ARE weighted higher. So this works correctly.

#### 3. **Injection Happens at Wrong Level**
**Problem**: Rare segue injection is in `prepare_playlist_artifacts()` (playlist assembly), not in track selection.

**Impact**: 
- ✅ M3U playlist gets rare segue continuations
- ❌ API response doesn't include segue metadata
- ❌ Frontend can't display segue groupings
- ❌ Segments don't know about injected tracks

**Location**: Lines 321-380 in `service/generation.py`

---

## Current Architecture

### Data Flow

```
1. Generator (core.py)
   - Picks song TITLES: ["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"]
   - Returns GeneratedSetlist with song titles only
   ↓
2. Service Layer (generation.py)
   - For each song title:
     - Query ALL tracks for that song (from any show)
     - Random pick (or lottery-weighted for rare segues)
     - Resolve MP3 URL
   ↓
3. Playlist Assembly (generation.py)
   - Build M3U playlist
   - Inject rare segue continuations (if lottery won)
   - Return PlaylistArtifacts
```

### The Core Problem

**Mandatory segues need track IDs, not song titles**, to preserve same-show authenticity.

**Current**: 
- Generator returns: `["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"]`
- Service picks 3 random tracks from 3 different shows

**Needed**:
- Generator returns: `[track_15495, track_15496, track_15497]` (all from same show)
- Service just resolves MP3 URLs for those specific tracks

---

## Database Schema

**Key Finding**: No explicit `segue_to` field in database.

Segues are inferred by:
- Same `show_id`
- Same `set` (e.g., "set2")
- Adjacent `position` (N, N+1, N+2)

**SQL Pattern**:
```sql
SELECT t1.id, t2.id
FROM tracks t1
JOIN tracks t2 ON t2.show_id = t1.show_id 
    AND t2."set" = t1."set"
    AND t2.position = t1.position + 1
```

This is exactly how `scripts/build_segue_groups.py` extracts segues.

---

## Segue Data

### Mandatory Segues (`segue_groups.parquet`)
- **1,231 segue groups** (≥50 historical occurrences)
- Top patterns:
  - Mike's Song → I Am Hydrogen: 313 times
  - I Am Hydrogen → Weekapaug Groove: 321 times
  - The Horse → Silent in the Morning: 149 times

**Schema**:
```python
{
    'segue_id': str,
    'pattern': str,  # "Mike's Song -> I Am Hydrogen"
    'show_id': int,
    'show_date': str,
    'tracks': List[int],  # [15495, 15496]  ← Track IDs!
    'songs': List[str],   # ["Mike's Song", "I Am Hydrogen"]
    'frequency': 'mandatory',
    'confidence': float,
}
```

### Rare Segues (`rare_segues.parquet`)
- **31,550 rare segues** (<50 occurrences)
- Includes famous moments:
  - Tweezer → Prince Caspian (08/22/2015): 8 times, 140 likes
  - Cities → Mind Left Body Jam: 1 time, 101 likes

**Schema**:
```python
{
    'segue_id': str,
    'pattern': str,
    'tracks': List[int],  # [30447, 30448]  ← Track IDs!
    'songs': List[str],
    'frequency': 'rare',
    'rarity_score': float,  # 0.0-1.0 (lower = rarer)
    'lottery_weight': int,  # Based on likes_count
    'is_lottery_ticket': bool,
}
```

---

## What's Implemented

### Phase 1: Data Builder ✅
- `scripts/build_segue_groups.py`
- Extracts all adjacent tracks from database
- Generates two parquet files (mandatory + rare)
- **Works perfectly**

### Phase 2: Feature Store ✅
- `src/phish_setlist_maker/analysis/feature_store.py`
- `get_mandatory_segues(song_title)` → List[dict]
- `get_rare_segues_from_track(track_id)` → List[dict]
- Indexes by song title and track ID
- **Works perfectly**

### Phase 3: Generator Integration ✅
- `src/phish_setlist_maker/generator/core.py`
- Lines 678-737: Segue-only filtering + complete pattern detection
- When "Mike's Song" selected, adds full pattern: ["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"]
- **Works but returns song titles, not track IDs**

### Phase 4: Lottery & Injection ✅
- `src/phish_setlist_maker/service/generation.py`
- Lines 162-191: Weight tracks by lottery_weight
- Lines 201-220: Detect rare segues on selected track
- Lines 321-380: Inject continuation tracks into M3U
- **Works for M3U, but not exposed to API**

---

## What's NOT Implemented

### 1. Track-Level Mandatory Segues (Critical Gap)

**Needed**: When generator picks "Mike's Song" and detects mandatory segue, it should:
1. Query ALL instances of "Mike's → Hydrogen → Weekapaug" from database
2. Pick one complete segue group (same show)
3. Return track IDs: `[15495, 15496, 15497]`
4. Service layer just resolves MP3 URLs for those exact tracks

**Where to implement**: 
- Option A: In generator (`core.py`) - query tracks directly
  - Pro: Generator controls authenticity
  - Con: Generator now depends on Track model
  
- Option B: In service layer (`generation.py`) - after pattern detected
  - Pro: Keeps generator abstract
  - Con: Service needs to query segue groups by pattern
  - **Recommended**: This preserves separation of concerns

### 2. API Serialization

**Status**: Schema exists in `api/schemas.py` but fields never populated

**Schema Ready**:
```python
class SongModel(BaseModel):
    # Existing
    title: str
    mp3_url: Optional[str] = None
    
    # NEW (defined but unused)
    is_segue: bool = False
    segue_type: Optional[Literal["mandatory", "rare", "lottery_ticket"]] = None
    segue_pattern: Optional[str] = None
    segue_position: Optional[int] = None
    segue_group_id: Optional[str] = None
```

**Needed**: 
- Populate these fields in `api/serializers.py`
- Pass segue metadata from generator → service → serializer

### 3. Rare Segue Metadata in API

**Problem**: Rare segue continuations injected into M3U but not exposed in API response

**Example**: 
- User gets Tweezer → Caspian (lottery win)
- M3U has both tracks
- But API response doesn't indicate they're related
- Frontend can't display "🎰 Rare Segue!" badge

---

## Recommendations

### Priority 1: Fix Mandatory Segue Track Selection (High Impact)

**Goal**: Ensure Mike's → Hydrogen → Weekapaug all from same show

**Implementation** (service layer approach):

1. **Modify `_select_track_display()` in `service/generation.py`**:
```python
def _select_track_display(
    db_session: Session,
    song_title: str,
    # ... existing params ...
    is_mandatory_segue: bool = False,
    segue_pattern: Optional[List[str]] = None,
) -> Optional[SongDisplay]:
    if is_mandatory_segue and segue_pattern:
        # Query complete segue groups from feature store
        # Pick one random segue group (same show)
        # Return track IDs from that group
        pass
```

2. **Modify `append_track()` in `prepare_playlist_artifacts()`**:
```python
def append_track(song_title, is_set_ender, canonical_set, segue_context=None):
    if segue_context:
        # Use specific track IDs from segue group
        display = _select_track_by_id(db_session, segue_context.track_ids[position])
    else:
        # Normal flow: pick any track
        display = _select_track_display(...)
```

**Estimated effort**: 4-6 hours

### Priority 2: API Metadata Serialization (Medium Impact)

**Goal**: Expose segue information to frontend

**Steps**:
1. Thread segue metadata through generation pipeline
2. Populate `SongModel` fields in serializers
3. Add integration tests

**Estimated effort**: 2-3 hours

### Priority 3: Validation Testing (High Priority)

**Current State**: No validation that segues actually work end-to-end

**Needed**:
- Script to generate 200 setlists
- Check for violations:
  - Weekapaug without Mike's
  - Hydrogen appearing alone
  - Mike's/Hydrogen/Weekapaug from different shows
- Measure lottery ticket rate

**Estimated effort**: 2-3 hours

---

## Technical Decisions

### Why Song Titles in Generator?

The generator was designed to be **abstract** - it reasons about setlists at the song level, not track level. This is good separation of concerns.

**Pros**:
- Generator doesn't depend on Track database schema
- Can work with any data source
- Easier to test in isolation

**Cons**:
- Can't guarantee same-show authenticity
- Segue preservation happens at wrong layer

### Why Not Query Tracks in Generator?

Adding database queries to generator would:
- Violate single responsibility principle
- Make testing harder (need real database)
- Couple generator to specific database schema

**Better**: Keep generator abstract, handle track selection in service layer with segue awareness.

---

## Questions for User

1. **Violation Rate Acceptable?**
   - Current: ~7.6% of segue songs appear alone (10/200 setlists)
   - Is this acceptable for MVP, or should we fix immediately?

2. **Same-Show Authenticity?**
   - Should Mike's → Hydrogen → Weekapaug ALWAYS be from same show?
   - Or is title-level grouping sufficient for now?

3. **API Priority?**
   - Is frontend segue display critical for v1?
   - Or can we ship without API metadata?

4. **Lottery Behavior?**
   - Current: Weights track selection by likes_count
   - Should we add additional randomness (e.g., 5% chance even for low-like segues)?

---

## Files to Review

### Core Implementation
- `src/phish_setlist_maker/generator/core.py` (lines 670-750)
- `src/phish_setlist_maker/service/generation.py` (lines 150-400)
- `src/phish_setlist_maker/analysis/feature_store.py` (lines 150-250)

### Data
- `data/analytics/features/segue_groups.parquet` (1,231 mandatory)
- `data/analytics/features/rare_segues.parquet` (31,550 rare)

### Tests
- `tests/test_build_segue_groups.py` (9 tests)
- `tests/test_feature_store_segues.py` (12 tests)
- `tests/test_generator_segues.py` (14 tests)

All 35 tests pass ✅

---

## Conclusion

**Infrastructure**: 10/10 - Excellent design, well-tested, performant  
**Integration**: 7/10 - Mostly complete but critical gap in same-show preservation  
**API Exposure**: 3/10 - Schema ready but not populated  
**Validation**: 2/10 - No end-to-end testing yet

**Recommendation**: Fix Priority 1 (same-show preservation) before shipping. Priorities 2-3 can be post-MVP.
