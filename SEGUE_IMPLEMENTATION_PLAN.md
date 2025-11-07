# Segue Groups - Maximum Implementation Plan
**Date**: 2025-11-07  
**Goal**: ALL segues (mandatory + rare), track-level selection with "lottery ticket" effect

---

## Key Findings

### Database Analysis

**No explicit segue indicator** in database:
- `tracks` table: No `segue_to` or `transition_type` column
- `track_tags`: Has "Famous" tag (rare), "Jamcharts" (notable jams)
- **Segues inferred by**: Adjacent position (same show, same set, position + 1)

### Segue Frequency Distribution

**Top 50 transitions** (all occurrences):
1. **Hydrogen → Weekapaug**: 321 times (mandatory)
2. **Mike's → Hydrogen**: 313 times (mandatory)
3. **The Horse → Silent**: 149 times (mandatory)
4. **Oh Kee Pa → Suzy**: 135 times (mandatory)
5. **Forbin's → Mockingbird**: 94 times (mandatory)
...
50. **Golgi → Slave**: 19 times

**Long tail**: Thousands of 1-8 occurrence segues (rare/lottery tickets)

### Famous Example: Tweezer → Prince Caspian

**Total occurrences**: 8 times in entire history
- **08/22/2015**: Track 30447 → 30448 (⭐ FAMOUS, 339 likes)
  - Tweezer: 17.6 min, Jamcharts
  - Caspian: 16.9 min, Famous + Jamcharts + Tease
  - Combined: 34.5 minutes of epic jamming
- 7 other occurrences: 0-9 likes each

**Rarity score**: 8/2104 shows = 0.38% of all shows

---

## Implementation Strategy

### Two-Tier System

#### Tier 1: Mandatory Segues (Always enforce)
Famous sequences that MUST stay together (>50 occurrences, >95% consistency):
- Mike's → Hydrogen → Weekapaug
- Hydrogen → Weekapaug
- The Horse → Silent in the Morning
- Oh Kee Pa → Suzy Greenberg
- Colonel Forbin's → Fly Famous Mockingbird
- etc. (36 total from famous_song_sequences.csv)

**Implementation**: Same as planned - pre-computed `segue_groups.parquet`

#### Tier 2: Rare Segues (Lottery tickets)
ALL other adjacent transitions (1-50 occurrences):
- Tweezer → Prince Caspian (8 times)
- Tweezer → Piper (20 times)
- Split Open and Melt → Squirming Coil (21 times)
- etc. (~5,000-10,000 rare pairs)

**Implementation**: Separate table `rare_segues.parquet`

---

## Data Structure

### Table 1: `segue_groups.parquet` (Mandatory, ~1,000 records)

Famous sequences, always enforced.

```python
{
    "segue_id": "mikes_hydrogen_weekapaug_2025_09_21_set2",
    "segue_type": "sandwich",  # "pair", "triplet"
    "pattern": "Mike's Song -> I Am Hydrogen -> Weekapaug Groove",
    "frequency": "mandatory",   # Always enforce
    "show_id": 2523,
    "show_date": "2025-09-21",
    "set_label": "set2",
    "tracks": [40659, 40660, 40661],
    "songs": ["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"],
    "total_duration": 1254,
    "likes_count": 45,
    "historical_occurrences": 307,  # How many times this pattern happened
    "confidence": 0.99,
    "era": "4.0"
}
```

**Size**: ~200 KB (1,000 records)

### Table 2: `rare_segues.parquet` (Lottery Tickets, ~50,000 records)

ALL other adjacent transitions (1-50 occurrences).

```python
{
    "segue_id": "tweezer_caspian_2015_08_22_set2",
    "segue_type": "pair",
    "pattern": "Tweezer -> Prince Caspian",
    "frequency": "rare",  # Lottery ticket
    "show_id": 1836,
    "show_date": "2015-08-22",
    "set_label": "set2",
    "tracks": [30447, 30448],
    "songs": ["Tweezer", "Prince Caspian"],
    "total_duration": 2068,  # 34.5 minutes!
    "likes_count": 339,
    "historical_occurrences": 8,  # Tweezer->Caspian happened 8 times total
    "rarity_score": 0.0038,  # 8/2104 shows
    "tags": ["Jamcharts", "Famous", "Tease"],  # From track_tags
    "is_lottery_ticket": True,  # Flag for special treatment
    "lottery_weight": 339,  # Use likes_count as lottery weight
    "era": "3.0"
}
```

