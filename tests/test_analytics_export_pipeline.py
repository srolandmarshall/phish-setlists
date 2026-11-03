from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd

from phish_setlist_maker.analysis import export_pipeline
from phish_setlist_maker.analysis.export_pipeline import (
    AnalyticsExportOptions,
    run_analytics_exports,
)


def test_non_parquet_pipeline_exports_base_tables_and_skips_trends(tmp_path):
    calls = []

    def export_table(table, destination, **kwargs):
        calls.append((table, destination, kwargs))

    run_analytics_exports(
        AnalyticsExportOptions(
            output_dir=tmp_path,
            file_format="csv",
            min_transition_count=12,
            min_placement_appearances=7,
            use_primary=True,
        ),
        table_exporter=export_table,
    )

    assert [table for table, _, _ in calls] == [
        "shows",
        "tracks",
        "songs",
        "set_segments",
        "song_transitions",
        "song_set_frequencies",
    ]
    assert all(path.suffix == ".csv" for _, path, _ in calls)
    assert all(kwargs["fmt"] == "csv" for _, _, kwargs in calls)
    assert all(kwargs["use_primary"] for _, _, kwargs in calls)
    assert calls[-2][2]["min_count"] == 12
    assert calls[-1][2]["min_appearances"] == 7
    assert (tmp_path / "trends").is_dir()


def test_parquet_pipeline_writes_trends_and_uses_primary_scope(
    tmp_path, monkeypatch
):
    calls = []
    writes = []
    scope_calls = []
    tracks = pd.DataFrame(
        [
            {
                "track_id": 1,
                "show_id": 10,
                "show_date": datetime(1995, 6, 16),
                "canonical_set": "set1",
                "position": 1,
                "song_effective_title": "Sample Song",
                "duration_seconds": 240,
            },
            {
                "track_id": 2,
                "show_id": 10,
                "show_date": datetime(1995, 6, 16),
                "canonical_set": "set1",
                "position": 2,
                "song_effective_title": "Other Song",
                "duration_seconds": 300,
            },
        ]
    )
    venues = pd.DataFrame({"venue": ["Sample Hall"]})
    tours = pd.DataFrame({"tour": ["Sample Tour"]})
    shows = pd.DataFrame({"show_id": [10]})

    @contextmanager
    def primary_scope():
        scope_calls.append("primary")
        yield object()

    @contextmanager
    def analytics_scope():
        scope_calls.append("analytics")
        yield object()

    monkeypatch.setattr(export_pipeline, "session_scope", primary_scope)
    monkeypatch.setattr(export_pipeline, "analytics_session_scope", analytics_scope)
    monkeypatch.setattr(export_pipeline, "load_venue_dataframe", lambda _session: venues)
    monkeypatch.setattr(export_pipeline, "load_tour_dataframe", lambda _session: tours)
    monkeypatch.setattr(export_pipeline, "load_show_dataframe", lambda _session: shows)
    monkeypatch.setattr(
        export_pipeline,
        "build_venue_tendencies",
        lambda _tracks, _shows: pd.DataFrame({"tendency": [1]}),
    )

    run_analytics_exports(
        AnalyticsExportOptions(output_dir=tmp_path, use_primary=True),
        table_exporter=lambda *args, **kwargs: calls.append((args, kwargs)),
        parquet_reader=lambda _path: tracks,
        parquet_writer=lambda frame, path: writes.append((frame, path)),
    )

    assert len(calls) == 6
    assert scope_calls == ["primary"]
    assert {path.name for _, path in writes} == {
        "song_year_counts.parquet",
        "set_duration_summary.parquet",
        "intro_outro_counts.parquet",
        "venues.parquet",
        "tours.parquet",
        "venue_tendencies.parquet",
    }


def test_analytics_pipeline_supports_direct_and_module_cli_invocation():
    repository = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repository / "src")
    commands = [
        [sys.executable, "scripts/run_analytics_exports.py", "--help"],
        [sys.executable, "-m", "scripts.run_analytics_exports", "--help"],
    ]

    for command in commands:
        result = subprocess.run(
            command,
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "--out-dir" in result.stdout
        assert "--min-transition-count" in result.stdout
