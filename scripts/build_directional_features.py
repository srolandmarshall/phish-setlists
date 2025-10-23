#!/usr/bin/env python
"""Build directional transition features with sequence constraints."""

import sys
from pathlib import Path

import pandas as pd

from phish_setlist_maker.analysis.database import build_song_transitions, load_track_dataframe
from phish_setlist_maker.analysis.features import compute_directional_transitions
from phish_setlist_maker.db import session_scope


def main():
    output_dir = Path("data/analytics/features")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Building directional transition features...")
    print("=" * 60)
    
    with session_scope() as session:
        # Load track data
        print("\n1. Loading track data from database...")
        tracks_df = load_track_dataframe(session)
        print(f"   Loaded {len(tracks_df)} tracks")
        
        # Build transition counts
        print("\n2. Computing transition counts...")
        transitions_df = build_song_transitions(tracks_df, min_count=1)
        print(f"   Found {len(transitions_df)} transitions")
        
        # Compute directional analysis
        print("\n3. Computing directional constraints...")
        directional_df = compute_directional_transitions(
            transitions_df,
            min_support=10,
            mandatory_threshold=0.85,
            adjacency_threshold=1.5,
        )
        print(f"   Analyzed {len(directional_df)} directional pairs")
        directional_df = compute_directional_transitions(
            transitions_df,
            min_support=10,
            mandatory_threshold=0.85,
            adjacency_threshold=1.5,
        )
        print(f"   Analyzed {len(directional_df)} directional pairs")
        
        # Show summary statistics
        mandatory = directional_df[directional_df["is_mandatory"]]
        forbidden_reverse = directional_df[directional_df["is_reverse_forbidden"]]
        
        print("\n4. Summary:")
        print(f"   • Mandatory sequences: {len(mandatory)}")
        print(f"   • Forbidden reverses: {len(forbidden_reverse)}")
        print(f"   • Average forward confidence: {directional_df['forward_confidence'].mean():.2%}")
        
        # Show top mandatory sequences
        print("\n5. Top mandatory sequences (confidence ≥ 85%):")
        if not mandatory.empty:
            top_mandatory = mandatory.nlargest(10, "forward_confidence")
            for _, row in top_mandatory.iterrows():
                print(
                    f"   {row['from_song']:30s} → {row['to_song']:30s} "
                    f"({row['forward_confidence']:.1%}, n={int(row['forward_count'])})"
                )
        
        # Show forbidden reverses
        print("\n6. Sample forbidden reverse transitions:")
        if not forbidden_reverse.empty:
            sample_forbidden = forbidden_reverse.head(10)
            for _, row in sample_forbidden.iterrows():
                print(
                    f"   {row['to_song']:30s} → {row['from_song']:30s} "
                    f"(forbidden, forward={int(row['forward_count'])}, reverse={int(row['reverse_count'])})"
                )
        
        # Save to parquet
        output_path = output_dir / "directional_transitions.parquet"
        directional_df.to_parquet(output_path, index=False)
        print(f"\n✓ Saved to {output_path}")
        print(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")
        
        return 0


if __name__ == "__main__":
    sys.exit(main())
