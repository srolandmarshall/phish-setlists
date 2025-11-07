# Ordering Rules — Implementation Verification & Fix

**Status**: ⚠️ CRITICAL — Needs verification and likely fixes  
**Priority**: NEXT after consolidation  
**Last Updated**: November 7, 2025

---

## Executive Summary

The system has **686 song ordering constraints** discovered from historical data, with CSV files documenting 36+ famous sequences and 100 top rules. However, **it's unclear if all 686 rules are properly enforced** during setlist generation.

**This is the next critical work item.**

---

## What We Have

### CSV Data (docs/figures/)

3 well-organized CSV files with constraint data:

**1. famous_song_sequences.csv** (36 sequences)
- Criteria: >50 cooccurrences AND >95% ordering consistency
- Example: Mike's Song → Weekapaug Groove (511 times, 99.4%)
- Columns: song_a, song_b, total_cooccurrences, sets, mandatory_in_sets, always_ordered

**2. top_50_ordering_rules.csv** (50 rules)
- By individual set type (set1, set2, set3, encore)
- Includes: cooccurrence_count, ordering_ratio, is_ordering_mandatory
- Set-specific constraints (e.g., Set 1 rules vs Set 2 rules)

**3. top_50_song_pairs.csv** (50 pairs)
- Across ALL set types combined
- Shows which rules apply in multiple sets
- Aggregated view of most common pairs

### Visualizations (PNG files)

4 analysis charts:
- `entropy_distribution.png` - Song placement variety
- `set_placement_heatmap.png` - Where songs appear by set
- `temporal_trends.png` - Evolution over time
- `transition_network.png` - Song connection graph

### Source Data (Parquet)

- **Location**: `data/analytics/features/ordering_constraints.parquet`
- **Records**: 686 total ordering rules
- **Threshold**: 90% ordering consistency = mandatory

---

## The Problem

### Current State: Unknown ❓

**Question**: Are all 686 rules actually being enforced?

**Evidence of issue**:
1. CSV files exist but may not be used by generator
2. Only 686 rules in parquet, unclear if all loaded
3. Generator code may only use subset of rules
4. No validation showing 100% rule compliance

### Symptoms

- Generated setlists might violate ordering rules
- "Impossible" sequences might appear
- Performance impact of constraint checking unknown
- No test coverage of rule enforcement

---

## The Fix: 5-Step Verification

### Step 1: Audit Generator Code

**File**: `src/phish_setlist_maker/generator/core.py`

**Questions to answer**:
- Does it load `ordering_constraints.parquet`?
- How many rules are loaded? (Should be ~686)
- Where does it check constraints? (In `_select_with_duration_budget()`?)
- What's the penalty for violating a rule? (Skip song? Exception?)

**Command**:
```bash
grep -n "ordering_constraints\|order\|sequence" src/phish_setlist_maker/generator/core.py
```

### Step 2: Test Rule Compliance

**Generate 100+ setlists and validate**:

```python
from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator.core import SetlistGenerator
import pandas as pd

# Load famous sequences
sequences = pd.read_csv('docs/figures/famous_song_sequences.csv')
mandatory_pairs = sequences[sequences['always_ordered'] == True]

violations = []

with session_scope() as session:
    gen = SetlistGenerator(session, use_ml_features=True)
    for i in range(100):
        result = gen.generate(num_sets=2, include_encore=True)
        
        # Check each set for violations
        for set_songs in result.sets:
            for idx, song in enumerate(set_songs.songs[:-1]):
                next_song = set_songs.songs[idx + 1]
                
                # Check if this pair violates any rules
                violating_rule = mandatory_pairs[
                    (mandatory_pairs['song_a'] == song) &
                    (mandatory_pairs['song_b'] == next_song)
                ]
                
                if len(violating_rule) > 0:
                    # This pair is mandatory in opposite order
                    violations.append({
                        'set': i,
                        'pair': f"{song} → {next_song}",
                        'should_be': f"{violating_rule.iloc[0]['song_b']} → {violating_rule.iloc[0]['song_a']}"
                    })

print(f"Total violations found: {len(violations)}")
if violations:
    for v in violations[:10]:
        print(f"  {v}")
```

### Step 3: Identify Gaps

**If violations found**:
- Which rules are violated most?
- Are they famous sequences or rare rules?
- Do violations correlate with specific songs?

**CSV analysis**:
```bash
# Load and analyze violations
python << 'EOF'
import pandas as pd

# Load what should be enforced
sequences = pd.read_csv('docs/figures/famous_song_sequences.csv')
rules = pd.read_csv('docs/figures/top_50_ordering_rules.csv')

print(f"Famous sequences to enforce: {len(sequences[sequences['always_ordered']])}")
print(f"Top rules to enforce: {len(rules[rules['is_ordering_mandatory']])}")

# List the top 10
print("\nTop 10 sequences by frequency:")
print(sequences.nlargest(10, 'total_cooccurrences')[['song_a', 'song_b', 'total_cooccurrences']])
EOF
```