**Size**: ~10 MB (50,000 records, all adjacent pairs)

### Table 3: `segue_lookup.parquet` (Index, ~500 records)

Fast lookup: Given a song, which segues start with it?

```python
{
    "song_title": "Tweezer",
    "mandatory_segues": [
        "Tweezer -> Tweezer Reprise"  # 82 times
    ],
    "rare_segues": [
        "Tweezer -> Prince Caspian",   # 8 times
        "Tweezer -> Piper",            # 20 times
        "Tweezer -> You Enjoy Myself", # 63 times
        # ... more
    ],
    "total_segue_variants": 47,  # Tweezer has segued into 47 different songs
    "is_segue_starter": True,
    "must_complete": False  # Can appear standalone
}
```

**Size**: ~50 KB

---

## Generation Logic

### Selection Flow

```python
def select_next_song_or_segue(previous_song, current_track_id, ...):
    """
    Select next song, checking for segues.
    
    Priority:
    1. Mandatory segues (always enforce)
    2. Rare segues (lottery ticket, weighted by likes)
    3. Normal song selection
    """
    
    if not previous_song:
        # First song in set - normal selection
        return select_song_title()
    
    # TIER 1: Check for mandatory segues
    mandatory = feature_store.get_mandatory_segues(previous_song)
    if mandatory:
        # Filter by duration budget
        valid = [s for s in mandatory if fits_duration_budget(s)]
        if valid:
            # Select best version (likes + recency)
            return select_segue_group(valid)
    
    # TIER 2: Check for rare segues (lottery ticket)
    # Use the ACTUAL track that was just selected
    rare_segues = feature_store.get_rare_segues_from_track(current_track_id)
    
    if rare_segues:
        # Lottery decision: 10-20% chance to include rare segue
        lottery_chance = calculate_lottery_chance(rare_segues)
        
        if random.random() < lottery_chance:
            # Winner! Include the rare segue
            # Weight by likes_count (famous versions more likely)
            selected = weighted_choice(rare_segues, weight_by='likes_count')
            
            # INJECT: Add next track even if it breaks duration
            return inject_segue(selected)
    
    # TIER 3: Normal song selection
    return select_song_title()
```

### Lottery Ticket Logic

```python
def calculate_lottery_chance(rare_segues: List[dict]) -> float:
    """
    Calculate probability of using a rare segue.
    
    Factors:
    - Rarity score (rarer = higher chance when selected)
    - Likes count (famous versions = higher chance)
    - Era match (current era = higher chance)
    """
    
    # Base lottery rate: 15%
    base_rate = 0.15
    
    # Adjust by rarity (rarer = more special)
    avg_rarity = sum(s['rarity_score'] for s in rare_segues) / len(rare_segues)
    rarity_multiplier = 1.0 / (avg_rarity + 0.01)  # Inverse rarity
    
    # Adjust by likes (famous performances = higher chance)
    max_likes = max(s['likes_count'] for s in rare_segues)
    likes_multiplier = 1.0 + (max_likes / 100.0)  # +1% per 100 likes
    
    # Combine
    lottery_chance = base_rate * min(rarity_multiplier, 3.0) * min(likes_multiplier, 2.0)
    
    # Cap at 50% (always allow normal selection path)
    return min(lottery_chance, 0.5)


def inject_segue(segue_group: dict) -> dict:
    """
    Inject rare segue, potentially replacing another song.
    
    If duration budget exceeded:
    - Remove least-important song from set so far
    - Add segue tracks
    - Log "lottery ticket" note in metadata
    """
    
    if duration_budget_exceeded(segue_group['total_duration']):
        # Find candidate to remove (not mandatory segues, not set opener)
        removable_songs = get_removable_songs(current_set)
        
        if removable_songs:
            # Remove song with lowest score
            removed = remove_song(removable_songs[-1])
            metadata_notes.append(
                f"Lottery ticket! Rare segue {segue_group['pattern']} "
                f"from {segue_group['show_date']} (replaced {removed})"
            )
        else:
            # Can't make room, skip lottery ticket
            return None
    
    return segue_group
```

