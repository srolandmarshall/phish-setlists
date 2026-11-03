"""Pure dataframe transformations for exported analytics trend tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_parquet(path: Path) -> pd.DataFrame:
    """Load a required Parquet dataset with a clear missing-file error."""
    if not path.exists():
        raise FileNotFoundError(f"Required dataset not found: {path}")
    return pd.read_parquet(path)


def write_parquet(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(destination, index=False)


def build_song_year_counts(tracks: pd.DataFrame) -> pd.DataFrame:
    working = tracks.dropna(subset=["show_date", "song_effective_title"]).copy()
    working["year"] = working["show_date"].dt.year
    return (
        working.groupby(["year", "song_effective_title"])
        .agg(play_count=("track_id", "nunique"))
        .reset_index()
        .sort_values(["year", "play_count"], ascending=[True, False])
    )


def build_set_duration_summary(tracks: pd.DataFrame) -> pd.DataFrame:
    working = tracks.dropna(
        subset=["show_id", "canonical_set", "duration_seconds", "show_date"]
    ).copy()
    working["year"] = working["show_date"].dt.year
    return (
        working.groupby(["year", "canonical_set"])
        .agg(
            total_duration_seconds=("duration_seconds", "sum"),
            median_duration_seconds=("duration_seconds", "median"),
            shows_count=("show_id", "nunique"),
        )
        .reset_index()
        .sort_values(["year", "canonical_set"])
    )


def build_intro_outro_counts(tracks: pd.DataFrame) -> pd.DataFrame:
    working = tracks.dropna(
        subset=[
            "show_id",
            "canonical_set",
            "position",
            "song_effective_title",
            "show_date",
        ]
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

    counts = (
        pd.concat([first, last], ignore_index=True)
        .groupby(["year", "canonical_set", "type", "song"])
        .size()
        .reset_index(name="appearances")
    )
    return counts.sort_values(
        ["year", "canonical_set", "type", "appearances"],
        ascending=[True, True, True, False],
    )
