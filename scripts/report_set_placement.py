"""Summarise set placement statistics for historical shows."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from phish_setlist_maker.analysis.database import (
    build_song_set_frequencies,
    load_track_dataframe,
)
from phish_setlist_maker.db import session_scope


@dataclass
class SetPlacementSummary:
    canonical_set: str
    total_tracks: int
    distinct_songs: int
    representative_songs: List[Tuple[str, float, int]]


def compute_set_summaries(
    tracks: pd.DataFrame,
    *,
    allowed_sets: Iterable[str],
    min_appearances: int,
) -> Dict[str, SetPlacementSummary]:
    filtered_tracks = tracks[tracks["canonical_set"].isin(allowed_sets)]

    per_set_track_counts = (
        filtered_tracks.groupby("canonical_set")["track_id"].nunique().to_dict()
    )
    per_set_song_counts = (
        filtered_tracks.groupby("canonical_set")["song_effective_title"]
        .nunique()
        .to_dict()
    )

    freqs = build_song_set_frequencies(
        filtered_tracks,
        min_appearances=min_appearances,
        allowed_sets=allowed_sets,
    )

    summaries: Dict[str, SetPlacementSummary] = {}
    for canonical_set, total_tracks in per_set_track_counts.items():
        subset = freqs[freqs["canonical_set"] == canonical_set]
        top_songs = (
            subset.sort_values(["count", "probability"], ascending=[False, False])
            .head(10)[["song_effective_title", "probability", "count"]]
            .values.tolist()
        )
        summaries[canonical_set] = SetPlacementSummary(
            canonical_set=canonical_set,
            total_tracks=int(total_tracks),
            distinct_songs=int(per_set_song_counts.get(canonical_set, 0)),
            representative_songs=[
                (str(title), float(prob), int(count))
                for title, prob, count in top_songs
            ],
        )
    return summaries


def compute_set_span_distribution(freqs: pd.DataFrame) -> Dict[int, int]:
    counts = (
        freqs.groupby("song_effective_title")["canonical_set"]
        .nunique()
        .value_counts()
        .sort_index()
    )
    return {int(k): int(v) for k, v in counts.items()}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate summary statistics for song set placement."
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--min-appearances",
        type=int,
        default=5,
        help="Minimum number of appearances for a song to be considered representative (default: 5).",
    )
    args = parser.parse_args()

    with session_scope() as session:
        tracks = load_track_dataframe(session)
        allowed_sets = ("set1", "set2", "set3", "encore")
        freqs = build_song_set_frequencies(
            tracks,
            min_appearances=args.min_appearances,
            allowed_sets=allowed_sets,
        )

    set_summaries = compute_set_summaries(
        tracks,
        allowed_sets=allowed_sets,
        min_appearances=args.min_appearances,
    )
    span_distribution = compute_set_span_distribution(freqs)

    if args.format == "json":
        payload = {
            "set_summaries": {key: asdict(value) for key, value in set_summaries.items()},
            "span_distribution": span_distribution,
        }
        print(json.dumps(payload, indent=2))
        return

    print("=== Set Placement Overview ===")
    for label, summary in set_summaries.items():
        print(f"\n[{label}]")
        print(f"  total tracks   : {summary.total_tracks:,}")
        print(f"  distinct songs : {summary.distinct_songs:,}")
        print("  top songs:")
        for title, prob, count in summary.representative_songs:
            print(f"    - {title} (p={prob:.3f}, count={count})")

    print("\n=== Song distribution across sets ===")
    for unique_sets, song_count in span_distribution.items():
        print(f"  Songs appearing in {unique_sets} sets: {song_count}")


if __name__ == "__main__":
    main()