---

## SQL Build Script

### Generate Both Tables

**Script**: `scripts/build_segue_groups.py`

```python
from sqlalchemy import text
import pandas as pd
from phish_setlist_maker.db import session_scope

def build_all_segues():
    """
    Build both mandatory and rare segue tables.
    """
    
    # Query ALL adjacent track pairs
    with session_scope() as session:
        query = text("""
            SELECT 
                s.id as show_id,
                s.date as show_date,
                t1.id as track1_id,
                t1.title as song1,
                t1.duration as duration1,
                t1.likes_count as likes1,
                t1.set as set_label,
                t2.id as track2_id,
                t2.title as song2,
                t2.duration as duration2,
                t2.likes_count as likes2,
                STRING_AGG(DISTINCT tg.name, ',') as tags
            FROM tracks t1
            JOIN tracks t2 ON t2.show_id = t1.show_id 
                AND t2.set = t1.set 
                AND t2.position = t1.position + 1
            JOIN shows s ON s.id = t1.show_id
            LEFT JOIN track_tags tt ON tt.track_id = t2.id
            LEFT JOIN tags tg ON tg.id = tt.tag_id
            GROUP BY s.id, s.date, t1.id, t1.title, t1.duration, 
                     t1.likes_count, t1.set, t2.id, t2.title, 
                     t2.duration, t2.likes_count
            ORDER BY s.date DESC
        """)
        
        all_segues = session.execute(query).fetchall()
    
    # Calculate historical frequencies
    pair_counts = {}
    for segue in all_segues:
        pair = (segue.song1, segue.song2)
        pair_counts[pair] = pair_counts.get(pair, 0) + 1
    
    # Separate into mandatory vs rare
    mandatory_records = []
    rare_records = []
    
    for segue in all_segues:
        pair = (segue.song1, segue.song2)
        occurrences = pair_counts[pair]
        
        record = {
            'segue_id': f"{segue.song1}_{segue.song2}_{segue.show_date}_{segue.set_label}".lower().replace(' ', '_'),
            'segue_type': 'pair',
            'pattern': f"{segue.song1} -> {segue.song2}",
            'show_id': segue.show_id,
            'show_date': segue.show_date,
            'set_label': segue.set_label,
            'tracks': [segue.track1_id, segue.track2_id],
            'songs': [segue.song1, segue.song2],
            'total_duration': segue.duration1 + segue.duration2,
            'likes_count': segue.likes1 + segue.likes2,
            'historical_occurrences': occurrences,
            'tags': segue.tags.split(',') if segue.tags else [],
        }
        
        if occurrences >= 50:
            # Mandatory segue
            record['frequency'] = 'mandatory'
            record['confidence'] = 0.95  # High confidence
            mandatory_records.append(record)
        else:
            # Rare segue (lottery ticket)
            record['frequency'] = 'rare'
            record['rarity_score'] = occurrences / 2104  # Total shows
            record['is_lottery_ticket'] = True
            record['lottery_weight'] = record['likes_count']
            rare_records.append(record)
    
    # Save to parquet
    df_mandatory = pd.DataFrame(mandatory_records)
    df_mandatory.to_parquet('data/analytics/features/segue_groups.parquet')
    
    df_rare = pd.DataFrame(rare_records)
    df_rare.to_parquet('data/analytics/features/rare_segues.parquet')
    
    print(f"Built {len(mandatory_records)} mandatory segues")
    print(f"Built {len(rare_records)} rare segues")
    print(f"Total: {len(all_segues)} track pairs")
    
    # Build lookup index
    build_segue_lookup(mandatory_records, rare_records)


def build_segue_lookup(mandatory, rare):
    """Build song -> segues index."""
    lookup = {}
    
    for record in mandatory:
        song = record['songs'][0]
        if song not in lookup:
            lookup[song] = {'song_title': song, 'mandatory_segues': [], 'rare_segues': []}
        lookup[song]['mandatory_segues'].append(record['pattern'])
    
    for record in rare:
        song = record['songs'][0]
        if song not in lookup:
            lookup[song] = {'song_title': song, 'mandatory_segues': [], 'rare_segues': []}
        lookup[song]['rare_segues'].append(record['pattern'])
    
    df_lookup = pd.DataFrame(list(lookup.values()))
    df_lookup.to_parquet('data/analytics/features/segue_lookup.parquet')
    
    print(f"Built lookup index for {len(lookup)} songs")


if __name__ == "__main__":
    build_all_segues()
```

