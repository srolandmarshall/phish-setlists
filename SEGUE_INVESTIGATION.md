# Segue-Based Song Pairing Investigation
**Date**: 2025-11-07  
**Status**: Analysis Complete - Track-Level Approach Needed

---

## Key Clarification

**User Requirement**: When songs traditionally segue into each other (adjacent tracks in shows), we should:
1. **Use the actual tracks from the same show** (not just song titles)
2. **Maintain the segue relationship** (preserve the specific performances)
3. **Avoid mixing disparate versions** (e.g., Mike's from Show A + Weekapaug from Show B)

This is different from the current song-title-based approach.

---

## Current vs. Needed Approach

### Current System (Song-Title Based)
```
Generation picks:
1. "Mike's Song" (any version from eligible pool)
2. "Weekapaug Groove" (any version from eligible pool)

Problem: These could be from different shows, breaking authentic segue
```

### Needed System (Track-Based)
```
Generation picks:
1. Mike's Song Track #40659 (2025-09-21)
2. → Must use Hydrogen Track #40660 (same show)
3. → Must use Weekapaug Track #40661 (same show)

Result: Preserves actual segue performance
```

---

## Real-World Segue Patterns (Database Analysis)

### Mike's Song → Next Track (Last 10 shows)
```
2025-09-21: Mike's [40659] → I Am Hydrogen [40660] → Weekapaug Groove [40661] 🎵
2025-09-14: Mike's [40553] → Ocelot [40554] → Kill Devil Falls [40555]
2025-07-26: Mike's [40465] → Wading in the Velvet Sea [40466] → Weekapaug [40467]
2025-07-20: Mike's [40411] → Horn [40412] → Reba [40413]
2025-07-12: Mike's [38514] → I Am Hydrogen [38515] → Weekapaug Groove [38516] 🎵
2025-06-27: Mike's [38375] → Cities [38376] → Divided Sky [38377]
2025-04-22: Mike's [38172] → I Am Hydrogen [38173] → Weekapaug Groove [38174] 🎵
2025-01-29: Mike's [40292] → I Am Hydrogen [40293] → Weekapaug Groove [40294] 🎵
2024-12-31: Mike's [38130] → Bouncing Around the Room [38131] → Weekapaug [38132]
2024-08-17: Mike's [37876] → I Am Hydrogen [37877] → Weekapaug Groove [37878] 🎵
```

**Key Findings**:
- Classic sandwich (Mike's → Hydrogen → Weekapaug): 6/15 recent shows (40%)
- Mike's leads to various songs (Ocelot, Wading, Cities, Horn, Bouncing)
- But Hydrogen → Weekapaug is 18/20 times (90%)

### I Am Hydrogen → Next Track (Last 20 shows)
```
Weekapaug Groove follows: 18/20 times (90%)
```

**Pattern**: Hydrogen almost always leads to Weekapaug (strong adjacency rule)

---

## Database Schema

### Track Table (Individual Performances)
```sql
tracks:
  - id (primary key)
  - show_id (foreign key to shows)
  - title (song name)
  - position (order within set)
  - set (set1, set2, encore, etc.)
  - duration (seconds)
  - slug (unique identifier)
  - likes_count
```

### Key Relationships
- Each track has a `show_id` and `position`
- Adjacent tracks: Same `show_id`, same `set`, `position + 1`
- Segues are identified by adjacent positions

---

## Proposed Solution: Track-Level Selection

### Concept
When generating a setlist:
1. Select a **track** (not just a song title)
2. Check if that track historically segues into another
3. If yes, include the **next track from the same show** as a unit
4. Treat segues as indivisible performance units

### Implementation Strategy

#### Option 1: Segue Groups (Pre-computed)
Build a feature table: `segue_groups.parquet`

```python
segue_groups = [
    {
        "group_id": "mikes_hydrogen_weekapaug_2025_09_21",
        "show_id": 2523,
        "show_date": "2025-09-21",
        "tracks": [
            {"track_id": 40659, "song": "Mike's Song", "position": 12, "duration": 615},
            {"track_id": 40660, "song": "I Am Hydrogen", "position": 13, "duration": 152},
            {"track_id": 40661, "song": "Weekapaug Groove", "position": 14, "duration": 487}
        ],
        "total_duration": 1254,
        "segue_type": "sandwich",
        "confidence": 0.99
    },
    # ... more groups
]
```

**Usage**:
```python
# Instead of selecting "Mike's Song", select segue group
group = select_segue_group(contains="Mike's Song")
# This gives you tracks [40659, 40660, 40661] as a unit
# Add all 3 tracks to setlist in sequence
```

**Pros**:
- Preserves authentic performances
- Simple to implement (pre-computed)
- Can weight by likes_count for best versions
- Duration is known (budget planning works)

**Cons**:
- Larger memory footprint (track-level vs song-level)
- More rigid (less mixing freedom)

#### Option 2: Dynamic Segue Detection
During generation, check if selected track has a mandatory segue:

```python
def select_next_song(previous_track_id):
    # Check if previous track has a mandatory next track
    segue_rule = feature_store.get_mandatory_segue(previous_track_id)
    
    if segue_rule:
        # Force selection of the next track from same show
        next_track = get_track_by_id(segue_rule.next_track_id)
        return next_track
    else:
        # Normal selection
        return weighted_pick(candidate_pool)
```

**Pros**:
- More flexible (only enforces known segues)
- Can still mix songs when no segue exists
- Smaller data footprint

**Cons**:
- Requires track-level data in generation
- More complex logic (track IDs vs song titles)

#### Option 3: Hybrid (Song + Track Selection)
Keep current song-title system, but enhance with track preference:

```python
def select_song(candidates):
    song = weighted_pick(candidates)  # Select song title as before
    
    # Check if this song typically segues
    if has_famous_segue(song):
        # Pick a track that includes the full segue sequence
        track = pick_track_with_segue(song)
        segue_tracks = get_segue_sequence(track)
        return segue_tracks  # Returns list of tracks
    else:
        # Pick any track for this song
        track = pick_track(song)
        return [track]
```

**Pros**:
- Minimal changes to existing system
- Preserves current song selection logic
- Only applies track-level for segues

**Cons**:
- More complex (two modes of operation)
- Still needs track-level data

---

## Data Requirements

### New Feature Table: `famous_segues.parquet`

Based on historical analysis, identify track sequences where:
- Song A → Song B occurs adjacently (position + 1)
- Frequency > 50 occurrences
- Confidence > 95%

**Columns**:
- `from_song`: "Mike's Song"
- `to_song`: "I Am Hydrogen" 
- `occurrences`: 334
- `confidence`: 98.6%
- `example_track_sequences`: List of (show_id, track_ids) tuples
- `avg_total_duration`: seconds

**Example Entry**:
```python
{
    "from_song": "I Am Hydrogen",
    "to_song": "Weekapaug Groove",
    "occurrences": 339,
    "confidence": 97.9%,
    "is_mandatory_adjacent": True,
    "example_sequences": [
        {"show_id": 2523, "tracks": [40660, 40661], "duration": 639},
        {"show_id": 2244, "tracks": [38515, 38516], "duration": 621},
        # ... more examples
    ]
}
```

### Track Selection Enhancement

Modify generator to work with track IDs:
- Instead of `selected_songs: List[str]` (song titles)
- Use `selected_tracks: List[int]` (track IDs)
- Each track carries: `track_id`, `song_title`, `show_id`, `duration`, `position`

---

## Impact on Current System

### Changes Needed

1. **Generator Core** (`core.py`):
   - Change from song-title selection to track selection
   - Add segue group handling
   - Track show_id to maintain segue integrity

2. **Feature Store** (`feature_store.py`):
   - Add `get_segue_groups()` method
   - Load `famous_segues.parquet`
   - Return track sequences instead of song titles

3. **Service Layer** (`service/tracks.py`):
   - Already works with track IDs (good!)
   - May need adjustments for segue groups

4. **API Response**:
   - Currently returns song titles
   - May need to include track metadata (show_date, etc.)

### Backward Compatibility

To avoid breaking existing API:
- Keep song-title output in API responses
- Internally use track IDs
- Add optional `include_track_metadata` flag for clients who want it

---

## Famous Segue Candidates (Top 20)

Based on CSV data, these should be segue groups:

1. **Mike's Song → Weekapaug Groove** (511×, 99.4%) - Direct or via Hydrogen
2. **I Am Hydrogen → Weekapaug Groove** (339×, 97.9%) - Mandatory adjacent
3. **Mike's Song → I Am Hydrogen** (334×, 98.6%) - Usually leads to Weekapaug
4. **The Oh Kee Pa Ceremony → Suzy Greenberg** (133×, 98.4%)
5. **Colonel Forbin's Ascent → Fly Famous Mockingbird** (124×, 94.9%)
6. **You Enjoy Myself → Possum** (67×, 100%)
7. **Bouncing Around the Room → You Enjoy Myself** (67×, 100%)
8. **Runaway Jim → Foam** (67×, 100%)
9. **Tweezer → Tweezer Reprise** (82×, 100%) - Set 2
10. **The Horse → Silent in the Morning** (91-94% confidence) - Already in directional_transitions

**Note**: Many of these already exist in `famous_song_sequences.csv` but need track-level implementation

---

## Recommended Approach

### Phase 1: Build Track-Level Segue Data
1. Query database for adjacent track sequences
2. Identify sequences matching famous_song_sequences.csv
3. Build `famous_segues.parquet` with track examples
4. Include show_id, track_ids, durations

### Phase 2: Modify Generator for Segue Groups
1. Add "segue mode" flag to generator
2. When selecting from famous segue songs, pick track with full sequence
3. Add all tracks in sequence as a unit
4. Update duration budget to account for multi-track sequences

### Phase 3: Test & Validate
1. Generate 100 setlists with segue enforcement
2. Verify Mike's → Hydrogen → Weekapaug appears as complete unit
3. Confirm tracks are from same show
4. Check duration budgets work correctly

### Phase 4: Scale
1. Apply to all 36 famous sequences
2. Add confidence thresholds (only enforce >95%)
3. Allow fallback to song-title mode if track unavailable

---

## Technical Considerations

### Duration Budget
Segue groups consume multiple slots but are selected as one unit:
```python
# Current: Each song selected independently
duration += get_song_duration("Mike's Song")  # ~8 min
duration += get_song_duration("Weekapaug")    # ~9 min

# Segue mode: Group selected as unit
segue_group = get_segue_group("Mike's → Hydrogen → Weekapaug")
duration += segue_group.total_duration  # 15-20 min total
```

### Rarity Consideration
User mentioned "recognize the rarity of these occurrences":
- Mike's → Hydrogen → Weekapaug is common (40% recent shows)
- Some segues rarer (Colonel Forbin's → Mockingbird less frequent)
- Weight selection by:
  1. Historical frequency (how often segue appears)
  2. Recency (favor recent versions)
  3. Likes count (community favorites)

### Mixing Freedom
Allow generator to:
- Use segue groups when available
- Fall back to individual songs if needed (duration constraints)
- Occasionally break segues for variety (configurable threshold)

---

## Next Steps

1. **Data Pipeline**: Build `famous_segues.parquet` from track sequences
2. **Proof of Concept**: Test with Mike's → Hydrogen → Weekapaug only
3. **Generator Update**: Add segue group selection mode
4. **Validation**: Measure segue accuracy in 100 generated setlists
5. **Scale**: Apply to all 36 famous sequences

---

## Summary

**Current Problem**: Generator selects song titles, can mix tracks from different shows  
**Root Cause**: Song-level selection doesn't preserve performance relationships  
**Solution**: Track-level segue groups that maintain show integrity  
**Benefit**: Authentic segues with actual performance characteristics preserved  
**Complexity**: Medium (requires track-level data pipeline + generator changes)
