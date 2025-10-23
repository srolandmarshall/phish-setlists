# Ordering Rules Documentation Index

**Last Updated**: 2025-10-23

This directory contains comprehensive analysis of the **686 song ordering constraint rules** discovered from Phish's historical setlist data.

---

## 📚 Documentation Files

### Main Analysis Document
**[ordering-rules-analysis.md](../ml/ordering-rules-analysis.md)** - Complete analysis with:
- Famous song sequences (top 25)
- Top 50 ordering rules by frequency
- Pattern categories (sandwiches, story songs, jam chains)
- Technical notes on discovery and usage

### Quick Reference
**[ordering-rules-quick-reference.md](./ordering-rules-quick-reference.md)** - Fast lookup with:
- Top 25 sequences in chart format
- Quick stats summary
- The Big 5 most iconic sequences
- Category breakdown

---

## 📊 Data Files (CSV)

All data files are in CSV format for easy viewing in spreadsheets or analysis tools.

### 1. Famous Song Sequences
**File**: `famous_song_sequences.csv`  
**Rows**: 36 sequences  
**Criteria**: >50 cooccurrences AND >95% ordering consistency

**Columns**:
- `song_a`, `song_b` - The song pair
- `total_cooccurrences` - Times they appeared together in same set
- `num_sets` - How many set types (set1, set2, etc.)
- `sets` - Which sets they appear in
- `mandatory_in_sets` - Sets where ordering is mandatory (>90%)
- `avg_ordering_ratio` - Average ordering consistency (0.0-1.0)
- `always_ordered` - TRUE if >95% consistency

**Example Row**:
```
Mike's Song, Weekapaug Groove, 511, 2, "set1, set2", "set1, set2", 0.994, TRUE
```

### 2. Top 50 Ordering Rules
**File**: `top_50_ordering_rules.csv`  
**Rows**: 50 rules  
**Criteria**: Most frequently cooccurring pairs, by individual set type

**Columns**:
- `song_a`, `song_b` - The song pair
- `set_label` - Which set (set1, set2, set3, encore)
- `cooccurrence_count` - Times together in this specific set type
- `a_before_b_count` - Times song_a came before song_b
- `a_before_b_ratio` - Ordering consistency (0.0-1.0)
- `is_ordering_mandatory` - TRUE if ratio ≥ 0.90

**Example Row**:
```
Mike's Song, Weekapaug Groove, set2, 351, 349, 0.994, TRUE
```

### 3. Top 50 Song Pairs
**File**: `top_50_song_pairs.csv`  
**Rows**: 50 pairs  
**Criteria**: Most frequently cooccurring pairs across ALL set types combined

**Columns**:
- `song_a`, `song_b` - The song pair
- `total_cooccurrences` - Total across all sets
- `num_sets` - Number of different set types
- `sets` - List of set types
- `mandatory_in_sets` - Sets with mandatory ordering
- `avg_ordering_ratio` - Average consistency
- `always_ordered` - TRUE if >95% consistent

**Example Row**:
```
Mike's Song, Weekapaug Groove, 511, 2, "set1, set2", "set1, set2", 0.994, TRUE
```

---

## 🎯 Key Findings

### The Big 5 Most Iconic Sequences

1. **Mike's Song → Weekapaug Groove** (511 times, 99.4%)
2. **I Am Hydrogen → Weekapaug Groove** (339 times, 97.9%)
3. **Mike's Song → I Am Hydrogen** (334 times, 98.6%)
4. **The Oh Kee Pa Ceremony → Suzy Greenberg** (133 times, 98.4%)
5. **Colonel Forbin's Ascent → Fly Famous Mockingbird** (124 times, 94.9%)

### Pattern Categories

- **Sandwich Suites**: Mike's → Hydrogen → Weekapaug, The Horse → Silent
- **Story Songs**: Forbin's → Mockingbird (Gamehendge narratives)
- **Jam Chains**: Tweezer → YEM, Tweezer → Harry Hood
- **Classic Pairs**: Oh Kee Pa → Suzy, Runaway Jim → Foam → Stash

---

## 🔧 How to Use This Data

### For Analysis
1. Open CSV files in Excel, Google Sheets, or pandas
2. Filter by `always_ordered=TRUE` for strict rules
3. Sort by `total_cooccurrences` for most common
4. Group by `sets` to see set-specific patterns

### For Generator Development
The setlist generator uses these rules to:
1. **Filter** invalid song placements (violate ordering)
2. **Boost** mandatory follow-up songs (3× weight)
3. **Preserve** authentic Phish performance flow

### For Music Analysis
Study patterns to understand:
- Song compatibility and flow
- Era-specific sequencing preferences
- Structural elements of Phish shows

---

## 📈 Source Data

All analysis derived from:
- **Raw Data**: `data/analytics/features/ordering_constraints.parquet`
- **Total Rules**: 686 ordering constraints
- **Threshold**: 90% ordering consistency = mandatory
- **Time Span**: Entire Phish performance history in database

---

## 🔗 Related Documentation

- [Cross-Set Dependencies](../ml/cross-set-dependencies.md) - Rules spanning multiple sets
- [Phase 2.2 Implementation](../ml/phase2-2-IMPLEMENTED.md) - Technical details
- [AGENTS-ML Roadmap](../../AGENTS-ml.md) - Overall ML feature roadmap

---

## 📝 Quick Commands

```bash
# View CSV files
cat docs/figures/famous_song_sequences.csv
cat docs/figures/top_50_ordering_rules.csv
cat docs/figures/top_50_song_pairs.csv

# Analyze in Python
import pandas as pd
df = pd.read_csv('docs/figures/famous_song_sequences.csv')
df[df['always_ordered'] == True].sort_values('total_cooccurrences', ascending=False)

# View complete raw data
import pandas as pd
df = pd.read_parquet('data/analytics/features/ordering_constraints.parquet')
df.head(50)
```

---

*This analysis reveals the hidden structure and patterns in Phish's setlist construction, providing data-driven insights into decades of musical evolution.* 🎸