---

## Size Estimates (Maximum Implementation)

### Storage
- `segue_groups.parquet`: ~200 KB (1,000 mandatory)
- `rare_segues.parquet`: ~10 MB (50,000 rare)
- `segue_lookup.parquet`: ~50 KB (500 songs)
- **Total**: ~10.3 MB

### Memory (In-Memory Loading)
- Mandatory segues: ~2 MB
- Rare segues: ~20 MB (can lazy-load if needed)
- Lookup index: ~1 MB
- **Total**: ~23 MB (negligible)

### Performance
- Load time: ~200ms (one-time at startup)
- Lookup time: <1ms per song
- Lottery calculation: <5ms per rare segue check

---

## Feature Store Integration

```python
class FeatureStore:
    def _load_segue_groups(self):
        # Load mandatory
        self._segue_groups = pd.read_parquet('segue_groups.parquet').to_dict('records')
        
        # Load rare (optional: lazy-load on first access)
        self._rare_segues = pd.read_parquet('rare_segues.parquet').to_dict('records')
        
        # Load lookup
        self._segue_lookup = pd.read_parquet('segue_lookup.parquet').to_dict('records')
        
        # Build indexes
        self._segue_by_song = {}  # song -> segue_ids
        self._segue_by_track = {}  # track_id -> rare segues
        
        for group in self._segue_groups:
            # Index mandatory by song
            for song in group['songs']:
                if song not in self._segue_by_song:
                    self._segue_by_song[song] = []
                self._segue_by_song[song].append(group['segue_id'])
        
        for segue in self._rare_segues:
            # Index rare by track_id (for lottery tickets)
            track_id = segue['tracks'][0]
            if track_id not in self._segue_by_track:
                self._segue_by_track[track_id] = []
            self._segue_by_track[track_id].append(segue)
    
    def get_mandatory_segues(self, song_title: str) -> List[dict]:
        """Get mandatory segues for a song."""
        segue_ids = self._segue_by_song.get(song_title, [])
        return [s for s in self._segue_groups if s['segue_id'] in segue_ids]
    
    def get_rare_segues_from_track(self, track_id: int) -> List[dict]:
        """Get rare segues that could follow this specific track."""
        return self._segue_by_track.get(track_id, [])
```

---

## Generator Modifications

### Core Changes

1. **Track-aware selection**: Generator must track `current_track_id` not just song title
2. **Lottery decision point**: After each song selected, check for rare segues
3. **Injection logic**: If lottery wins, inject next track(s) even if duration tight
4. **Metadata logging**: Note when lottery tickets trigger

### Example Flow

```
1. Generate Set 2
2. Select opener: "Tweezer" → Pick track 30447 (2015-08-22)
3. Check rare segues for track 30447
   → Found: Caspian [30448] (8 total occurrences, 339 likes, rarity=0.0038)
4. Lottery check:
   → Base: 15%
   → Rarity multiplier: 1/0.0038 = 263× (capped at 3×) = 3×
   → Likes multiplier: 339/100 = 3.39× (capped at 2×) = 2×
   → Final: 15% × 3 × 2 = 90% (capped at 50%) = 50%
5. Roll: random() = 0.23 → Winner!
6. Inject Caspian [30448] after Tweezer
7. Add note: "Lottery ticket! Rare Tweezer -> Prince Caspian from 2015-08-22 (8 total occurrences)"
```

