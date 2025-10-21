"""Smoke tests for the CLI entrypoint."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import importlib.util
from pathlib import Path

from pytest_mock import MockerFixture

from phish_setlist_maker.generator.core import GenerationMetadata, GeneratedSetlist, SetSegment
from phish_setlist_maker.service import GenerationResult, SegmentDetails, SongDisplay


def _fake_cli_result() -> GenerationResult:
    metadata = GenerationMetadata(
        reference_date=date(2024, 1, 1),
        cutoff_date=date(2024, 1, 1),
        era="4.0",
        year=2024,
        notes=[],
    )
    generated = GeneratedSetlist(
        sets=[SetSegment(label="Set 1", songs=["Maze"])],
        encore=None,
        metadata=metadata,
    )
    segments = [
        SegmentDetails(
            label="Set 1",
            songs=["Maze"],
            tracks=[SongDisplay(title="Maze", duration_seconds=600)],
            duration_seconds=600,
        )
    ]
    return GenerationResult(
        seed=11,
        generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        generated=generated,
        segments=segments,
        encore=None,
        playlist=None,
        html=None,
    )


def test_cli_html_invocation(tmp_path, db_session, mocker: MockerFixture, monkeypatch, capsys) -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "generate_setlist.py"
    spec = importlib.util.spec_from_file_location("generate_setlist", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[misc]
    cli = module

    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)

    @contextmanager
    def fake_session_scope():
        yield db_session

    monkeypatch.setattr(cli, "session_scope", fake_session_scope)

    mocker.patch.object(cli, "generate_show", return_value=_fake_cli_result())
    render_html_spy = mocker.patch.object(cli, "render_html_report")
    render_markdown_spy = mocker.patch.object(cli, "render_markdown")

    monkeypatch.setattr(cli.sys, "argv", [str(tmp_path / "scripts" / "generate_setlist.py"), "--html"])

    cli.main()

    captured = capsys.readouterr()
    assert "Wrote setlist to" in captured.out
    assert render_html_spy.called
    assert not render_markdown_spy.called
    output_path_arg = render_html_spy.call_args.kwargs.get("output_path")
    assert output_path_arg is not None
    assert Path(output_path_arg).parent == tmp_path / "data"
