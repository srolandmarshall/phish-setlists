"""Database-backed export helpers for analytics datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..db import analytics_session_scope, session_scope
from .database import (
    build_set_segments,
    build_song_set_frequencies,
    build_song_transitions,
    load_show_dataframe,
    load_song_dataframe,
    load_track_dataframe,
)


def write_frame(frame: pd.DataFrame, destination: Path, file_format: str) -> None:
    """Write one dataframe in a supported analytics export format."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if file_format == "parquet":
        frame.to_parquet(destination, index=False)
    elif file_format == "csv":
        frame.to_csv(destination, index=False)
    elif file_format == "json":
        frame.to_json(destination, orient="records", indent=2)
    else:
        raise ValueError(f"Unsupported format: {file_format}")


def export_table(
    table: str,
    destination: Path,
    *,
    fmt: str,
    min_count: int,
    min_appearances: int,
    use_primary: bool,
) -> None:
    """Load, transform, and write one analytics table."""
    scope = session_scope if use_primary else analytics_session_scope

    with scope() as session:
        if table == "shows":
            frame = load_show_dataframe(session)
        elif table == "tracks":
            frame = load_track_dataframe(session)
        elif table == "songs":
            frame = load_song_dataframe(session)
        elif table == "set_segments":
            frame = build_set_segments(load_track_dataframe(session))
        elif table == "song_transitions":
            frame = build_song_transitions(
                load_track_dataframe(session), min_count=min_count
            )
        elif table == "song_set_frequencies":
            frame = build_song_set_frequencies(
                load_track_dataframe(session), min_appearances=min_appearances
            )
        else:
            raise ValueError(f"Unknown table: {table}")

    write_frame(frame, destination, fmt)
