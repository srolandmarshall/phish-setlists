"""Export analysis-ready tables to disk."""

from __future__ import annotations

import argparse
from pathlib import Path

from phish_setlist_maker.analysis.exporting import (
    export_table,
    write_frame as _write_frame,
)


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
