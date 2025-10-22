"""Data extraction utilities for analytics workflows."""

from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from ..constants import ERA_DEFINITIONS
from ..generator.historical import normalize_set_label
from ..models import Show, Song, SongTrack, Track


def _execute_dataframe(session: Session, stmt: Select) -> pd.DataFrame:
    result = session.execute(stmt)
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame(columns=result.keys())
    return pd.DataFrame(rows, columns=result.keys())


def load_show_dataframe(session: Session) -> pd.DataFrame:
    """Return high-level show metadata."""

    stmt = select(
        Show.id.label("show_id"),
        Show.date.label("show_date"),
        Show.venue_id,
        Show.tour_id,
        Show.duration.label("duration_ms"),
        Show.likes_count,
        Show.tags_count,
        Show.audio_status,
        Show.performance_gap_value,
    )
    frame = _execute_dataframe(session, stmt)

    if frame.empty:
        return frame

    frame["show_date"] = pd.to_datetime(frame["show_date"])
    frame["era"] = frame["show_date"].apply(_infer_era)
    frame["year"] = frame["show_date"].dt.year
    frame["duration_seconds"] = (frame["duration_ms"].fillna(0) / 1000.0).astype(float)
    return frame


def load_song_dataframe(session: Session) -> pd.DataFrame:
    """Return song metadata suitable for feature generation."""

    stmt = select(
        Song.id.label("song_id"),
        Song.title,
        Song.slug,
        Song.artist,
        Song.alias,
        Song.original,
        Song.tracks_count,
    )
    return _execute_dataframe(session, stmt)


def load_track_dataframe(session: Session) -> pd.DataFrame:
    """Return track-level details with show and song context."""

    stmt = (
        select(
            Track.id.label("track_id"),
            Track.show_id,
            Show.date.label("show_date"),
            Track.set.label("set_label"),
            Track.position,
            Track.title.label("track_title"),
            Track.duration.label("duration_ms"),
            Track.likes_count,
            Song.id.label("song_id"),
            Song.title.label("song_title"),
            Song.slug.label("song_slug"),
        )
        .join(Show, Track.show_id == Show.id)
        .join(SongTrack, SongTrack.track_id == Track.id, isouter=True)
        .join(Song, Song.id == SongTrack.song_id, isouter=True)
        .order_by(Show.date, Track.position)
    )

    frame = _execute_dataframe(session, stmt)
    if frame.empty:
        return frame

    frame["show_date"] = pd.to_datetime(frame["show_date"])
    frame["canonical_set"] = frame["set_label"].map(_canonical_for_analysis)
    frame["song_effective_title"] = frame["song_title"].fillna(frame["track_title"])
    frame["duration_seconds"] = (frame["duration_ms"].fillna(0) / 1000.0).astype(float)
    frame["era"] = frame["show_date"].apply(_infer_era)
    frame["year"] = frame["show_date"].dt.year
    return frame


def build_set_segments(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-set summaries from a track dataframe."""

    if frame.empty:
        return pd.DataFrame(
            columns=[
                "show_id",
                "show_date",
                "canonical_set",
                "track_count",
                "duration_seconds",
                "song_titles",
            ]
        )

    sorted_frame = frame.sort_values(["show_id", "canonical_set", "position"])
    sorted_frame = sorted_frame.dropna(subset=["canonical_set"])

    def _collect(group: pd.DataFrame) -> pd.Series:
        titles = group["song_effective_title"].tolist()
        duration = float(group["duration_seconds"].sum())
        return pd.Series(
            {
                "show_date": group["show_date"].iloc[0],
                "canonical_set": group["canonical_set"].iloc[0],
                "track_count": int(group["track_id"].nunique()),
                "duration_seconds": duration,
                "song_titles": titles,
            }
        )

    segments = (
        sorted_frame.groupby(["show_id", "canonical_set"], as_index=False)
        .apply(_collect)
        .reset_index(drop=True)
    )
    return segments


def build_song_transitions(
    frame: pd.DataFrame,
    *,
    min_count: int = 1,
) -> pd.DataFrame:
    """Compute consecutive song transition counts within sets."""

    if frame.empty:
        return pd.DataFrame(
            columns=["from_title", "to_title", "canonical_set", "count"]
        )

    sorted_frame = frame.sort_values(["show_id", "canonical_set", "position"])
    sorted_frame = sorted_frame.dropna(subset=["canonical_set"])
    sorted_frame["next_song"] = sorted_frame.groupby(["show_id", "canonical_set"])[
        "song_effective_title"
    ].shift(-1)

    transitions = sorted_frame.dropna(subset=["next_song"])

    grouped = (
        transitions.groupby(
            ["song_effective_title", "next_song", "canonical_set"], as_index=False
        )
        .agg(count=("track_id", "count"))
        .rename(
            columns={
                "song_effective_title": "from_title",
                "next_song": "to_title",
            }
        )
    )

    if min_count > 1:
        grouped = grouped[grouped["count"] >= min_count].reset_index(drop=True)

    return grouped


def build_song_set_frequencies(
    frame: pd.DataFrame,
    *,
    min_appearances: int = 1,
    allowed_sets: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Compute per-set appearance probabilities for each song."""

    if frame.empty:
        return pd.DataFrame(
            columns=["song_effective_title", "canonical_set", "count", "probability"]
        )

    filtered = frame.dropna(subset=["canonical_set"])

    if allowed_sets is not None:
        filtered = filtered[filtered["canonical_set"].isin(allowed_sets)]

    counts = (
        filtered.groupby(["song_effective_title", "canonical_set"])
        .agg(count=("track_id", "nunique"))
        .reset_index()
    )
    totals = counts.groupby("song_effective_title")["count"].transform("sum")
    counts["probability"] = counts["count"] / totals

    if min_appearances > 1:
        counts = counts[counts["count"] >= min_appearances].reset_index(drop=True)

    return counts


def _infer_era(show_date: Optional[pd.Timestamp]) -> Optional[str]:
    if pd.isna(show_date):
        return None
    for label, definition in ERA_DEFINITIONS.items():
        if definition.contains(show_date.date()):
            return label
    return None
def _canonical_for_analysis(label: Optional[str]) -> Optional[str]:
    if not label:
        return None
    normalized = normalize_set_label(label)
    if not normalized:
        return None
    if normalized.startswith("set"):
        return normalized
    if normalized.startswith("encore") or normalized.startswith("e"):
        return "encore"
    return None
