#!/usr/bin/env python
"""Discover set-level ordering constraints (not just adjacent pairs)."""

import sys
from pathlib import Path

from phish_setlist_maker.analysis.database import load_track_dataframe
from phish_setlist_maker.analysis.features import compute_set_ordering_constraints
from phish_setlist_maker.db import session_scope


def main():
    output_dir = Path("data/analytics/features")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Discovering set-level ordering constraints...")
    print("=" * 70)
    
    with session_scope() as session:
        # Load track data
        print("\n1. Loading track data from database...")
        tracks_df = load_track_dataframe(session)
        print(f"   Loaded {len(tracks_df)} tracks")
        
        # Compute ordering constraints
        print("\n2. Analyzing song pair orderings within sets...")
        ordering_df = compute_set_ordering_constraints(
            tracks_df,
            min_cooccurrence=20,
            directionality_threshold=0.90,
        )
        print(f"   Found {len(ordering_df)} song pairs that cooccur frequently")
        
        # Show mandatory orderings
        mandatory = ordering_df[ordering_df["is_ordering_mandatory"]]
        print(f"\n3. Mandatory ordering constraints (≥90% directional):")
        print(f"   Found {len(mandatory)} mandatory orderings")
        
        if not mandatory.empty:
            top_mandatory = mandatory.nlargest(15, "a_before_b_ratio")
            print("\n   Top mandatory orderings:")
            for _, row in top_mandatory.iterrows():
                print(
                    f"   {row['song_a']:30s} → {row['song_b']:30s} "
                    f"({row['a_before_b_ratio']:.1%}, n={int(row['cooccurrence_count'])})"
                )
        
        # Save to parquet
        output_path = output_dir / "ordering_constraints.parquet"
        ordering_df.to_parquet(output_path, index=False)
        print(f"\n✓ Saved to {output_path}")
        print(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")
        
        return 0


if __name__ == "__main__":
    sys.exit(main())