---

## API Response Design

### Schema Changes (`schemas.py`)

**Enhanced SongModel**:
```python
class SongModel(BaseModel):
    # Existing fields
    title: str
    mp3_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    origin: Optional[str] = None
    show_date: Optional[str] = None
    track_id: Optional[int] = None
    
    # NEW: Segue metadata
    is_segue: bool = False
    segue_type: Optional[Literal["mandatory", "rare", "lottery_ticket"]] = None
    segue_pattern: Optional[str] = None  # "Mike's Song -> Weekapaug Groove"
    segue_position: Optional[int] = None  # 1, 2, 3 (position in multi-song segue)
    segue_group_id: Optional[str] = None  # Groups segue songs together
    historical_occurrences: Optional[int] = None  # How many times this segue happened
    rarity_score: Optional[float] = None  # 0.0-1.0 (lower = rarer)
    likes_count: Optional[int] = None  # Track likes
```

### Example API Responses

#### Mandatory Segue (Mike's → Hydrogen → Weekapaug)

```json
{
  "sets": [
    {
      "label": "Set 2",
      "songs": ["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"],
      "tracks": [
        {
          "title": "Mike's Song",
          "track_id": 40659,
          "show_date": "2025-09-21",
          "duration_seconds": 615,
          "is_segue": true,
          "segue_type": "mandatory",
          "segue_pattern": "Mike's Song -> I Am Hydrogen -> Weekapaug Groove",
          "segue_position": 1,
          "segue_group_id": "mikes_hydrogen_weekapaug_2025_09_21_set2",
          "historical_occurrences": 307,
          "likes_count": 25
        },
        {
          "title": "I Am Hydrogen",
          "track_id": 40660,
          "show_date": "2025-09-21",
          "duration_seconds": 153,
          "is_segue": true,
          "segue_type": "mandatory",
          "segue_pattern": "Mike's Song -> I Am Hydrogen -> Weekapaug Groove",
          "segue_position": 2,
          "segue_group_id": "mikes_hydrogen_weekapaug_2025_09_21_set2",
          "historical_occurrences": 307,
          "likes_count": 12
        },
        {
          "title": "Weekapaug Groove",
          "track_id": 40661,
          "show_date": "2025-09-21",
          "duration_seconds": 486,
          "is_segue": true,
          "segue_type": "mandatory",
          "segue_pattern": "Mike's Song -> I Am Hydrogen -> Weekapaug Groove",
          "segue_position": 3,
          "segue_group_id": "mikes_hydrogen_weekapaug_2025_09_21_set2",
          "historical_occurrences": 307,
          "likes_count": 8
        }
      ]
    }
  ]
}
```

#### Lottery Ticket (Tweezer → Caspian)

```json
{
  "sets": [
    {
      "label": "Set 2",
      "songs": ["Tweezer", "Prince Caspian", "Piper"],
      "tracks": [
        {
          "title": "Tweezer",
          "track_id": 30447,
          "show_date": "2015-08-22",
          "duration_seconds": 1056,
          "is_segue": true,
          "segue_type": "lottery_ticket",
          "segue_pattern": "Tweezer -> Prince Caspian",
          "segue_position": 1,
          "segue_group_id": "tweezer_caspian_2015_08_22_set2",
          "historical_occurrences": 8,
          "rarity_score": 0.0038,
          "likes_count": 140
        },
        {
          "title": "Prince Caspian",
          "track_id": 30448,
          "show_date": "2015-08-22",
          "duration_seconds": 1012,
          "is_segue": true,
          "segue_type": "lottery_ticket",
          "segue_pattern": "Tweezer -> Prince Caspian",
          "segue_position": 2,
          "segue_group_id": "tweezer_caspian_2015_08_22_set2",
          "historical_occurrences": 8,
          "rarity_score": 0.0038,
          "likes_count": 199
        },
        {
          "title": "Piper",
          "track_id": 30449,
          "show_date": "2015-08-22",
          "duration_seconds": 542,
          "is_segue": false
        }
      ]
    }
  ],
  "metadata": {
    "notes": [
      "⭐ Lottery ticket! Rare Tweezer -> Prince Caspian from 08/22/2015 (8 occurrences in history)"
    ]
  }
}
```

