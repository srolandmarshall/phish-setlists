"""Run the full analytics export pipeline in one shot."""

from __future__ import annotations

import argparse
from pathlib import Path

from phish_setlist_maker.analysis.export_pipeline import (
    AnalyticsExportOptions,
    run_analytics_exports,
)


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
    run_analytics_exports(
        AnalyticsExportOptions(
            output_dir=args.out_dir,
            file_format=args.format,
            min_transition_count=args.min_transition_count,
            min_placement_appearances=args.min_placement_appearances,
            use_primary=args.use_primary,
        )
    )


if __name__ == "__main__":
    main()
