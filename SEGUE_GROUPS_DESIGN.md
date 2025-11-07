Can# Segue Groups - Static Table Design
**Date**: 2025-11-07  
**Approach**: Pre-computed parquet tables with SQL offload

---

## Size Estimates

### Memory Impact (Minimal)

- **Total segue records**: ~3,000-4,000 (famous sequences only)
- **Parquet file size**: ~500 KB - 1 MB
- **In-memory footprint**: <2 MB loaded
- **Verdict**: ✅ Negligible impact on RAM

### Database Coverage

- Mike's → Hydrogen → Weekapaug: 307 complete sandwich performances
- Famous 2-song pairs: ~3,060 segues across 8 top sequences
- Potential to expand to all 36 famous sequences: ~10,000-15,000 records

---

## Table Design

### Table 1: `segue_groups.parquet`

Pre-computed segue units ready for selection.

**Schema**:

```python
{
    "segue_id": str,           # "mikes_hydrogen_weekapaug_2025_09_21_set2"
    "segue_type": str,         # "sandwich", "pair", "triplet"
    "pattern": str,            # "Mike's Song -> I Am Hydrogen -> Weekapaug Groove"
    "show_id": int,            # 2523
    "show_date": date,         # 2025-09-21
    "set_label": str,          # "set2"
    "tracks": List[int],       # [40659, 40660, 40661]
    "songs": List[str],        # ["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"]
    "total_duration": int,     # 1254 seconds
    "avg_duration": int,       # 418 seconds per song
    "likes_count": int,        # Sum of track likes
    "confidence": float,       # 0.99 (how often this sequence appears)
    "era": str,                # "4.0"
}
```

**Size**: ~200 bytes per record × 5,000 records = **~1 MB**

**Example Records**:

```python
[
    {
        "segue_id": "mikes_hydrogen_weekapaug_2025_09_21_set2",
        "segue_type": "sandwich",
        "pattern": "Mike's Song -> I Am Hydrogen -> Weekapaug Groove",
        "show_id": 2523,
        "show_date": "2025-09-21",
        "set_label": "set2",
        "tracks": [40659, 40660, 40661],
        "songs": ["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"],
        "total_duration": 1254,
        "avg_duration": 418,
        "likes_count": 45,
        "confidence": 0.99,
        "era": "4.0"
    },
    {
        "segue_id": "hydrogen_weekapaug_2024_08_03_set2",
        "segue_type": "pair",
        "pattern": "I Am Hydrogen -> Weekapaug Groove",
        "show_id": 2211,
        "show_date": "2024-08-03",
        "set_label": "set2",
        "tracks": [37659, 37660],
        "songs": ["I Am Hydrogen", "Weekapaug Groove"],
        "total_duration": 639,
        "avg_duration": 320,
        "likes_count": 32,
        "confidence": 0.97,
        "era": "4.0"
    }
]
```

### Table 2: `segue_lookup.parquet`

Fast lookup: Given a song, which segues is it part of?

**Schema**:

```python
{
    "song_title": str,         # "Mike's Song"
    "segue_patterns": List[str], # ["Mike's -> Hydrogen -> Weekapaug", "Mike's -> Weekapaug"]
    "total_occurrences": int,  # 511
    "is_segue_starter": bool,  # True (starts segues)
    "is_segue_middle": bool,   # False
    "must_complete": bool,     # False (can appear standalone)
}
```

**Size**: ~100 bytes × 100 songs = **~10 KB**

**Example Records**:

```python
[
    {
        "song_title": "Mike's Song",
        "segue_patterns": [
            "Mike's Song -> I Am Hydrogen -> Weekapaug Groove",
            "Mike's Song -> Weekapaug Groove"
        ],
        "total_occurrences": 511,
        "is_segue_starter": True,
        "is_segue_middle": False,
        "must_complete": False
    },
    {
        "song_title": "I Am Hydrogen",
        "segue_patterns": [
            "Mike's Song -> I Am Hydrogen -> Weekapaug Groove",
            "I Am Hydrogen -> Weekapaug Groove"
        ],
        "total_occurrences": 339,
        "is_segue_starter": False,
        "is_segue_middle": True,
        "must_complete": True  # Hydrogen ALWAYS needs Weekapaug
    }
]
```

