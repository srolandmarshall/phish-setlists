"""Generate time-series trend tables from exported analytics datasets."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd


def _load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required dataset not found: {path}")
    return pd.read_parquet(path)


def _write_parquet(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(destination, index=False)


def build_song_year_counts(tracks: pd.DataFrame) -> pd.DataFrame:
    working = tracks.dropna(subset=["show_date", "song_effective_title"]).copy()
    working["year"] = working["show_date"].dt.year
    counts = (
        working.groupby(["year", "song_effective_title"])
        .agg(play_count=("track_id", "nunique"))
        .reset_index()
        .sort_values(["year", "play_count"], ascending=[True, False])
    )
    return counts


def build_set_duration_summary(tracks: pd.DataFrame) -> pd.DataFrame:
    working = tracks.dropna(subset=["show_id", "canonical_set", "duration_seconds", "show_date"]).copy()
    working["year"] = working["show_date"].dt.year
    summaries = (
        working.groupby(["year", "canonical_set"])
        .agg(
            total_duration_seconds=("duration_seconds", "sum"),
            median_duration_seconds=("duration_seconds", "median"),
            shows_count=("show_id", "nunique"),
        )
        .reset_index()
        .sort_values(["year", "canonical_set"])
    )
    return summaries


def build_intro_outro_counts(tracks: pd.DataFrame) -> pd.DataFrame:
    working = tracks.dropna(
        subset=["show_id", "canonical_set", "position", "song_effective_title", "show_date"]
    ).copy()
    working["year"] = working["show_date"].dt.year

    ordered = working.sort_values(["show_id", "canonical_set", "position"])

    first = (
        ordered.groupby(["show_id", "canonical_set"])
        .head(1)
        .loc[:, ["show_id", "canonical_set", "year", "song_effective_title"]]
        .rename(columns={"song_effective_title": "song"})
    )
    first["type"] = "intro"

    last = (
        ordered.groupby(["show_id", "canonical_set"])
        .tail(1)
        .loc[:, ["show_id", "canonical_set", "year", "song_effective_title"]]
        .rename(columns={"song_effective_title": "song"})
    )
    last["type"] = "outro"

    combined = pd.concat([first, last], ignore_index=True)

    counts = (
        combined.groupby(["year", "canonical_set", "type", "song"])
        .size()
        .reset_index(name="appearances")
    )

    return counts.sort_values(
        ["year", "canonical_set", "type", "appearances"], ascending=[True, True, True, False]
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