#### Non-Segue Song (Normal)

```json
{
  "title": "David Bowie",
  "track_id": 35678,
  "show_date": "2023-07-15",
  "duration_seconds": 893,
  "is_segue": false,
  "likes_count": 45
}
```

### Frontend Display Guidance

#### Visual Indicators

**Mandatory Segues**:
- Show ` > ` arrow between songs
- Same background color for grouped songs
- Badge: "Classic Sequence"
- Tooltip: "Mike's Song → I Am Hydrogen → Weekapaug Groove (313 historical occurrences)"

**Lottery Tickets**:
- Show `⭐ > ` arrow with star
- Highlighted background (gold/special color)
- Badge: "Rare Segue!" or "Lottery Ticket"
- Tooltip: "Tweezer → Prince Caspian (only 8 times in history!)"
- Show date of performance

**Non-Segue**:
- No arrow
- Standard display
- Individual song card

#### Example UI Mock

```
Set 2:
┌────────────────────────────────────────────────┐
│ Mike's Song > I Am Hydrogen > Weekapaug Groove │ [Classic Sequence]
│ 09/21/2025 • 21 minutes total                  │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│ ⭐ Tweezer > Prince Caspian                    │ [RARE SEGUE!]
│ 08/22/2015 • 34 minutes • Only 8x in history   │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│ Piper                                          │
│ 08/22/2015 • 9 minutes                         │
└────────────────────────────────────────────────┘
```

### Frontend Implementation Notes

1. **Group Detection**: Use `segue_group_id` to identify which songs belong together
2. **Display Order**: Respect `segue_position` for multi-song segues
3. **Visual Hierarchy**:
   - Lottery tickets = most prominent (gold/special)
   - Mandatory = medium prominence (subtle grouping)
   - Normal = standard
4. **Tooltip Content**:
   - Pattern name
   - Historical occurrences
   - Rarity score (if lottery)
   - Show date (always same within segue)
5. **Player Integration**:
   - Auto-advance through segue (don't pause between tracks)
   - Show combined time for segue group
   - Individual track progress within segue

### Serializer Changes (`serializers.py`)

Add segue metadata population:

```python
def serialize_track_with_segue(
    track: Track,
    segue_metadata: Optional[dict] = None
) -> SongModel:
    """Serialize track with optional segue metadata."""
    
    base = SongModel(
        title=track.title,
        track_id=track.id,
        show_date=track.show.date.isoformat() if track.show else None,
        duration_seconds=track.duration,
        likes_count=track.likes_count,
    )
    
    if segue_metadata:
        base.is_segue = True
        base.segue_type = segue_metadata.get('segue_type')
        base.segue_pattern = segue_metadata.get('pattern')
        base.segue_position = segue_metadata.get('position')
        base.segue_group_id = segue_metadata.get('segue_id')
        base.historical_occurrences = segue_metadata.get('historical_occurrences')
        base.rarity_score = segue_metadata.get('rarity_score')
    
    return base
```

---

## Validation Plan

### Test Cases

1. **Mandatory enforcement**: Generate 100 setlists, verify Mike's → Hydrogen → Weekapaug always together
2. **Lottery rate**: Track how often rare segues appear (should be ~15-20% when candidates available)
3. **Famous versions**: Verify 2015-08-22 Tweezer → Caspian can appear (with tracking)
4. **Duration handling**: Confirm injection logic works when budget tight

---

## Summary

**Approach**: Two-tier system (mandatory + lottery)  
**Coverage**: ALL segues (1,000 mandatory + 50,000 rare)  
**Size**: ~10 MB parquet, ~23 MB in memory  
**Logic**: Mandatory always enforced, rare = weighted lottery (15-50% chance)  
**Famous segues**: Weighted by likes_count (339 likes = higher lottery chance)  
**Injection**: Can replace songs if needed to fit rare segue  
**User experience**: "Lottery ticket" notes when rare segues appear

**Result**: Maximum authenticity with exciting "rare performance" discoveries
