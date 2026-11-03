"""Composable orchestration for complete analytics exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from ..db import analytics_session_scope, session_scope
from .database import (
    build_venue_tendencies,
    load_show_dataframe,
    load_tour_dataframe,
    load_venue_dataframe,
)
from .exporting import export_table
from .trends import (
    build_intro_outro_counts,
    build_set_duration_summary,
    build_song_year_counts,
)


@dataclass(frozen=True, slots=True)
class AnalyticsExportOptions:
    output_dir: Path = Path("data/analytics")
    file_format: str = "parquet"
    min_transition_count: int = 10
    min_placement_appearances: int = 5
    use_primary: bool = False


def run_analytics_exports(
    options: AnalyticsExportOptions,
    *,
    table_exporter: Callable[..., None] | None = None,
    parquet_reader: Callable[[Path], pd.DataFrame] | None = None,
    parquet_writer: Callable[[pd.DataFrame, Path], None] | None = None,
) -> None:
    """Run base exports and, for Parquet, all derived trend exports."""
    table_exporter = table_exporter or export_table
    parquet_reader = parquet_reader or pd.read_parquet
    parquet_writer = parquet_writer or _write_parquet
    base_dir = options.output_dir
    trend_dir = base_dir / "trends"
    base_dir.mkdir(parents=True, exist_ok=True)
    trend_dir.mkdir(parents=True, exist_ok=True)

    common = {
        "fmt": options.file_format,
        "use_primary": options.use_primary,
    }
    table_exporter(
        "shows", base_dir / f"shows.{options.file_format}",
        min_count=1, min_appearances=1, **common,
    )
    table_exporter(
        "tracks", base_dir / f"tracks.{options.file_format}",
        min_count=1, min_appearances=1, **common,
    )
    table_exporter(
        "songs", base_dir / f"songs.{options.file_format}",
        min_count=1, min_appearances=1, **common,
    )
    table_exporter(
        "set_segments", base_dir / f"set_segments.{options.file_format}",
        min_count=1, min_appearances=1, **common,
    )
    table_exporter(
        "song_transitions", base_dir / f"song_transitions.{options.file_format}",
        min_count=options.min_transition_count, min_appearances=1, **common,
    )
    table_exporter(
        "song_set_frequencies",
        base_dir / f"song_set_frequencies.{options.file_format}",
        min_count=1,
        min_appearances=options.min_placement_appearances,
        **common,
    )

    if options.file_format != "parquet":
        print("Trend tables require Parquet exports; skipping trend generation.")
        return

    tracks = parquet_reader(base_dir / "tracks.parquet")
    parquet_writer(
        build_song_year_counts(tracks), trend_dir / "song_year_counts.parquet"
    )
    parquet_writer(
        build_set_duration_summary(tracks),
        trend_dir / "set_duration_summary.parquet",
    )
    parquet_writer(
        build_intro_outro_counts(tracks),
        trend_dir / "intro_outro_counts.parquet",
    )

    print("Building venue and tour analysis...")
    scope = session_scope if options.use_primary else analytics_session_scope
    with scope() as session:
        venues = load_venue_dataframe(session)
        tours = load_tour_dataframe(session)
        shows = load_show_dataframe(session)

    parquet_writer(venues, base_dir / "venues.parquet")
    parquet_writer(tours, base_dir / "tours.parquet")
    parquet_writer(
        build_venue_tendencies(tracks, shows),
        base_dir / "venue_tendencies.parquet",
    )
    print("Analytics exports complete.")


def _write_parquet(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(destination, index=False)