---

## SQL Generation Script

Build tables from database (run periodically or on data updates).

**Script**: `scripts/build_segue_groups.py`

```python
from sqlalchemy import text
from phish_setlist_maker.db import session_scope
import pandas as pd

FAMOUS_SEQUENCES = [
    # (songs, min_confidence)
    (["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"], 0.95),
    (["Mike's Song", "Weekapaug Groove"], 0.90),
    (["I Am Hydrogen", "Weekapaug Groove"], 0.95),
    (["The Oh Kee Pa Ceremony", "Suzy Greenberg"], 0.95),
    (["Colonel Forbin's Ascent", "Fly Famous Mockingbird"], 0.90),
    # ... more sequences
]

def build_segue_groups():
    records = []

    with session_scope() as session:
        for songs, confidence in FAMOUS_SEQUENCES:
            if len(songs) == 2:
                query = text("""
                    SELECT
                        s.id as show_id,
                        s.date as show_date,
                        t1.set as set_label,
                        t1.id as track1_id,
                        t2.id as track2_id,
                        t1.duration + t2.duration as total_duration,
                        t1.likes_count + t2.likes_count as likes_count
                    FROM tracks t1
                    JOIN tracks t2 ON t2.show_id = t1.show_id
                        AND t2.set = t1.set
                        AND t2.position = t1.position + 1
                    JOIN shows s ON s.id = t1.show_id
                    WHERE t1.title = :song1 AND t2.title = :song2
                    ORDER BY s.date DESC
                """)

                results = session.execute(query, {
                    "song1": songs[0],
                    "song2": songs[1]
                }).fetchall()

                for row in results:
                    records.append({
                        "segue_id": f"{songs[0].lower().replace(' ', '_')}_{songs[1].lower().replace(' ', '_')}_{row.show_date}_{row.set_label}",
                        "segue_type": "pair",
                        "pattern": f"{songs[0]} -> {songs[1]}",
                        "show_id": row.show_id,
                        "show_date": row.show_date,
                        "set_label": row.set_label,
                        "tracks": [row.track1_id, row.track2_id],
                        "songs": songs,
                        "total_duration": row.total_duration,
                        "avg_duration": row.total_duration // 2,
                        "likes_count": row.likes_count,
                        "confidence": confidence,
                    })

            elif len(songs) == 3:
                # Similar query for 3-song sandwiches
                pass

    df = pd.DataFrame(records)
    df.to_parquet("data/analytics/features/segue_groups.parquet")
    print(f"Built {len(records)} segue groups")

if __name__ == "__main__":
    build_segue_groups()
```

---

## Generator Integration

### Option A: Eager Loading (Recommended)

Load all segue groups at generator startup, filter during selection.

**Feature Store** (`feature_store.py`):

```python
def _load_segue_groups(self) -> None:
    """Load pre-computed segue groups."""
    segue_path = self.features_dir / "segue_groups.parquet"

    if not segue_path.exists():
        self._segue_groups = []
        return

    df = pd.read_parquet(segue_path)

    # Convert to list of dicts for fast access
    self._segue_groups = df.to_dict('records')

    # Build index: song_title -> list of segue_ids
    self._segue_by_song = {}
    for group in self._segue_groups:
        for song in group['songs']:
            if song not in self._segue_by_song:
                self._segue_by_song[song] = []
            self._segue_by_song[song].append(group['segue_id'])

def get_segue_groups_for_song(self, song_title: str) -> List[dict]:
    """Get all segue groups containing this song."""
    if self._segue_by_song is None:
        return []

    segue_ids = self._segue_by_song.get(song_title, [])
    return [g for g in self._segue_groups if g['segue_id'] in segue_ids]
```

