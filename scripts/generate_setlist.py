#!/usr/bin/env python3
"""CLI helper to generate a Phish setlist and emit a Markdown report."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
from random import Random
from typing import Dict, Optional
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from phish_setlist_maker.db import session_scope  # noqa: E402
from phish_setlist_maker.generator import (  # noqa: E402
    SetlistGenerator,
    random_set_lengths,
)


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
        default="4.0",
        help="Restrict history to a specific era (default: 4.0).",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Only consider shows through the end of this calendar year.",
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
        help="Seed for deterministic generation.",
    )
    parser.add_argument(
        "--allow-previous-show",
        action="store_true",
        help="Allow songs from the previous show to be eligible (default excludes them).",
    )
    parser.add_argument(
        "--set-length",
        action="append",
        default=[],
        metavar="SET=COUNT",
        help="Override a set length (e.g., --set-length set1=11). Repeat as needed.",
    )
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


def render_markdown(output_path: Path, generated, generated_at: datetime) -> None:
    lines = ["# Generated Setlist", ""]

    metadata = generated.metadata
    lines.append("## Context")
    lines.append(format_metadata_line("Generated at", generated_at.isoformat(timespec="seconds")))
    lines.append(format_metadata_line("Reference date", str(metadata.reference_date)))
    lines.append(format_metadata_line("Cutoff date", str(metadata.cutoff_date)))
    lines.append(format_metadata_line("Era", metadata.era or "All history"))
    lines.append(format_metadata_line("Year limit", str(metadata.year) if metadata.year else "Full run"))
    lines.append("")

    for segment in generated.sets:
        lines.append(f"## {segment.label}")
        for idx, song in enumerate(segment.songs, start=1):
            lines.append(f"{idx}. {song}")
        lines.append("")

    if generated.encore:
        lines.append("## Encore")
        for idx, song in enumerate(generated.encore.songs, start=1):
            lines.append(f"{idx}. {song}")
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

    rng = Random(args.seed) if args.seed is not None else None
    length_rng: Optional[Random] = Random(args.seed) if args.seed is not None else None

    with session_scope() as session:
        generator = SetlistGenerator(session, rng=rng)

        set_lengths = dict(set_length_overrides)
        if not set_lengths:
            set_lengths = random_set_lengths(
                session,
                reference_date=args.reference_date,
                era=args.era,
                year=args.year,
                num_sets=args.num_sets,
                include_encore=args.include_encore,
                rng=length_rng,
            )

        generated = generator.generate(
            reference_date=args.reference_date,
            era=args.era,
            year=args.year,
            num_sets=args.num_sets,
            include_encore=args.include_encore,
            set_lengths=set_lengths,
            exclude_previous_show=not args.allow_previous_show,
        )

    now_utc = datetime.now(timezone.utc)
    timestamp = now_utc.strftime("%Y%m%d_%H%M%S")
    output_dir = PROJECT_ROOT / "data"
    output_path = output_dir / f"setlist_{timestamp}.md"

    render_markdown(output_path, generated, now_utc)
    print(f"Wrote setlist to {output_path}")


if __name__ == "__main__":
    main()