### Step 4: Fix Implementation

If rules not enforced, fix in generator:

**Location**: `src/phish_setlist_maker/generator/core.py` → `_select_with_duration_budget()` or `_build_candidate_pool()`

**Pseudocode**:
```python
# Load all 686 ordering rules
ordering_rules = self._feature_store.get_ordering_constraints()

# Before adding song to set:
for song in candidates:
    # Check if this song has ordering requirements
    for rule in ordering_rules:
        if rule.dependent == song:
            # This song requires another song first
            if rule.required not in current_set_songs:
                # Skip this song, requirement not met
                candidates.remove(song)
                break
```

### Step 5: Validation & Metrics

**Run comprehensive test**:

```bash
# Generate 500 setlists and validate
poetry run python scripts/analyze_generation_frequency.py -n 500 --check-ordering-rules

# Should output:
# - Total setlists: 500
# - Total songs generated: ~10,000
# - Ordering rule violations: 0 (or specific count)
# - Famous sequence compliance: 100%
# - Coverage by rule type: sandwich, story, jam, classic
```

**Expected results**:
- ✅ 100% compliance with famous sequences (The Big 5)
- ✅ 99%+ compliance with all mandatory rules
- ✅ 0 violations in test run
- ✅ Performance impact <5ms per generation

---

## Implementation Checklist

### Audit Phase
- [ ] Read generator code, identify constraint loading
- [ ] Count actual rules loaded (should be ~686)
- [ ] Identify where checking happens
- [ ] Review penalty for violations

### Testing Phase
- [ ] Generate 100 setlists
- [ ] Load CSV files and famous sequences
- [ ] Check for violations
- [ ] Document findings

### Fix Phase (if needed)
- [ ] Implement missing constraint checks
- [ ] Add performance monitoring
- [ ] Write unit tests for each rule type
- [ ] Validate 100% compliance

### Documentation Phase
- [ ] Update docs/ml/03-CONSTRAINTS-HEURISTICS.md
- [ ] Add validation results to metrics section
- [ ] Document any performance impact
- [ ] Update roadmap status

---

## CSV File Reference

### Load and Analyze

```python
import pandas as pd

# Load data
sequences = pd.read_csv('docs/figures/famous_song_sequences.csv')
rules = pd.read_csv('docs/figures/top_50_ordering_rules.csv')
pairs = pd.read_csv('docs/figures/top_50_song_pairs.csv')

# Analyze
print(f"Total famous sequences: {len(sequences)}")
print(f"Mandatory sequences: {len(sequences[sequences['always_ordered']])}")

# The Big 5
print("\nTop 5 by frequency:")
print(sequences.nlargest(5, 'total_cooccurrences'))

# By set type
print("\nRules by set type:")
print(rules['set_label'].value_counts())

# All mandatory rules
mandatory = sequences[sequences['always_ordered'] == True].sort_values('total_cooccurrences', ascending=False)
print(f"\nMandatory rules: {len(mandatory)}")
```

---

## Related Files

- **Data**: `data/analytics/features/ordering_constraints.parquet` (686 rules)
- **Generator**: `src/phish_setlist_maker/generator/core.py`
- **Feature Store**: `src/phish_setlist_maker/analysis/feature_store.py`
- **Tests**: `tests/test_generator.py`
- **Analysis**: `docs/figures/README.md`

---

## Risk Assessment

**If rules NOT properly enforced**:
- ❌ Generated setlists violate authentic song pairings
- ❌ Famous sequences like Mike's → Weekapaug might be wrong order
- ❌ Setlists sound "broken" to Phish fans
- ❌ All "constraint" claims in documentation are false

**If properly enforced**:
- ✅ Setlists respect 686 authentic rules
- ✅ 100% compliance with famous sequences
- ✅ System working as documented
- ✅ Can move to next features (openers, venue, etc.)

---

## Next Steps

1. **Read this doc** - Understand the problem
2. **Run audit** - Check generator code for constraint loading
3. **Run test** - Generate 100 setlists and check for violations
4. **Report findings** - What's broken? What's working?
5. **Fix** - Implement missing constraints (if needed)
6. **Validate** - 100% compliance test
7. **Document** - Update metrics and roadmap

---

**Priority**: CRITICAL — Directly impacts setlist quality  
**Estimated Time**: 1–3 days (audit + fix + validation)  
**Impact**: High — Affects all generated setlists

Ready to investigate? 🔍

---

**Related Documentation**:
- `docs/ml/03-CONSTRAINTS-HEURISTICS.md` - Constraint system overview
- `docs/figures/README.md` - Ordering rules analysis
- `docs/ML-OVERVIEW.md` - Mentions this as next priority
