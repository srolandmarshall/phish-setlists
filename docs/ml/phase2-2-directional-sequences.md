# Phase 2.2: Directional Sequence Rules & Constraints

**Problem Identified**: 2025-10-22  
**Issue**: ML features identify song pairs but don't capture:
- Directionality (Mike's → Weekapaug, not Weekapaug → Mike's)
- Mandatory adjacency (they must follow each other)
- Mutual exclusivity without the pair (Weekapaug shouldn't appear alone)

**Example Bug**: Generated Set 2 with Weekapaug, then later Mike's Song (wrong order, not adjacent)

---

## Root Cause Analysis

### Current System:

1. **Transition Lift** (Phase 1):
   ```python
   # Bidirectional - boosts BOTH directions equally
   Mike's → Weekapaug: lift = 47×
   Weekapaug → Mike's: lift = 47×  # WRONG!
   ```

2. **Dependency Rules** (existing):
   ```python
   # Only ensures presence, not order
   SongDependencyRule(
       trigger="Mike's Song",
       requirements=("Weekapaug Groove",),
       insert_adjacent=True  # Good!
   )
   ```

3. **ML Transition Bonus** (Phase 2.1):
   ```python
   # Applies bonus to BOTH directions
   if transition.lift > 2.0:
       boost = 1.0 + ml_transition_bonus * normalized_lift
   ```

### The Gap:

- ✅ ML knows they're paired (high lift)
- ✅ Rules ensure Weekapaug appears if Mike's does
- ❌ ML doesn't know the ORDER matters
- ❌ Rules don't prevent Weekapaug appearing first
- ❌ No "forbidden transitions" (Weekapaug → Mike's is invalid)

---

## Solution: Multi-Layered Approach

### Layer 1: Enhanced Feature Engineering (Phase 2.2a)

**Add directionality to transition analysis**:

```python
# Instead of just lift scores, track:
{
    "from_song": "Mike's Song",
    "to_song": "Weekapaug Groove",
    "lift": 47.0,
    "directionality": "mandatory_forward",  # NEW
    "adjacency_required": True,             # NEW
    "reverse_forbidden": True,              # NEW
}
```

**Detection heuristics**:
- If A→B appears 90%+ of the time A appears, mark as `mandatory_forward`
- If B→A appears <5% of the time, mark as `reverse_forbidden`
- If average distance between A and B is <2 songs, mark `adjacency_required`

**Output**: `data/analytics/features/directional_transitions.parquet`

### Layer 2: ML-Driven Rule Discovery (Phase 2.2b)

**Auto-generate rules from data**:

```python
# scripts/discover_sequence_rules.py
def discover_sequence_rules(min_support=20, min_confidence=0.85):
    """Find mandatory song sequences from historical data."""
    
    # Example discoveries:
    rules = [
        SequenceRule(
            trigger="Mike's Song",
            must_follow=["Weekapaug Groove"],
            confidence=0.95,
            support=558,
            max_gap=0,  # immediate adjacency
        ),
        SequenceRule(
            trigger="Also Sprach Zarathustra",
            must_follow=["2001"],
            confidence=0.89,
            support=142,
            max_gap=0,
        ),
        # ... more discovered rules
    ]
```

**Output**: `src/phish_setlist_maker/generator/ml_rules.py`

### Layer 3: Enhanced Generator Logic (Phase 2.2c)

**Forbidden transitions check**:

```python
def _weighted_pick(self, pool, used_songs, previous_song=None, target_set=None):
    # ... existing code ...
    
    # NEW: Filter out forbidden transitions
    if previous_song and self._use_ml_features and self._feature_store:
        forbidden = self._feature_store.get_forbidden_next_songs(previous_song)
        pool = [freq for freq in pool if freq.title not in forbidden]
    
    # NEW: Boost mandatory sequences even more
    if previous_song and self._feature_store:
        mandatory = self._feature_store.get_mandatory_next_songs(previous_song)
        for idx, (freq, weight) in enumerate(weighted_candidates):
            if freq.title in mandatory:
                # Much stronger boost than normal transitions
                weighted_candidates[idx] = (freq, weight * 3.0)
```

**Validation after generation**:

```python
def _validate_sequence_rules(self, songs: List[str]):
    """Ensure no forbidden transitions occurred."""
    violations = []
    for i, song in enumerate(songs[:-1]):
        next_song = songs[i + 1]
        if self._feature_store.is_forbidden_transition(song, next_song):
            violations.append(f"{song} → {next_song}")
    
    if violations:
        # Log warning or re-generate
        logger.warning(f"Sequence violations: {violations}")
```

---

## Implementation Plan

### Phase 2.2a: Directional Feature Engineering (2-3 hours)

1. **Update `src/phish_setlist_maker/analysis/features.py`**:
   ```python
   def compute_directional_transitions(
       tracks_df: pd.DataFrame,
       min_support: int = 10,
       mandatory_threshold: float = 0.85,
       forbidden_threshold: float = 0.05,
   ) -> pd.DataFrame:
       """Compute directed transition rules with constraints."""
   ```

2. **Detect patterns**:
   - Count A→B vs B→A occurrences
   - Calculate conditional probabilities
   - Compute average gaps between pairs
   - Flag mandatory/forbidden patterns

3. **Output new parquet**:
   - `directional_transitions.parquet` with constraints
   - Includes confidence, support, max_gap fields

### Phase 2.2b: Rule Discovery Script (1-2 hours)

1. **Create `scripts/discover_sequence_rules.py`**:
   - Load directional transitions
   - Generate SequenceRule objects
   - Write to `ml_rules.py` or JSON

2. **Manual review step**:
   - Human verification of discovered rules
   - Edit thresholds if needed
   - Commit approved rules

### Phase 2.2c: Generator Integration (2-3 hours)

1. **Update FeatureStore**:
   ```python
   def get_forbidden_next_songs(self, from_song: str) -> Set[str]
   def get_mandatory_next_songs(self, from_song: str) -> Set[str]
   def is_forbidden_transition(self, from_song: str, to_song: str) -> bool
   ```

2. **Update `_weighted_pick`**:
   - Filter forbidden transitions
   - Boost mandatory sequences
   - Validate after selection

3. **Add validation pass**:
   - Check for violations post-generation
   - Log warnings or trigger re-generation

### Phase 2.2d: Testing (1 hour)

1. **Unit tests**:
   - Test forbidden transition filtering
   - Test mandatory sequence boosting
   - Test validation logic

2. **Integration tests**:
   - Generate 100 setlists, check for Mike's/Weekapaug violations
   - Verify other known sequences (2001→Zarathustra, etc.)

---

## Expected Outcomes

### Discovered Rules (estimates):

| Trigger | Must Follow | Confidence | Support | Notes |
|---------|-------------|------------|---------|-------|
| Mike's Song | Weekapaug Groove | 95% | 558 | Classic sandwich |
| Swept Away | Steep | 98% | 89 | Nearly always paired |
| McGrupp | Watchful Hosemasters | 92% | 56 | Story continuation |
| The Man Who | Avenu Malkenu | 87% | 42 | Gamehendge sequence |
| I Am Hydrogen | Weekapaug Groove | 85% | 124 | Mike's Groove variation |

**Note**: "Also Sprach Zarathustra" and "2001" are aliases (same song), not a sequence.

### Forbidden Reverse Transitions:

- Weekapaug → Mike's (unless part of "Mike's Groove")
- Steep → Swept Away
- Watchful Hosemasters → McGrupp
- etc.

### Critical: Alias Normalization

Before computing transitions, resolve aliases to canonical titles:
```python
def normalize_song_title(song_df: pd.DataFrame) -> pd.DataFrame:
    """Merge aliases to canonical names before sequence analysis.
    
    Example: 'Also Sprach Zarathustra' (title) has alias '2001'
             Both should map to the same canonical song.
    """
    # Load Song table with alias mappings
    # Resolve all references to canonical form
    # This prevents false "Also Sprach → 2001" sequences
```

---

## Success Metrics

- ✅ Zero Mike's/Weekapaug order violations in 1000 generated setlists
- ✅ Discovered rules match known Phish lore (manual verification)
- ✅ No false positives (incorrectly forbidden valid transitions)
- ✅ Performance impact <10ms per generation

---

## Timeline

- **Phase 2.2a**: 2-3 hours (directional features)
- **Phase 2.2b**: 1-2 hours (rule discovery)
- **Phase 2.2c**: 2-3 hours (generator integration)
- **Phase 2.2d**: 1 hour (testing)

**Total**: 6-9 hours

---

## Future Enhancements

1. **N-song sequences**: A→B→C patterns (e.g., "Mike's → Hydrogen → Weekapaug")
2. **Set-specific rules**: Some sequences more common in Set 2
3. **Era-specific rules**: Patterns change over time
4. **Confidence intervals**: Probabilistic enforcement vs hard constraints
5. **User-contributed rules**: Allow manual additions to discovered rules

---

## Notes

This addresses the core issue: **ML features need to respect sequence ORDER and ADJACENCY**, not just co-occurrence. The current lift scores are too naive - they treat all pairs as symmetric when many are directional and mandatory.

The solution integrates ML-discovered rules with the existing rule engine, creating a hybrid system that's both data-driven and structurally sound.
