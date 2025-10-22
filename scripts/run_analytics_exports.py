"""Run the full analytics export pipeline in one shot."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from export_analysis import export_table
from build_trend_tables import (
    build_intro_outro_counts,
    build_set_duration_summary,
    build_song_year_counts,
)


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export analytics datasets and derived trend tables.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/analytics"),
        help="Destination directory for exported tables (default: data/analytics)",
    )
    parser.add_argument(
        "--format",
        choices=["parquet", "csv", "json"],
        default="parquet",
        help="File format for base exports (default: parquet)",
    )
    parser.add_argument(
        "--min-transition-count",
        type=int,
        default=10,
        help="Minimum occurrences for song transitions (default: 10)",
    )
    parser.add_argument(
        "--min-placement-appearances",
        type=int,
        default=5,
        help="Minimum appearances for song set placement probabilities (default: 5)",
    )
    parser.add_argument(
        "--use-primary",
        action="store_true",
        help="Read from the primary database instead of the analytics clone.",
    )
    args = parser.parse_args()

    base_dir = args.out_dir
    trend_dir = base_dir / "trends"
    _ensure_directory(base_dir)
    _ensure_directory(trend_dir)

    # Core tables
    export_table("shows", base_dir / f"shows.{args.format}", fmt=args.format, use_primary=args.use_primary, min_count=1, min_appearances=1)
    export_table("tracks", base_dir / f"tracks.{args.format}", fmt=args.format, use_primary=args.use_primary, min_count=1, min_appearances=1)
    export_table("songs", base_dir / f"songs.{args.format}", fmt=args.format, use_primary=args.use_primary, min_count=1, min_appearances=1)

    # Aggregated tables
    export_table("set_segments", base_dir / f"set_segments.{args.format}", fmt=args.format, use_primary=args.use_primary, min_count=1, min_appearances=1)
    export_table(
        "song_transitions",
        base_dir / f"song_transitions.{args.format}",
        fmt=args.format,
        min_count=args.min_transition_count,
        use_primary=args.use_primary,
        min_appearances=1,
    )
    export_table(
        "song_set_frequencies",
        base_dir / f"song_set_frequencies.{args.format}",
        fmt=args.format,
        min_appearances=args.min_placement_appearances,
        use_primary=args.use_primary,
        min_count=1,
    )

    if args.format != "parquet":
        print("Trend tables require Parquet exports; skipping trend generation.")
        return

    tracks_path = base_dir / "tracks.parquet"
    tracks = pd.read_parquet(tracks_path)

    song_year_counts = build_song_year_counts(tracks)
    song_year_counts.to_parquet(trend_dir / "song_year_counts.parquet", index=False)

    set_duration_summary = build_set_duration_summary(tracks)
    set_duration_summary.to_parquet(trend_dir / "set_duration_summary.parquet", index=False)

    intro_outro_counts = build_intro_outro_counts(tracks)
    intro_outro_counts.to_parquet(trend_dir / "intro_outro_counts.parquet", index=False)

    print("Analytics exports complete.")


if __name__ == "__main__":
    main()
