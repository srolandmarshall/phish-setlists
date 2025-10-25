#!/usr/bin/env python3
"""CLI helper to generate a Phish setlist and emit a Markdown report."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from phish_setlist_maker.db import session_scope  # noqa: E402
from phish_setlist_maker.generator.html_basic import render_html_report  # noqa: E402
from phish_setlist_maker.service import (  # noqa: E402
    GenerationRequest,
    SongDisplay,
    generate_show,
)
from phish_setlist_maker.service.playlist import build_playlist_sections  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Phish setlist and write it to a Markdown file."
    )
    parser.add_argument(
        "--reference-date",
        type=lambda value: datetime.strptime(value, "%Y-%m-%d").date(),
        help="Anchor the generation context (YYYY-MM-DD). Defaults to latest show in DB.",
    )
    parser.add_argument(
        "--era",
        choices=["1.0", "2.0", "3.0", "4.0"],
        help="Restrict history to a specific era. Defaults to 4.0 unless --year predates it.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=datetime.now().year,
        help="Only consider shows through the end of this calendar year (default: current year).",
    )
    parser.add_argument(
        "--num-sets",
        type=int,
        choices=[2, 3],
        default=2,
        help="Number of main sets to generate (default: 2).",
    )
    parser.add_argument(
        "--no-encore",
        action="store_false",
        dest="include_encore",
        help="Skip generating an encore segment.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Seed for deterministic generation. Defaults to cryptographically random when omitted.",
    )
    parser.add_argument(
        "--allow-previous-show",
        dest="allow_previous_show",
        action="store_true",
        help="Allow songs from the previous show to be eligible (default).",
    )
    parser.add_argument(
        "--exclude-previous-show",
        dest="allow_previous_show",
        action="store_false",
        help="Exclude songs from the previous show.",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Render output as HTML instead of Markdown.",
    )
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Build an M3U playlist by pulling public mp3 URLs from phish.in.",
    )
    parser.add_argument(
        "--set-length",
        action="append",
        default=[],
        metavar="SET=COUNT",
        help="Override a set length (e.g., --set-length set1=11). Repeat as needed.",
    )
    parser.add_argument(
        "--jamminess",
        type=float,
        metavar="LEVEL",
        help="Jam intensity (0.0=tight/concise, 0.5=balanced, 1.0=maximum jam). Default: dynamic selection.",
    )
    parser.set_defaults(allow_previous_show=None)
    return parser.parse_args()


def parse_set_lengths(overrides: list[str]) -> Dict[str, int]:
    parsed: Dict[str, int] = {}
    for entry in overrides:
        if "=" not in entry:
            raise ValueError(f"Invalid set-length override '{entry}'. Expected SET=COUNT.")
        label, value = entry.split("=", 1)
        label = label.strip().lower()
        if label not in {"set1", "set2", "set3", "encore"}:
            raise ValueError(f"Unsupported set label '{label}'.")
        try:
            parsed[label] = int(value)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid count for '{label}': {value}") from exc
    return parsed


def format_metadata_line(label: str, value: Optional[str]) -> str:
    display = value if value is not None else "N/A"
    return f"- {label}: {display}"


def render_markdown(
    output_path: Path,
    generated,
    generated_at: datetime,
    *,
    sections: Optional[Sequence[Tuple[str, Sequence[SongDisplay]]]] = None,
) -> None:
    lines = ["# Generated Setlist", ""]

    metadata = generated.metadata
    lines.append("## Context")
    lines.append(format_metadata_line("Generated at", generated_at.isoformat(timespec="seconds")))
    lines.append(format_metadata_line("Reference date", str(metadata.reference_date)))
    lines.append(format_metadata_line("Cutoff date", str(metadata.cutoff_date)))
    lines.append(format_metadata_line("Era", metadata.era or "All history"))
    lines.append(format_metadata_line("Year limit", str(metadata.year) if metadata.year else "Full run"))
    lines.append("")

    section_lookup: Dict[str, Sequence[SongDisplay]] = {}
    if sections:
        for title, tracks in sections:
            section_lookup[title] = tracks

    def section_tracks(label: str, fallback_songs: Sequence[str]) -> Sequence[SongDisplay]:
        rows = section_lookup.get(label)
        if rows:
            return rows
        return [SongDisplay(title=song, mp3_url=None, duration_seconds=None, origin=None) for song in fallback_songs]

    def format_total(seconds: Optional[int]) -> Optional[str]:
        if seconds is None or seconds <= 0:
            return None
        minutes, secs = divmod(seconds, 60)
        return f"{minutes}:{secs:02d}"

    def rows_duration(rows: Sequence[SongDisplay]) -> Optional[int]:
        total = 0
        any_duration = False
        for song in rows:
            if song.duration_seconds and song.duration_seconds > 0:
                total += song.duration_seconds
                any_duration = True
        return total if any_duration else None

    for segment in generated.sets:
        rows = section_tracks(segment.label, segment.songs)
        total_seconds = rows_duration(rows)
        header = segment.label
        formatted_total = format_total(total_seconds)
        if formatted_total:
            header = f"{header} [{formatted_total}]"
        lines.append(f"## {header}")
        for idx, song in enumerate(rows, start=1):
            display = song.title
            if song.duration_label:
                display = f"{display} [{song.duration_label}]"
            lines.append(f"{idx}. {display}")
            if song.origin:
                lines.append(f"   *{song.origin}*")
        lines.append("")

    if generated.encore:
        encore_label = generated.encore.label if generated.encore else "Encore"
        rows = section_tracks(encore_label, generated.encore.songs if generated.encore else [])
        total_seconds = rows_duration(rows)
        formatted_total = format_total(total_seconds)
        header = encore_label if not formatted_total else f"{encore_label} [{formatted_total}]"
        lines.append(f"## {header}")
        for idx, song in enumerate(rows, start=1):
            display = song.title
            if song.duration_label:
                display = f"{display} [{song.duration_label}]"
            lines.append(f"{idx}. {display}")
            if song.origin:
                lines.append(f"   *{song.origin}*")
        lines.append("")

    if metadata.notes:
        lines.append("## Notes")
        for note in metadata.notes:
            lines.append(f"- {note}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()

    set_length_overrides = parse_set_lengths(args.set_length)

    allow_previous_show = True if args.allow_previous_show is None else args.allow_previous_show

    request = GenerationRequest(
        reference_date=args.reference_date,
        era=args.era,
        year=args.year,
        num_sets=args.num_sets,
        include_encore=args.include_encore,
        set_lengths=set_length_overrides or None,
        allow_previous_show=allow_previous_show,
        seed=args.seed,
        include_playlist=args.playlist,
        include_html=False,
        prefetch_track_metadata=True,
        fail_on_playlist_error=False,
        jamminess=args.jamminess,
    )

    with session_scope() as session:
        result = generate_show(session, request)

    generated = result.generated
    now_utc = result.generated_at
    timestamp = now_utc.strftime("%Y%m%d_%H%M%S")
    output_dir = PROJECT_ROOT / "data"
    extension = "html" if args.html else "md"
    output_path = output_dir / f"setlist_{timestamp}.{extension}"

    playlist_sections_data: List[Tuple[str, List[SongDisplay]]]
    first_track_url: Optional[str] = None
    if result.playlist:
        playlist_sections_data = result.playlist.sections
        first_track_url = result.playlist.first_track_url
    else:
        playlist_sections_data = [
            (segment.label, segment.tracks) for segment in result.segments
        ]
        if result.encore:
            playlist_sections_data.append((result.encore.label, result.encore.tracks))

    playlist_path: Optional[Path] = None
    if args.playlist and result.playlist and result.playlist.m3u_text:
        output_dir.mkdir(parents=True, exist_ok=True)
        playlist_path = output_dir / f"playlist_{timestamp}.m3u"
        playlist_path.write_text(result.playlist.m3u_text, encoding="utf-8")

    def render_html_output(path: Path, include_playlist: bool) -> None:
        playlist_file = playlist_path if include_playlist else None
        track_url = first_track_url if include_playlist else None

        sections = build_playlist_sections(
            result.segments,
            result.encore,
            include_audio_links=include_playlist,
        )
        render_html_report(
            output_path=path,
            generated=generated,
            generated_at=now_utc,
            playlist_path=playlist_file,
            first_track_url=track_url,
            playlist_sections=sections,
        )

    if args.playlist:
        render_markdown(output_path, generated, now_utc, sections=playlist_sections_data)
        html_output = output_path.with_suffix(".html")
        render_html_output(html_output, include_playlist=True)
    elif args.html:
        render_html_output(output_path, include_playlist=False)
    else:
        render_markdown(output_path, generated, now_utc, sections=playlist_sections_data)

    message = f"Wrote setlist to {output_path} (seed={result.seed})"
    if playlist_path:
        message += f"; playlist -> {playlist_path}"
    print(message)


if __name__ == "__main__":
    main()
