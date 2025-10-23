# Phish Song Ordering Rules - Complete Analysis

**Generated**: 2025-10-23  
**Data Source**: `ordering_constraints.parquet`  
**Total Rules**: 686

---

## Executive Summary

This document analyzes the **686 ordering constraint rules** discovered from Phish's historical setlist data. These rules describe songs that consistently appear in a specific order when played in the same set.

### Key Findings:

- **662 unique song pairs** have mandatory ordering
- **36 'famous sequences'** (>50 occurrences, >95% ordering consistency)
- **Top pairing**: Mike's Song → Weekapaug Groove (511 times, 99.4% ordering)
- **Most sets involved**: Some pairs span set1, set2, and encore

---

## Famous Song Sequences

These are the most iconic and frequently-played song sequences in Phish history (>50 occurrences, >95% directional consistency).

| Rank | Song A | Song B | Times Played | Ordering % | Sets |
|------|--------|--------|--------------|------------|------|
| 1 | Mike's Song | Weekapaug Groove | 511 | 99.4% | set1, set2 |
| 2 | I Am Hydrogen | Weekapaug Groove | 339 | 97.9% | set1, set2 |
| 3 | Mike's Song | I Am Hydrogen | 334 | 98.6% | set1, set2 |
| 4 | The Oh Kee Pa Ceremony | Suzy Greenberg | 133 | 98.4% | set1, set2 |
| 5 | Mike's Song | Hold Your Head Up | 106 | 99.1% | set2 |
| 6 | You Enjoy Myself | Hold Your Head Up | 101 | 100.0% | set2 |
| 7 | Tweezer | Hold Your Head Up | 100 | 100.0% | set2 |
| 8 | Weekapaug Groove | Hold Your Head Up | 98 | 100.0% | set2 |
| 9 | Hold Your Head Up | Hold Your Head Up | 96 | 100.0% | set2 |
| 10 | Narration | Narration | 87 | 100.0% | set1, set2 |
| 11 | Big Ball Jam | Hold Your Head Up | 84 | 98.8% | set2 |
| 12 | Tweezer | Tweezer Reprise | 82 | 100.0% | set2 |
| 13 | I Am Hydrogen | Hold Your Head Up | 74 | 100.0% | set2 |
| 14 | Runaway Jim | Foam | 67 | 100.0% | set1 |
| 15 | Bouncing Around the Room | You Enjoy Myself | 67 | 100.0% | set1, set2 |
| 16 | You Enjoy Myself | Possum | 67 | 100.0% | set1, set2 |
| 17 | Uncle Pen | Hold Your Head Up | 65 | 100.0% | set2 |
| 18 | Foam | Bouncing Around the Room | 63 | 100.0% | set1 |
| 19 | Tweezer | You Enjoy Myself | 63 | 100.0% | set2 |
| 20 | Foam | Stash | 63 | 100.0% | set1 |
| 21 | Foam | Cavern | 63 | 100.0% | set1 |
| 22 | Runaway Jim | Stash | 59 | 100.0% | set1 |
| 23 | Runaway Jim | You Enjoy Myself | 58 | 100.0% | set1, set2 |
| 24 | Bouncing Around the Room | Run Like an Antelope | 56 | 100.0% | set1 |
| 25 | Rift | Stash | 56 | 100.0% | set1 |

### Interpretation:

- **Times Played**: Number of shows where both songs appeared in the same set
- **Ordering %**: How often Song A appeared before Song B (>95% = virtually always)
- **Sets**: Which set types this pairing occurs in (set1, set2, set3, encore)

---

## Top 50 Ordering Rules (by Frequency)

These are the most commonly co-occurring song pairs, broken down by set type.

