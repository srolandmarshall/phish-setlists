#!/usr/bin/env python3
"""Display venue and tour analysis. Run after build_venue_tour_analysis.py."""

import argparse
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/analytics"),
        help="Directory with Parquet files",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=15,
        help="Number of top venues/tours to display",
    )
    args = parser.parse_args()

    venues = pd.read_parquet(args.data_dir / "venues.parquet")
    tours = pd.read_parquet(args.data_dir / "tours.parquet")
    tendencies = pd.read_parquet(args.data_dir / "venue_tendencies.parquet")

    merged = tendencies.merge(
        venues[["venue_id", "venue_name", "city", "state", "country"]],
        on="venue_id",
    )

    print("=== Top Venues by Show Count ===\n")
    top_venues = merged.nlargest(args.top_n, "show_count")
    for _, row in top_venues.iterrows():
        location = f"{row['city']}, {row['state']}" if row["state"] else row["city"]
        print(f"{row['venue_name']} ({location})")
        print(f"  {row['show_count']} shows, {row['track_count']} tracks")
        print(f"  Avg show duration: {row['avg_show_duration']/60:.1f} min")
        if row["top_songs"]:
            print(f"  Top songs: {', '.join(row['top_songs'][:3])}")
        print()

    print("\n=== Notable Tours ===\n")
    top_tours = tours.nlargest(args.top_n, "shows_count")
    for _, row in top_tours.iterrows():
        start = row["starts_on"].strftime("%Y-%m-%d") if pd.notna(row["starts_on"]) else "?"
        end = row["ends_on"].strftime("%Y-%m-%d") if pd.notna(row["ends_on"]) else "?"
        print(f"{row['tour_name']}")
        print(f"  {start} to {end} ({row['duration_days']} days)")
        print(f"  {row['shows_count']} shows")
        print()


if __name__ == "__main__":
    main()
