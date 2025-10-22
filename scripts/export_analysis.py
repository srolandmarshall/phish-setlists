"""Export analysis-ready tables to disk."""

from __future__ import annotations

import argparse
from pathlib import Path

from phish_setlist_maker.analysis import (
    build_set_segments,
    build_song_set_frequencies,
    build_song_transitions,
    load_show_dataframe,
    load_song_dataframe,
    load_track_dataframe,
)
from phish_setlist_maker.db import analytics_session_scope, session_scope


def _write_frame(frame: pd.DataFrame, destination: Path, fmt: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "parquet":
        frame.to_parquet(destination, index=False)
    elif fmt == "csv":
        frame.to_csv(destination, index=False)
    elif fmt == "json":
        frame.to_json(destination, orient="records", indent=2)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def export_table(
    table: str,
    destination: Path,
    *,
    fmt: str,
    min_count: int,
    min_appearances: int,
    use_primary: bool,
) -> None:
    scope = session_scope if use_primary else analytics_session_scope

    with scope() as session:
        if table == "shows":
            frame = load_show_dataframe(session)
        elif table == "tracks":
            frame = load_track_dataframe(session)
        elif table == "songs":
            frame = load_song_dataframe(session)
        elif table == "set_segments":
            tracks = load_track_dataframe(session)
            frame = build_set_segments(tracks)
        elif table == "song_transitions":
            tracks = load_track_dataframe(session)
            frame = build_song_transitions(tracks, min_count=min_count)
        elif table == "song_set_frequencies":
            tracks = load_track_dataframe(session)
            frame = build_song_set_frequencies(
                tracks, min_appearances=min_appearances
            )
        else:
            raise ValueError(f"Unknown table: {table}")

    _write_frame(frame, destination, fmt)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export analytics tables.")
    parser.add_argument(
        "--table",
        required=True,
        choices=[
            "shows",
            "tracks",
            "songs",
            "set_segments",
            "song_transitions",
            "song_set_frequencies",
        ],
        help="Name of the table to export.",
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Destination file path.",
    )
    parser.add_argument(
        "--format",
        default="parquet",
        choices=["parquet", "csv", "json"],
        help="Output format (default: parquet).",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="Minimum transition count when exporting song_transitions.",
    )
    parser.add_argument(
        "--min-appearances",
        type=int,
        default=1,
        help="Minimum appearances when exporting song_set_frequencies.",
    )
    parser.add_argument(
        "--use-primary",
        action="store_true",
        help="Use the primary database instead of the analytics clone.",
    )

    args = parser.parse_args()

    export_table(
        args.table,
        args.out,
        fmt=args.format,
        min_count=args.min_count,
        min_appearances=args.min_appearances,
        use_primary=args.use_primary,
    )


if __name__ == "__main__":
    main()
