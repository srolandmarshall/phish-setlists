"""Generate time-series trend tables from exported analytics datasets."""

from __future__ import annotations

import argparse
from pathlib import Path

from phish_setlist_maker.analysis.trends import (
    build_intro_outro_counts,
    build_set_duration_summary,
    build_song_year_counts,
    load_parquet as _load_parquet,
    write_parquet as _write_parquet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build trend tables from analytics exports.")
    parser.add_argument(
        "--tracks",
        type=Path,
        default=Path("data/analytics/tracks.parquet"),
        help="Path to the exported tracks dataset (default: data/analytics/tracks.parquet).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/analytics/trends"),
        help="Directory to store derived tables (default: data/analytics/trends).",
    )
    args = parser.parse_args()

    tracks = _load_parquet(args.tracks)

    song_year_counts = build_song_year_counts(tracks)
    _write_parquet(song_year_counts, args.out_dir / "song_year_counts.parquet")

    set_duration_summary = build_set_duration_summary(tracks)
    _write_parquet(set_duration_summary, args.out_dir / "set_duration_summary.parquet")

    intro_outro_counts = build_intro_outro_counts(tracks)
    _write_parquet(intro_outro_counts, args.out_dir / "intro_outro_counts.parquet")

    print("Trend tables written to", args.out_dir)


if __name__ == "__main__":
    main()
