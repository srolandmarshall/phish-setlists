#!/usr/bin/env python3
"""Build venue and tour analysis tables. Run with --help for options."""

import argparse
from pathlib import Path

import pandas as pd

from phish_setlist_maker.analysis.database import (
    build_venue_tendencies,
    load_show_dataframe,
    load_tour_dataframe,
    load_track_dataframe,
    load_venue_dataframe,
)
from phish_setlist_maker.db import session_scope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/analytics"),
        help="Output directory for Parquet files",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    with session_scope() as session:
        print("Loading venues...")
        venues = load_venue_dataframe(session)
        venue_path = args.out_dir / "venues.parquet"
        venues.to_parquet(venue_path, index=False)
        print(f"  → {venue_path} ({len(venues)} venues)")

        print("Loading tours...")
        tours = load_tour_dataframe(session)
        tour_path = args.out_dir / "tours.parquet"
        tours.to_parquet(tour_path, index=False)
        print(f"  → {tour_path} ({len(tours)} tours)")

        print("Loading shows & tracks for venue tendencies...")
        shows = load_show_dataframe(session)
        tracks = load_track_dataframe(session)

        print("Building venue tendencies...")
        venue_tendencies = build_venue_tendencies(tracks, shows)
        tendencies_path = args.out_dir / "venue_tendencies.parquet"
        venue_tendencies.to_parquet(tendencies_path, index=False)
        print(f"  → {tendencies_path} ({len(venue_tendencies)} venues with stats)")

    print("\nDone. Use these files in notebooks or downstream scripts.")


if __name__ == "__main__":
    main()
