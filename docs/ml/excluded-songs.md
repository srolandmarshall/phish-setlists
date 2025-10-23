# Excluded Songs - Filtering Non-Musical Content

**Implemented**: 2025-10-23  
**Status**: ✅ Complete and tested

---

## Overview

The setlist generator now excludes situational, meta, and technical "songs" that should never appear in generated setlists. These are not actual musical performances but rather metadata, crowd interactions, or special-occasion-only items.

## The Problem

The historical data includes non-musical entries like:
- **Banter** - Crowd interaction/talking (138 appearances)
- **Audience Chess Move** - Situational audience participation (12 appearances)
- **Happy Birthday to You** - Special occasions only (23 appearances)
- **Narration** - Spoken word/storytelling, not songs (38 appearances)
- **Jam** - Generic jam placeholder (97 appearances)

These would occasionally appear in generated setlists, creating unrealistic results.

## The Solution

### Exclusion List

**File**: `data/analytics/excluded_songs.csv`

| Song Title | Reason | Category |
|------------|--------|----------|
| Banter | Non-musical crowd interaction | meta |
| Audience Chess Move | Situational audience participation | situational |
| Happy Birthday to You | Special occasion only | situational |
| Birthday | Special occasion only | situational |
| Soundcheck | Pre-show technical | technical |
| Tuning | Technical/between songs | technical |
| Intro | Not a song - metadata | meta |
| Outro | Not a song - metadata | meta |
| Jam | Generic jam placeholder (not Big Ball Jam) | meta |
| Narration | Spoken word/story - not musical | meta |
| Rhombus Narration | Gamehendge narration - not a song | meta |
| Thanksgiving | Holiday-specific | situational |

### Categories

1. **meta** - Metadata, not actual songs (Intro, Outro, Narration)
2. **situational** - Special occasions only (birthdays, holidays, chess moves)
3. **technical** - Pre-show or between-song technical elements (Soundcheck, Tuning)

### Note on "Jam"

- ❌ **"Jam"** (generic) - Excluded (placeholder in data)
- ✅ **"Big Ball Jam"** - Included (actual Phish composition)
- ✅ **"Mind Left Body Jam"** - Included (actual Phish composition)

## Implementation

### Generator Integration

The exclusion list is loaded automatically in `SetlistGenerator.__init__()`:

```python
def __init__(self, session, ...):
    # ...
    self._excluded_songs: Set[str] = self._load_excluded_songs()
```

### Loading Logic

1. **Primary source**: Load from `data/analytics/excluded_songs.csv`
2. **Fallback**: Hardcoded list in case CSV is missing
3. **Applied in**: `_build_candidate_pool()` method filters eligible songs

```python
def _build_candidate_pool(self, ...):
    eligible = set(eligible_songs)
    
    # Filter out excluded songs
    eligible = eligible - self._excluded_songs
    
    candidates = [...]
```

### Where It Applies

Exclusions are applied **universally**:
- ✅ All sets (Set 1, Set 2, Set 3)
- ✅ Encores
- ✅ Both legacy and ML-enabled generation modes

## Testing

### Verification Test

```python
from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator import SetlistGenerator

with session_scope() as session:
    generator = SetlistGenerator(session=session)
    
    # Check loaded exclusions
    print(f"Excluded: {len(generator._excluded_songs)} songs")
    
    # Generate and verify
    setlist = generator.generate()
    all_songs = []
    for seg in setlist.sets:
        all_songs.extend(seg.songs)
    
    # No excluded songs should appear
    assert not any(song in generator._excluded_songs for song in all_songs)
```

### Test Results

✅ **10 generated setlists** - Zero excluded songs appeared  
✅ **All 28 existing tests** - Pass with no regressions  
✅ **12 excluded songs** loaded correctly from CSV

## Adding New Exclusions

To exclude additional songs:

### Option 1: Edit CSV (Preferred)

Edit `data/analytics/excluded_songs.csv`:

```csv
song_title,reason,category
Your New Song,Why it should be excluded,category_name
```

Categories: `meta`, `situational`, `technical`

### Option 2: Hardcoded Fallback

Edit `src/phish_setlist_maker/generator/core.py`, method `_load_excluded_songs()`:

```python
excluded.update([
    "Banter",
    "Your New Song",  # Add here
    # ...
])
```

**Note**: CSV is preferred for easy maintenance without code changes.

## Examples of Excluded Content

### Meta (Non-Songs)
- **Banter**: Band talking to crowd
- **Narration**: Gamehendge storytelling
- **Intro/Outro**: Set markers, not songs
- **Jam**: Generic placeholder (not a specific composition)

### Situational (Special Occasions)
- **Happy Birthday to You**: Birthday shows only
- **Audience Chess Move**: Crowd participation game
- **Thanksgiving**: Holiday-specific

### Technical (Pre-show/Between-songs)
- **Soundcheck**: Pre-show technical check
- **Tuning**: Between-song instrument tuning

## Historical Data

From analysis of Phish setlist database:

| Song | Appearances | Why Excluded |
|------|-------------|--------------|
| Banter | 138 | Most common - not a song |
| Jam | 97 | Generic placeholder |
| Narration | 38 | Spoken word stories |
| Happy Birthday | 23 | Special occasions only |
| Crowd Control | 23 | Not excluded - actual song |
| Intro | 16 | Metadata marker |
| Audience Chess | 12 | Rare situational event |
| Rhombus Narration | 11 | Gamehendge story |

**Note**: "Crowd Control" is NOT excluded - it's an actual Phish song (Trey solo), distinct from crowd banter.

## Performance Impact

- **Memory**: ~1KB (12 song titles in set)
- **Loading**: <1ms (CSV read at init)
- **Filtering**: <1ms (set difference operation)
- **Total impact**: Negligible

## Related Features

- [Cross-Set Dependencies](./cross-set-dependencies.md) - Rules spanning multiple sets
- [Ordering Constraints](./ordering-rules-analysis.md) - Song sequencing rules
- [Phase 2.2 Implementation](./phase2-2-IMPLEMENTED.md) - ML constraint system

---

## Summary

✅ **Problem Solved**: Situational/meta content no longer appears in generated setlists  
✅ **Implementation**: Simple, maintainable CSV-based exclusion list  
✅ **Testing**: Verified across 10 generated setlists, all tests pass  
✅ **Performance**: Zero measurable impact  
✅ **Extensibility**: Easy to add new exclusions via CSV

The generator now produces more realistic setlists by filtering out non-musical content! 🎸
