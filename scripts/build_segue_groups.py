"""Build segue groups from database track data.

Extracts complete segue chains (not just pairs!) and separates them into:
1. Mandatory segues (≥50 occurrences) - Always enforced (stored as pairs for flexibility)
2. Rare segues (<50 occurrences) - Lottery tickets (stored as complete chains!)

Outputs:
- data/analytics/features/segue_groups.parquet (pairs for mandatory)
- data/analytics/features/rare_segues.parquet (complete chains!)
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from sqlalchemy.orm import Session

from phish_setlist_maker.analysis.segue_chains import (
    adjacent_pairs_from_rows,
    build_dataframe,
    calculate_chain_pattern_frequencies,
    calculate_frequencies,
    complete_chains_from_rows,
    extract_pairs_from_chains,
    extract_subchains,
    separate_chains_by_frequency,
)
from phish_setlist_maker.analysis.segue_data import (
    load_adjacent_pair_rows,
    load_ordered_track_rows,
)
from phish_setlist_maker.db import session_scope


def extract_complete_chains(session: Session) -> List[dict]:
    """Load ordered track rows and build contiguous historical chains."""
    return complete_chains_from_rows(load_ordered_track_rows(session))


def extract_adjacent_pairs(session: Session) -> List[dict]:
    """Load adjacent track rows and normalize them into pair records."""
    return adjacent_pairs_from_rows(load_adjacent_pair_rows(session))


def build_all_segues(
    session: Session,
    output_dir: Path,
    threshold: int = 50,
    max_rare_chain_length: int = 5,
    min_lottery_likes: int = 5
) -> Tuple[int, int]:
    """
    Build both mandatory and rare segue tables.

    Mandatory segues (≥threshold): Stored as pairs for generation flexibility
    Rare segues (<threshold): Stored as complete chains for lottery tickets!

    Args:
        threshold: Minimum occurrences for mandatory segues
        max_rare_chain_length: Maximum length for rare segue chains (to avoid capturing entire sets)

    Returns (num_mandatory, num_rare).
    """
    print("Extracting complete segue chains from database...")
    chains = extract_complete_chains(session)
    print(f"  Found {len(chains)} complete segue chains")

    print(f"Extracting sub-chains (max length {max_rare_chain_length}, min likes {min_lottery_likes})...")
    subchains = extract_subchains(chains, max_length=max_rare_chain_length, min_total_likes=min_lottery_likes)
    print(f"  Extracted {len(subchains)} sub-chains (pre-filtered by likes)")

    print("Extracting pairs from chains...")
    pairs = extract_pairs_from_chains(chains)
    print(f"  Extracted {len(pairs)} adjacent track pairs")

    print("Calculating frequencies...")
    pair_frequencies = calculate_frequencies(pairs)
    subchain_frequencies = calculate_chain_pattern_frequencies(subchains)
    print(f"  Found {len(pair_frequencies)} unique song pairs")
    print(f"  Found {len(subchain_frequencies)} unique sub-chain patterns")

    print(f"Separating by frequency (threshold={threshold}, min_lottery_likes={min_lottery_likes})...")
    mandatory, rare = separate_chains_by_frequency(
        subchains, subchain_frequencies, pairs, pair_frequencies,
        threshold=threshold, max_rare_chain_length=max_rare_chain_length,
        min_lottery_likes=min_lottery_likes
    )
    print(f"  Mandatory segues (pairs): {len(mandatory)}")
    print(f"  Rare segues (complete chains): {len(rare)}")

    # Show some stats about rare chains
    if rare:
        chain_lengths = [len(r['tracks']) for r in rare]
        print(f"  Rare chain lengths: min={min(chain_lengths)}, max={max(chain_lengths)}, avg={sum(chain_lengths)/len(chain_lengths):.1f}")

    print("Building DataFrames...")
    df_mandatory = build_dataframe(mandatory)
    df_rare = build_dataframe(rare)

    print("Saving to parquet...")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df_mandatory.to_parquet(output_dir / "segue_groups.parquet", index=False)
    df_rare.to_parquet(output_dir / "rare_segues.parquet", index=False)

    print(f"✓ Saved {len(mandatory)} mandatory segues to segue_groups.parquet")
    print(f"✓ Saved {len(rare)} rare segues to rare_segues.parquet")

    return len(mandatory), len(rare)


def main():
    """Main entry point for building segue groups."""
    with session_scope() as session:
        output_dir = Path(__file__).parent.parent / "data" / "analytics" / "features"
        build_all_segues(session, output_dir=output_dir, threshold=50)



if __name__ == "__main__":
    main()
