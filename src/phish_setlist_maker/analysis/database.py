"""Data extraction utilities for analytics workflows."""

from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from ..constants import ERA_DEFINITIONS
from ..generator.historical import normalize_set_label
from ..models import Show, Song, SongTrack, Tour, Track, Venue


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
def load_venue_dataframe(session: Session) -> pd.DataFrame:
    """Return venue metadata with show counts."""
    stmt = select(
        Venue.id.label("venue_id"),
        Venue.name.label("venue_name"),
        Venue.city,
        Venue.state,
        Venue.country,
        Venue.slug.label("venue_slug"),
        Venue.latitude,
        Venue.longitude,
        Venue.shows_count,
    )
    return _execute_dataframe(session, stmt)


def load_tour_dataframe(session: Session) -> pd.DataFrame:
    """Return tour metadata with date ranges."""
    stmt = select(
        Tour.id.label("tour_id"),
        Tour.name.label("tour_name"),
        Tour.starts_on,
        Tour.ends_on,
        Tour.slug.label("tour_slug"),
        Tour.shows_count,
    )
    frame = _execute_dataframe(session, stmt)
    if not frame.empty:
        frame["starts_on"] = pd.to_datetime(frame["starts_on"])
        frame["ends_on"] = pd.to_datetime(frame["ends_on"])
        frame["duration_days"] = (frame["ends_on"] - frame["starts_on"]).dt.days
    return frame


def build_venue_tendencies(tracks_df: pd.DataFrame, shows_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate venue-level statistics from tracks + shows."""
    if tracks_df.empty or shows_df.empty:
        return pd.DataFrame(
            columns=["venue_id", "show_count", "track_count", "avg_show_duration", "top_songs"]
        )
    
    merged = tracks_df.merge(shows_df[["show_id", "venue_id"]], on="show_id", how="left")
    merged = merged.dropna(subset=["venue_id"])
    
    venue_stats = (
        merged.groupby("venue_id")
        .agg(
            show_count=("show_id", "nunique"),
            track_count=("track_id", "count"),
            total_duration=("duration_seconds", "sum"),
        )
        .reset_index()
    )
    
    venue_stats["avg_show_duration"] = venue_stats["total_duration"] / venue_stats["show_count"]
    
    top_songs = (
        merged.groupby(["venue_id", "song_effective_title"])
        .size()
        .reset_index(name="play_count")
        .sort_values(["venue_id", "play_count"], ascending=[True, False])
        .groupby("venue_id")
        .head(5)
        .groupby("venue_id")["song_effective_title"]
        .apply(list)
        .reset_index(name="top_songs")
    )
    
    return venue_stats.merge(top_songs, on="venue_id", how="left").drop(columns=["total_duration"])


def build_set_ending_frequencies(
    frame: pd.DataFrame,
    *,
    allowed_sets: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Compute set-ending song probabilities from track data.
    
    Identifies the last song in each set and calculates how often
    each song appears as a set closer for each canonical set.
    
    Args:
        frame: Track dataframe with show_id, canonical_set, position, song_effective_title
        allowed_sets: Optional filter for specific sets (e.g., ['set1', 'set2'])
    
    Returns:
        DataFrame with columns: song_effective_title, canonical_set, ending_count, total_count, ending_probability
    """
    if frame.empty:
        return pd.DataFrame(
            columns=["song_effective_title", "canonical_set", "ending_count", "total_count", "ending_probability"]
        )
    
    # Filter to allowed sets if specified
    filtered = frame.dropna(subset=["canonical_set", "song_effective_title"])
    if allowed_sets is not None:
        filtered = filtered[filtered["canonical_set"].isin(allowed_sets)]
    
    # Identify set-ending songs (last position in each set)
    set_endings = (
        filtered.sort_values("position")
        .groupby(["show_id", "canonical_set"])
        .tail(1)[["show_id", "canonical_set", "song_effective_title"]]
    )
    
    # Count how often each song ends each set type
    ending_counts = (
        set_endings.groupby(["song_effective_title", "canonical_set"])
        .size()
        .reset_index(name="ending_count")
    )
    
    # Count total appearances of each song in each set (for probability calculation)
    total_counts = (
        filtered.groupby(["song_effective_title", "canonical_set"])
        .size()
        .reset_index(name="total_count")
    )
    
    # Merge and calculate probability
    result = ending_counts.merge(
        total_counts,
        on=["song_effective_title", "canonical_set"],
        how="left"
    )
    result["ending_probability"] = result["ending_count"] / result["total_count"]
    
    return result.sort_values(["canonical_set", "ending_count"], ascending=[True, False])


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
