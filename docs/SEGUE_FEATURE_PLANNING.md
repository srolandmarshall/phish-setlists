# Segue Feature — Consolidated Plan
Date: 2025-11-07
Status: Direction decided; implementation underway

## Problem
- Current system prevents bad order but doesn’t proactively keep famous pairs adjacent.
- Song-level selection mixes performances across shows; authentic segues require track-level pairing.

## Decisions
- Treat famous sequences as track-level “segue groups” drawn from the same show/set.
- Use a two-tier approach:
  - Mandatory segues (high-frequency, high-confidence) — always enforce during generation.
  - Rare segues (“lottery tickets”) — optional injection, weighted by likes/rarity.
- Keep post-generation dependency rules as a safety net.

## Data Artifacts (Parquet)
- segue_groups.parquet: mandatory pairs/sandwiches with track IDs, durations, likes, confidence.
- rare_segues.parquet: long-tail adjacent pairs with rarity, likes, tags.
- segue_lookup.parquet: fast index (song → segues that start with it).

## Implementation Outline
1) Build scripts
   - Query adjacent track pairs; separate mandatory vs. rare by thresholds; write parquet tables.
2) Feature store
   - Eager-load segue tables; indexes by song and by track; lightweight (<~25 MB total in max mode).
3) Generator
   - Priority: mandatory segues → rare segues (lottery) → normal selection.
   - Mandatory: force-adjacent selection from available groups that fit duration.
   - Rare: probabilistic injection based on rarity/likes; can replace a low-value song if tight.
   - Continue to run post-gen rules as fallback.

## Ordering/Directional Rules Alignment
- Keep ordering constraints to prevent violations.
- Replace weak “3× weight boost” for mandatory transitions with forced selection when available.
- Ensure famous sequences (e.g., Mike’s → Hydrogen → Weekapaug) are represented in segue tables.

## Validation
- Generate 100 setlists; verify adjacency rates for top sequences (~95%+ where historically warranted).
- Confirm tracks in a segue share show_id/set; check duration budgeting and fallback behavior.

## Notes
- Memory/IO cost is minimal for mandatory-only; acceptable for maximum (rare segues) with lazy-loading.
- This preserves authenticity (same-show tracks) while retaining variety via the lottery tier.