| Rank | Song A | Song B | Set | Cooccurrences | A→B Count | Ordering % | Mandatory |
|------|--------|--------|-----|---------------|-----------|------------|-----------|
| 1 | Mike's Song | Weekapaug Groove | set2 | 351 | 349 | 99.4% | ✓ |
| 2 | I Am Hydrogen | Weekapaug Groove | set2 | 209 | 205 | 98.1% | ✓ |
| 3 | Mike's Song | I Am Hydrogen | set2 | 205 | 201 | 98.0% | ✓ |
| 4 | Mike's Song | Weekapaug Groove | set1 | 160 | 159 | 99.4% | ✓ |
| 5 | I Am Hydrogen | Weekapaug Groove | set1 | 130 | 127 | 97.7% | ✓ |
| 6 | Mike's Song | I Am Hydrogen | set1 | 129 | 128 | 99.2% | ✓ |
| 7 | Mike's Song | Hold Your Head Up | set2 | 106 | 105 | 99.1% | ✓ |
| 8 | You Enjoy Myself | Hold Your Head Up | set2 | 101 | 101 | 100.0% | ✓ |
| 9 | Tweezer | Hold Your Head Up | set2 | 100 | 100 | 100.0% | ✓ |
| 10 | Weekapaug Groove | Hold Your Head Up | set2 | 98 | 98 | 100.0% | ✓ |
| 11 | Colonel Forbin's Ascent | Fly Famous Mockingbird | set1 | 96 | 93 | 96.9% | ✓ |
| 12 | Hold Your Head Up | Hold Your Head Up | set2 | 96 | 96 | 100.0% | ✓ |
| 13 | Big Ball Jam | Hold Your Head Up | set2 | 84 | 83 | 98.8% | ✓ |
| 14 | Tweezer | Tweezer Reprise | set2 | 82 | 82 | 100.0% | ✓ |
| 15 | The Oh Kee Pa Ceremony | Suzy Greenberg | set1 | 78 | 77 | 98.7% | ✓ |
| 16 | The Horse | Silent in the Morning | set2 | 75 | 71 | 94.7% | ✓ |
| 17 | I Am Hydrogen | Hold Your Head Up | set2 | 74 | 74 | 100.0% | ✓ |
| 18 | The Horse | Silent in the Morning | set1 | 72 | 65 | 90.3% | ✓ |
| 19 | Runaway Jim | Foam | set1 | 67 | 67 | 100.0% | ✓ |
| 20 | Uncle Pen | Hold Your Head Up | set2 | 65 | 65 | 100.0% | ✓ |
| 21 | Foam | Stash | set1 | 63 | 63 | 100.0% | ✓ |
| 22 | Foam | Bouncing Around the Room | set1 | 63 | 63 | 100.0% | ✓ |
| 23 | Foam | Cavern | set1 | 63 | 63 | 100.0% | ✓ |
| 24 | Tweezer | You Enjoy Myself | set2 | 63 | 63 | 100.0% | ✓ |
| 25 | Runaway Jim | Stash | set1 | 59 | 59 | 100.0% | ✓ |
| 26 | Narration | Narration | set1 | 59 | 59 | 100.0% | ✓ |
| 27 | Bouncing Around the Room | Run Like an Antelope | set1 | 56 | 56 | 100.0% | ✓ |
| 28 | Poor Heart | Stash | set1 | 56 | 56 | 100.0% | ✓ |
| 29 | Rift | Stash | set1 | 56 | 56 | 100.0% | ✓ |
| 30 | The Oh Kee Pa Ceremony | Suzy Greenberg | set2 | 55 | 54 | 98.2% | ✓ |
| 31 | Sparkle | Stash | set1 | 55 | 55 | 100.0% | ✓ |
| 32 | Tweezer | Harry Hood | set2 | 53 | 53 | 100.0% | ✓ |
| 33 | Divided Sky | Cavern | set1 | 53 | 53 | 100.0% | ✓ |
| 34 | Foam | Sparkle | set1 | 51 | 51 | 100.0% | ✓ |
| 35 | Bouncing Around the Room | David Bowie | set1 | 51 | 50 | 98.0% | ✓ |
| 36 | Suzy Greenberg | Hold Your Head Up | set2 | 51 | 51 | 100.0% | ✓ |
| 37 | Mike's Song | Simple | set2 | 51 | 51 | 100.0% | ✓ |
| 38 | Bouncing Around the Room | Stash | set1 | 50 | 50 | 100.0% | ✓ |
| 39 | Foam | Run Like an Antelope | set1 | 50 | 50 | 100.0% | ✓ |
| 40 | Divided Sky | Run Like an Antelope | set1 | 49 | 49 | 100.0% | ✓ |
| 41 | Foam | Divided Sky | set1 | 49 | 49 | 100.0% | ✓ |
| 42 | Chalk Dust Torture | Stash | set1 | 49 | 49 | 100.0% | ✓ |
| 43 | Hold Your Head Up | Love You | set2 | 49 | 17 | 34.7% |  |
| 44 | The Landlady | Bouncing Around the Room | set1 | 48 | 48 | 100.0% | ✓ |
| 45 | Simple | Weekapaug Groove | set2 | 48 | 48 | 100.0% | ✓ |
| 46 | Foam | David Bowie | set1 | 48 | 48 | 100.0% | ✓ |
| 47 | Llama | Hold Your Head Up | set2 | 48 | 48 | 100.0% | ✓ |
| 48 | Reba | Run Like an Antelope | set1 | 47 | 47 | 100.0% | ✓ |
| 49 | Stash | Cavern | set1 | 46 | 46 | 100.0% | ✓ |
| 50 | Runaway Jim | Bouncing Around the Room | set1 | 46 | 46 | 100.0% | ✓ |

