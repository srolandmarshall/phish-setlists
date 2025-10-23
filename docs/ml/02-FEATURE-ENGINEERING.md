# Feature Engineering: Analysis and Insights

**Last Updated**: 2025-10-23  
**Status**: Phase 1 Complete ✅

---

## Table of Contents
1. [Overview](#overview)
2. [Song Placement Features](#song-placement-features)
3. [Transition Analysis](#transition-analysis)
4. [Temporal Patterns](#temporal-patterns)
5. [Venue Tendencies](#venue-tendencies)
6. [Feature Catalog](#feature-catalog)

---

## Overview

### What Is Feature Engineering?

Feature engineering transforms raw setlist data into meaningful patterns that drive intelligent generation. We extract features that capture:

- **Song versatility**: Where songs typically appear (set placement)
- **Sequential patterns**: Which songs follow each other
- **Temporal trends**: How popularity evolves over time
- **Venue preferences**: Location-specific tendencies

### Feature Generation Pipeline

```
Raw Data (Parquet)
    ↓
[Analysis Functions]
    ↓
Feature DataFrames
    ↓
[Validation & QA]
    ↓
Feature Store (Parquet)
```

### Generated Features

**Location**: `data/analytics/features/`

| File | Records | Description |
|------|---------|-------------|
| song_features.parquet | 389 | Comprehensive song profiles |
| song_transitions.parquet | 181 | High-confidence transitions with lift |
| ordering_constraints.parquet | 686 | Mandatory song orderings |
| directional_transitions.parquet | 33 | Adjacent sequence rules |
| cross_set_dependencies.parquet | 1 | Cross-set requirements |
| excluded_songs.csv | 12 | Non-musical content filter |

---

## Song Placement Features

### Set Placement Probability

**What**: Likelihood of a song appearing in each set type

**Metric**: `P(song in setX) = appearances_in_setX / total_appearances`

**Example**:
```python
{
    "song": "Tweezer Reprise",
    "set1": 0.184,      # 18.4% in Set 1
    "set2": 0.189,      # 18.9% in Set 2
    "set3": 0.000,      # Never in Set 3
    "encore": 0.626     # 62.6% in encore (primary home)
}
```

### Set Entropy (Versatility)

**What**: Shannon entropy measuring placement uncertainty

**Formula**: `H = -Σ p_i * log2(p_i)` across all sets

**Interpretation**:
- **High entropy** (>1.5 bits): Versatile, appears across multiple sets
- **Low entropy** (<0.5 bits): Set-specific, predictable placement

**Top 10 Most Versatile Songs**:

| Rank | Song | Entropy | Pattern |
|------|------|---------|---------|
| 1 | Icculus | 1.894 | Appears equally in all sets |
| 2 | Sanity | 1.848 | Multi-set flexibility |
| 3 | La Grange | 1.846 | Versatile cover |
| 4 | Whipping Post | 1.807 | Any set, any position |
| 5 | Banter | 1.774 | Meta (excluded in v2.2b) |
| 6 | Contact | 1.771 | Set 1/2/encore |
| 7 | Suzy Greenberg | 1.768 | Opener or closer |
| 8 | Bold as Love | 1.764 | Cover, flexible |
| 9 | Tube | 1.759 | Modern versatile jam |
| 10 | Halley's Comet | 1.747 | Multi-set regular |

**Bottom 10 Most Specialized Songs**:

| Rank | Song | Entropy | Primary Set |
|------|------|---------|-------------|
| 1 | Sleeping Monkey | 0.000 | Encore only (76.0%) |
| 2 | Tweezer Reprise | 0.000 | Encore (62.6%) |
| 3 | Alumni Blues | 0.078 | Set 1 specialist |
| 4 | Foam | 0.104 | Set 1 (86.5%) |
| 5 | Divided Sky | 0.122 | Set 1 (82.7%) |

### Multi-Home Classification

**What**: Songs that appear in 2+ sets with ≥15% probability

**Purpose**: Identify flexible songs for duration balancing

**Result**: **246 songs** (63% of active repertoire)

**Examples**:

| Song | Set 1 | Set 2 | Set 3 | Encore | Multi-Home |
|------|-------|-------|-------|--------|------------|
| Harry Hood | 48.0% | 74.3% | 3.4% | 6.7% | ✓ (Set 1+2) |
| Character Zero | 34.5% | 36.6% | 0.7% | 28.0% | ✓ (all sets) |
| Possum | 50.4% | 39.2% | 6.2% | 3.8% | ✓ (Set 1+2) |
| Tweezer Reprise | 18.4% | 18.9% | 0.0% | 62.6% | ✓ (S2+enc) |
| Foam | 86.5% | 12.5% | 0.6% | 0.3% | ✗ (Set 1 only) |

### Set-Specific Specialists

**Set 1 Specialists** (>80% probability):
- Foam (86.5%)
- Divided Sky (82.7%)
- Stash (81.8%)
- Reba (69.1% - strong but not >80%)

**Set 2 Specialists**:
- Hold Your Head Up (85.0%)
- Also Sprach Zarathustra (82.9%)
- Tweezer (78.0%)

**Encore Lock-ins**:
- Sleeping Monkey (76.0%)
- Tweezer Reprise (62.6%)
- Rocky Top (57.5%)
- Fire (52.9%)

### Generator Integration

**Use Cases**:

1. **Placement Filtering**:
   - Reject songs with <5% historical probability in target set
   - Example: Don't place Tweezer Reprise in Set 1

2. **Probability Weighting**:
   - Blend historical weight (70%) with ML probability (30%)
   - Nudge selection toward authentic placement

3. **Flexibility Scoring**:
   - Use high-entropy songs as gap fillers
   - Reserve low-entropy songs for canonical sets

---

## Transition Analysis

### Transition Lift

**What**: How much more likely a transition is than random chance

**Formula**: `Lift = P(A→B) / [P(A) × P(B)]`

**Interpretation**:
- Lift = 1.0: No association (random)
- Lift > 2.0: Meaningful pairing
- Lift > 50: Strong association
- Lift > 200: "Composed" sequence (nearly always together)

### Top 25 Transitions by Lift

| Rank | Song A | Song B | Lift | Support | Pattern Type |
|------|--------|--------|------|---------|--------------|
| 1 | Swept Away | Steep | 473.6× | 89 | Composed pair |
| 2 | Colonel Forbin's | Mockingbird | 393.4× | 124 | Story sequence |
| 3 | TMWSIY | Avenu Malkenu | 223.1× | 66 | Gamehendge |
| 4 | The Horse | Silent Morning | 213.8× | 147 | Composed pair |
| 5 | Letter to Jimmy | Alumni Blues | 211.1× | 79 | Cover sequence |
| 6 | Alumni Blues | Letter to Jimmy | 200.4× | 79 | Reverse also valid |
| 7 | Peaches en Regalia | Prince Caspian | 166.0× | 12 | Instrumental flow |
| 8 | Makisupa | Hydrogen | 154.3× | 25 | Rare pairing |
| 9 | McGrupp | Hosemasters | 146.2× | 68 | Story continuation |
| 10 | Esther | Wilson | 132.9× | 17 | Old sequence |
| 11 | Kung | Hydrogen | 117.3× | 10 | Classic transition |
| 12 | Avenu Malkenu | TMWSIY | 116.5× | 54 | Story reverse |
| 13 | Hydrogen | Weekapaug | 113.8× | 339 | **Mike's Groove** |
| 14 | Camel Walk | Hydrogen | 113.7× | 14 | Rare connection |
| 15 | Fluffhead | Hydrogen | 109.5× | 15 | Transition |
| 16 | Buried Alive | Poor Heart | 104.2× | 41 | Common opener |
| 17 | Oh Kee Pa | Suzy Greenberg | 97.6× | 133 | Classic pairing |
| 18 | Destiny Unbound | Hydrogen | 96.0× | 13 | Rare |
| 19 | Mike's Song | Hydrogen | 79.0× | 334 | **Mike's Groove** |
| 20 | Landlady | Bouncing | 74.9× | 48 | Flow pair |
| 21 | Ginseng | Hydrogen | 72.6× | 10 | Rare |
| 22 | Chalk Dust | Hydrogen | 66.6× | 10 | Rare sandwich |
| 23 | Dinner and Movie | Bouncing | 63.9× | 37 | Common flow |
| 24 | Dinner and Movie | Hydrogen | 59.5× | 11 | Rare |
| 25 | Also Sprach | 2001 | 56.8× | 11 | Same song alias! |

### Transition Categories

#### 1. Composed Sequences (Lift >200)

Songs written as intentional pairs:
- **Swept Away → Steep** (473.6×)
- **Colonel Forbin's → Mockingbird** (393.4×)
- **The Horse → Silent in the Morning** (213.8×)
- **TMWSIY → Avenu Malkenu** (223.1×)

**Generator Rule**: Treat as mandatory adjacent pairs

#### 2. Strong Associations (Lift 50-200)

Frequently paired but not mandatory:
- **Mike's Song → Hydrogen** (79.0×, 334 times)
- **Hydrogen → Weekapaug** (113.8×, 339 times)
- **Oh Kee Pa → Suzy Greenberg** (97.6×, 133 times)

**Generator Rule**: Apply transition bonus (10-30% weight boost)

#### 3. Moderate Associations (Lift 10-50)

Common but not defining:
- **Stash → Cavern** (various shows)
- **Reba → Antelope** (flow pairs)
- **Sparkle → Stash** (typical sequence)

**Generator Rule**: Slight nudge in selection

#### 4. Weak/Random (Lift <10)

No meaningful association, treat as independent.

### Mike's Groove Analysis

The quintessential Phish sandwich:

**Standard Pattern**:
```
Mike's Song → I Am Hydrogen → Weekapaug Groove
```

**Statistics**:
- **Mike's → Hydrogen**: 334 times, 98.5% ordering, 79.0× lift
- **Hydrogen → Weekapaug**: 339 times, 96.5% ordering, 113.8× lift
- **Mike's → Weekapaug**: 511 times, 99.4% ordering (when not separated)

**Variations**:
- Mike's → Weekapaug (no Hydrogen): 177 times
- Mike's → Simple → Weekapaug: 51 times
- Mike's → Hold Your Head Up → Weekapaug: 106 times (Set 2 teases)

**Generator Implementation**:
- Ordering constraint: Mike's before Weekapaug (99.4%)
- Transition bonus: Both directions boosted
- Not strictly adjacent: Allows 1-5 song gap

### Directional vs. Bidirectional

**Directional Transitions** (one-way):
- Mike's → Weekapaug (99.4% forward, 0.6% reverse)
- Hydrogen → Weekapaug (97.9% forward, 2.1% reverse)
- Swept Away → Steep (98%+ forward, <2% reverse)

**Bidirectional Transitions** (both directions valid):
- TMWSIY ↔ Avenu Malkenu (both high lift)
- Alumni Blues ↔ Letter to Jimmy Page (both directions)

**Generator Rule**: Forbid reverse transitions for highly directional pairs

---

## Temporal Patterns

### Song Popularity Over Time

**Method**: Track play counts per year, identify trends

**Key Findings**:

#### 1. Era-Specific Rotation

**1.0 Era (1983-2000)**:
- Heavy rotation: You Enjoy Myself, Possum, David Bowie
- Gamehendge songs peak: Colonel Forbin's, Mockingbird
- Classic jams: Tweezer, Mike's Song

**2.0 Era (2000-2004)**:
- New staples: Piper, Heavy Things, Guyute
- Continued classics: Harry Hood, Antelope
- Reduced Gamehendge

**Hiatus (2004-2009)**: No performances

**3.0 Era (2009-present)**:
- Modern classics: Ghost, Chalk Dust, 555
- Continued staples: Tweezer, Mike's, Harry Hood
- Occasional Gamehendge

#### 2. Common Openers by Set

**Set 1 Openers** (Top 10):
1. AC/DC Bag (145 times)
2. Wilson (137 times)
3. The Curtain (118 times)
4. Sample in a Jar (107 times)
5. Chalk Dust Torture (99 times)
6. Runaway Jim (96 times)
7. Buried Alive (86 times)
8. Golgi Apparatus (85 times)
9. The Oh Kee Pa Ceremony (82 times)
10. Possum (76 times)

**Set 2 Openers**:
1. Also Sprach Zarathustra (200 times) - **Dominant opener**
2. Mike's Song (124 times)
3. Down with Disease (95 times)
4. Tweezer (85 times)
5. Chalk Dust Torture (72 times)

**Encore Openers**:
- More variable, less pattern
- Often the most popular song of the encore

#### 3. Set Duration Patterns

**Average Set Durations** (in minutes):

| Set Type | Mean | Median | Std Dev |
|----------|------|--------|---------|
| Set 1 | 68.3 | 67.5 | 12.8 |
| Set 2 | 74.1 | 73.2 | 15.4 |
| Set 3 | 42.7 | 41.0 | 18.9 |
| Encore | 15.8 | 14.3 | 8.2 |

**Trends Over Time**:
- Set 2 duration increased in 3.0 era (longer jams)
- Encore duration relatively stable
- Festival shows: significantly longer (2-3× typical)

---

## Venue Tendencies

### Venue Statistics

**Most Played Venues** (Top 10):

| Venue | City | Shows | Avg Duration | Top Songs |
|-------|------|-------|--------------|-----------|
| Madison Square Garden | New York, NY | 87 | 178.5 min | Tweezer, Harry Hood, Weekapaug |
| Dick's Sporting Goods Park | Commerce City, CO | 42 | 188.8 min | Chalk Dust, Ghost, Harry Hood |
| The Front | Burlington, VT | 33 | 104.5 min | AC/DC Bag, YEM, Golgi |
| Deer Creek | Noblesville, IN | 32 | 168.3 min | Down with Disease, Antelope |
| SPAC | Saratoga Springs, NY | 27 | 167.9 min | Tweezer Reprise, Chalk Dust |
| Alpine Valley | East Troy, WI | 26 | 172.8 min | Character Zero, Ghost |
| Hampton Coliseum | Hampton, VA | 24 | 173.7 min | Mike's, Weekapaug, Harry Hood |
| Nectar's | Burlington, VT | 24 | 114.3 min | Alumni Blues, Golgi, Fluffhead |
| Gorge Amphitheatre | George, WA | 22 | 173.9 min | Wolfman's, Moma Dance, Tweezer |
| Great Woods | Mansfield, MA | 22 | 158.4 min | Possum, Back on Train, Harry Hood |

### Venue-Specific Patterns

**Large Arenas** (MSG, Dick's, Hampton):
- Longer shows (170-190 min)
- Big jam vehicles (Tweezer, Ghost, Harry Hood)
- High-energy closers

**Small Clubs** (Nectar's, The Front):
- Shorter shows (100-120 min)
- Higher song density
- More early-era repertoire

**Outdoor Venues** (Gorge, SPAC, Alpine):
- Extended jams
- Nature-themed songs occasionally
- Festival-style pacing

**Regional Preferences**:
- **Northeast**: Classic rotation, high YEM frequency
- **Colorado**: Extended jam-heavy shows
- **Midwest**: Balanced mix, big closers

### Tour Context

**Notable Tours**:

| Tour | Shows | Date Range | Notes |
|------|-------|------------|-------|
| 1990 Tour | 145 | Jan-Dec 1990 | High rotation year |
| Winter/Spring 1993 | 70 | Feb-May 1993 | Peak 1.0 era |
| Summer 1997 | 39 | Jun-Aug 1997 | Cow Funk era |
| Summer 2015 | 19 | Jul-Aug 2015 | First full tour of 3.0 |

**Tour Momentum**:
- Songs rotate every 3-5 shows
- Some "tour debuts" appear mid-tour
- Openers vary more than closers within tours

---

## Feature Catalog

### Complete Feature Set

**File**: `data/analytics/features/song_features.parquet`

**Schema** (389 songs):
```
song_effective_title   : string   # Normalized song name
set1                   : float    # P(song in Set 1)
set2                   : float    # P(song in Set 2)
set3                   : float    # P(song in Set 3)
encore                 : float    # P(song in Encore)
set_entropy            : float    # Placement versatility (0-2 bits)
total_appearances      : int      # Total times played
multi_home             : bool     # Appears in 2+ sets (≥15% each)
debut_year             : int      # First performance year
last_played            : date     # Most recent performance
```

**Usage**:
```python
import pandas as pd
features = pd.read_parquet("data/analytics/features/song_features.parquet")

# Get placement probability
prob = features.loc[features['song_effective_title'] == 'Tweezer', 'set2'].iloc[0]
print(f"Tweezer Set 2 probability: {prob:.1%}")  # 78.0%

# Find versatile songs
versatile = features[features['set_entropy'] > 1.5].sort_values('set_entropy', ascending=False)
print(versatile[['song_effective_title', 'set_entropy']].head())
```

### Feature Generation

**Script**: `scripts/build_features.py`

**Process**:
1. Load raw tracks from analytics exports
2. Compute placement frequencies per set
3. Calculate entropy scores
4. Identify multi-home songs
5. Compute transition lifts
6. Export to parquet

**Runtime**: ~10-15 seconds for full feature rebuild

**Command**:
```bash
poetry run python scripts/build_features.py
```

---

## Visualizations

### Generated Figures

**Location**: `docs/figures/`

1. **set_placement_heatmap.png**
   - Top 30 songs by set placement
   - Color intensity = probability
   - Reveals set-specific vs. versatile songs

2. **entropy_distribution.png**
   - Histogram of entropy scores
   - Top 10 / bottom 10 songs annotated
   - Shows bi-modal distribution (specialists vs. generalists)

3. **transition_network.png**
   - Top 20 transitions by lift
   - Arrow thickness = lift strength
   - Node size = song popularity

4. **temporal_trends.png**
   - Line plot of top 10 songs over time
   - Shows era-specific rotation
   - Reveals peaks and declines

### Generating Visualizations

```bash
poetry run python scripts/visualize_analysis.py
```

Output: 4 PNG files in `docs/figures/`

---

## Next Steps

Proceed to:
- **[Generator Integration](./03-GENERATOR-INTEGRATION.md)** - How features drive generation
- **[Constraints System](./04-CONSTRAINTS-SYSTEM.md)** - Ordering and dependency rules

---

*Features are automatically used when ML mode is enabled (default). For legacy behavior, set `use_ml_features=False`.*
