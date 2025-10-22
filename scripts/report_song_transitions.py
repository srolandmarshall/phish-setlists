"""Report high-confidence song transitions per set."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from phish_setlist_maker.analysis.database import (
    build_song_transitions,
    load_track_dataframe,
)
from phish_setlist_maker.db import session_scope


@dataclass
class TransitionSummary:
    canonical_set: str
    transitions: List[Tuple[str, str, int]]


def summarise_transitions(
    tracks: pd.DataFrame,
    *,
    allowed_sets: Iterable[str],
    min_count: int,
    top_n: int,
) -> Dict[str, TransitionSummary]:
    filtered_tracks = tracks[tracks["canonical_set"].isin(allowed_sets)]

    transitions = build_song_transitions(filtered_tracks, min_count=min_count)

    summaries: Dict[str, TransitionSummary] = {}
    for canonical_set in allowed_sets:
        subset = transitions[transitions["canonical_set"] == canonical_set]
        top_rows = subset.sort_values("count", ascending=False).head(top_n)
        payload = [
            (str(row["from_title"]), str(row["to_title"]), int(row["count"]))
            for _, row in top_rows.iterrows()
        ]
        summaries[canonical_set] = TransitionSummary(
            canonical_set=canonical_set,
            transitions=payload,
        )
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Report frequent song transitions.")
    parser.add_argument(
        "--min-count",
        type=int,
        default=10,
        help="Minimum number of historical appearances for a transition (default: 10).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=15,
        help="Number of transitions to show per set (default: 15).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    args = parser.parse_args()

    allowed_sets = ("set1", "set2", "set3", "encore")

    with session_scope() as session:
        tracks = load_track_dataframe(session)

    summaries = summarise_transitions(
        tracks,
        allowed_sets=allowed_sets,
        min_count=args.min_count,
        top_n=args.top,
    )

    if args.format == "json":
        payload = {key: asdict(value) for key, value in summaries.items()}
        print(json.dumps(payload, indent=2))
        return

    print("=== Frequent Song Transitions ===")
    for label in allowed_sets:
        summary = summaries[label]
        print(f"\n[{label}]")
        if not summary.transitions:
            print("  <no transitions meeting the threshold>")
            continue
        for from_title, to_title, count in summary.transitions:
            print(f"  {from_title} → {to_title} ({count} shows)")


if __name__ == "__main__":
    main()