**Generator** (`core.py`):

```python
def _select_next_with_segue_check(
    self,
    previous_song: Optional[str],
    candidate_pool: List[SongFrequency],
    used_songs: Set[str],
    eligible_songs: Set[str],
    current_duration: float,
    max_duration: Optional[float]
) -> Optional[Union[str, List[int]]]:  # Returns song title OR list of track IDs
    """
    Select next song, checking for segue groups.

    Returns:
        - str: Song title (normal selection)
        - List[int]: Track IDs (segue group selected)
    """

    # Check if previous song starts a famous segue
    if previous_song and self._use_ml_features and self._feature_store:
        segue_groups = self._feature_store.get_segue_groups_for_song(previous_song)

        if segue_groups:
            # Filter groups that fit duration budget
            valid_groups = [
                g for g in segue_groups
                if (max_duration is None or
                    current_duration + g['total_duration'] <= max_duration)
            ]

            if valid_groups:
                # Weight by likes and recency
                weights = [g['likes_count'] * (1.0 if g['show_date'] > date(2020, 1, 1) else 0.5)
                          for g in valid_groups]

                # Random selection weighted by quality
                selected = random.choices(valid_groups, weights=weights, k=1)[0]

                # Return track IDs (segue group mode)
                return selected['tracks']

    # Normal song-title selection
    return self._weighted_pick(candidate_pool, used_songs, ...)
```

### Option B: SQL Query (If RAM constrained)

Query database on-demand during generation.

**Pros**: Zero memory footprint  
**Cons**: Adds query latency (~10-50ms per lookup)

**When to use**: If parquet tables exceed 10 MB or generation happens infrequently

---

## Performance Comparison

### Parquet (Eager Load)

- **Load time**: 50-100ms (one-time at startup)
- **Memory**: ~2 MB
- **Lookup time**: <1ms (in-memory dict)
- **Total overhead**: ~100ms startup + negligible per-generation

### SQL (On-Demand)

- **Load time**: 0ms
- **Memory**: 0 MB
- **Lookup time**: 10-50ms per query × 20 songs = 200-1000ms per setlist
- **Total overhead**: ~1 second per generation

**Verdict**: Parquet is 10× faster with negligible memory cost

---

## Fallback Strategy

If segue group not available:

1. Try to find individual tracks matching song titles
2. Fall back to post-generation rules (current system)
3. Log warning about missing segue

```python
if isinstance(selection, list):  # Track IDs returned
    # Segue group selected
    tracks = fetch_tracks_by_ids(selection)
    for track in tracks:
        add_track_to_setlist(track)
else:  # Song title returned
    # Normal selection, pick any track
    track = pick_random_track_for_song(selection)
    add_track_to_setlist(track)
```

---

## Deployment Plan

### Phase 1: Build Script

- Create `scripts/build_segue_groups.py`
- Query famous sequences from database
- Generate `segue_groups.parquet` (~1 MB)

### Phase 2: Feature Store

- Add `_load_segue_groups()` method
- Add `get_segue_groups_for_song()` lookup
- Test memory impact (<5 MB)

### Phase 3: Generator

- Modify `_weighted_pick()` to return track IDs or song title
- Add segue group selection logic
- Handle both modes in track assembly

### Phase 4: Validation

- Generate 100 setlists
- Measure: How often Mike's → Hydrogen → Weekapaug appears as unit
- Verify tracks are from same show

---

## Summary

**Approach**: Static parquet table with eager loading  
**Size**: ~1 MB file, ~2 MB in memory  
**Performance**: <100ms startup, <1ms per lookup  
**SQL Usage**: Only during table generation (offline)  
**Scalability**: Can support 100+ segue patterns with <10 MB total  
**Verdict**: ✅ Minimal resource impact, maximum speed
