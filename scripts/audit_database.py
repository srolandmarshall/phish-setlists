"""Quick database audit for analytics groundwork.

This script prints a handful of coverage metrics that help validate the
historical archives before running ML notebooks. It relies on the standard
database settings defined in ``phish_setlist_maker.config``.
"""

from __future__ import annotations

import argparse
import sys
from typing import Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from phish_setlist_maker.db import session_scope
from phish_setlist_maker.models import Show, Song, SongTrack, Track


def _format_date_range(result: Tuple) -> str:
    start, end = result
    if start is None or end is None:
        return "unknown → unknown"
    return f"{start.isoformat()} → {end.isoformat()}"


def run_audit() -> int:
    try:
        with session_scope() as session:
            show_count = session.execute(select(func.count(Show.id))).scalar_one()
            date_bounds = session.execute(
                select(func.min(Show.date), func.max(Show.date))
            ).one()

            track_count = session.execute(select(func.count(Track.id))).scalar_one()
            zero_duration = session.execute(
                select(func.count()).where((Track.duration == 0) | (Track.duration.is_(None)))
            ).scalar_one()
            missing_set = session.execute(
                select(func.count()).where((Track.set == "") | (Track.set.is_(None)))
            ).scalar_one()

            song_count = session.execute(select(func.count(Song.id))).scalar_one()
            songs_with_alias = session.execute(
                select(func.count()).where(Song.alias.is_not(None))
            ).scalar_one()

            linking_rows = session.execute(
                select(func.count(SongTrack.id))
            ).scalar_one()

    except SQLAlchemyError as exc:
        print("Database audit failed:", exc, file=sys.stderr)
        return 1

    print("=== Show Coverage ===")
    print(f"Total shows      : {show_count:,}")
    print(f"Date range       : {_format_date_range(date_bounds)}")
    print()

    print("=== Track Coverage ===")
    print(f"Total tracks             : {track_count:,}")
    print(f"Tracks w/ zero duration  : {zero_duration:,}")
    print(f"Tracks missing set label : {missing_set:,}")
    if track_count:
        pct_zero = zero_duration / track_count * 100
        pct_missing = missing_set / track_count * 100
        print(f" - zero duration pct     : {pct_zero:.2f}%")
        print(f" - missing set pct       : {pct_missing:.2f}%")
    print()

    print("=== Songs & Links ===")
    print(f"Total songs        : {song_count:,}")
    print(f"Songs with alias   : {songs_with_alias:,}")
    if song_count:
        print(f" - alias coverage  : {songs_with_alias / song_count * 100:.2f}%")
    print(f"Song↔Track links   : {linking_rows:,}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the Phish setlist database.")
    parser.parse_args()
    raise SystemExit(run_audit())


if __name__ == "__main__":
    main()