---

## Notable Patterns & Categories

### 1. Classic Sandwich Patterns

Multi-song sequences that form a complete 'sandwich' or suite:

- **Mike's Song → I Am Hydrogen → Weekapaug Groove**
  - Mike's → Hydrogen: 334 times (98.5% ordering)
  - Hydrogen → Weekapaug: 339 times (96.5% ordering)
  - Mike's → Weekapaug: 511 times (99.4% ordering) *(when not separated)*

- **The Horse → Silent in the Morning**
  - 147 cooccurrences (93.2% ordering)
  - Appears in set1 and set2

### 2. Story Songs & Narrations

Songs with narrative continuity that must appear in order:

- **Colonel Forbin's Ascent → Fly Famous Mockingbird**
  - 124 cooccurrences (94.9% ordering)
  - The classic Gamehendge narrative sequence
  - Appears in set1 and set2

- **You Enjoy Myself → Possum** / **Possum → You Enjoy Myself**
  - Both directions appear frequently (67 times YEM→Possum, 52 times Possum→YEM)
  - 100% ordering in both directions (context-dependent)
  - Suggests they often bookend segments

### 3. Jam Vehicle Chains

Long improvisational songs that flow into each other:

- **Tweezer → You Enjoy Myself**: 63 times (100% ordering)
- **Tweezer → Harry Hood**: 53 times (100% ordering)
- **Mike's Song → Weekapaug Groove**: 511 times (99.4% ordering) - the ultimate chain

### 4. Encore Patterns

*(Most encore songs are standalone, with fewer strict ordering patterns)*

---

## Technical Notes

### How These Rules Were Discovered

1. **Data Source**: Historical Phish setlist data from all shows
2. **Analysis Method**: 
   - For each set, identify all song pairs that appeared together
   - Track how often Song A appeared before Song B
   - Calculate ordering ratio (A before B / total cooccurrences)
3. **Mandatory Threshold**: Ordering ratio ≥ 90% = mandatory rule

### How These Rules Are Used

The setlist generator uses these rules to:

1. **Filter invalid candidates**: Skip songs that would violate ordering
   - Example: Don't add Mike's Song after Weekapaug is already in the set

2. **Boost sequential songs**: Apply 3× weight to mandatory next songs
   - Example: After Mike's Song, Weekapaug becomes much more likely

3. **Preserve Phish's performance patterns**: Maintain the authentic flow

---

## Complete Dataset

The full analysis data is available in CSV format:

- **`docs/figures/top_50_ordering_rules.csv`**: Top 50 rules by set type
- **`docs/figures/top_50_song_pairs.csv`**: Top 50 pairs across all sets
- **`docs/figures/famous_song_sequences.csv`**: High-confidence sequences
- **`data/analytics/features/ordering_constraints.parquet`**: Complete 686 rules

---

## Related Documentation

- [Phase 2.2 Implementation](./phase2-2-IMPLEMENTED.md) - Technical implementation details
- [Cross-Set Dependencies](./cross-set-dependencies.md) - Rules spanning multiple sets
- [AGENTS-ML Roadmap](../../AGENTS-ml.md) - Overall ML feature roadmap

---

*Generated by the Phish Setlist Maker ML analysis pipeline*