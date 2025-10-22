#!/usr/bin/env python
"""Demo script showing ML-enhanced setlist generation.

Compare legacy mode vs. ML mode to see feature-driven differences.
"""

from datetime import date
from random import Random

from phish_setlist_maker.db import session_scope
from phish_setlist_maker.generator.core import SetlistGenerator


def main():
    with session_scope() as session:
        seed = 12345
        ref_date = date(2023, 12, 31)
        
        print("=" * 70)
        print("LEGACY MODE (Historical Frequencies Only)")
        print("=" * 70)
        
        gen_legacy = SetlistGenerator(session, rng=Random(seed), use_ml_features=False)
        result_legacy = gen_legacy.generate(
            reference_date=ref_date,
            num_sets=2,
            include_encore=True,
        )
        
        for s in result_legacy.sets:
            print(f"\n{s.label}:")
            for song in s.songs:
                print(f"  • {song}")
        
        if result_legacy.encore:
            print(f"\n{result_legacy.encore.label}:")
            for song in result_legacy.encore.songs:
                print(f"  • {song}")
        
        print("\n" + "=" * 70)
        print("ML MODE (30% ML Placement + 10% Transition Bonus)")
        print("=" * 70)
        
        gen_ml = SetlistGenerator(
            session,
            rng=Random(seed),
            use_ml_features=True,
            ml_placement_weight=0.3,
            ml_transition_bonus=0.1,
        )
        result_ml = gen_ml.generate(
            reference_date=ref_date,
            num_sets=2,
            include_encore=True,
        )
        
        for s in result_ml.sets:
            print(f"\n{s.label}:")
            for song in s.songs:
                print(f"  • {song}")
        
        if result_ml.encore:
            print(f"\n{result_ml.encore.label}:")
            for song in result_ml.encore.songs:
                print(f"  • {song}")
        
        print("\n" + "=" * 70)
        print(f"Feature store loaded: {gen_ml._feature_store.loaded}")
        print(f"Songs in catalog: {len(gen_ml._feature_store._song_features)}")
        print(f"Transitions tracked: {len(gen_ml._feature_store._transition_lifts)}")
        print("=" * 70)


if __name__ == "__main__":
    main()
