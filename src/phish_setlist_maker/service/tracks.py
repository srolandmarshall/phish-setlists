"""Helpers for fetching track metadata from the local DB and phish.in."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from random import Random
from typing import List, Optional, Tuple

import requests
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Show, Song, SongTrack, Track
from .errors import PlaylistServiceError

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class CandidateTrack:
    track_id: int
    slug: Optional[str]
    duration: Optional[int]
    show_date: Optional[date]
    likes_count: int
    metadata_cache: Optional[dict] = None


def query_tracks_for_song(db_session: Session, song_slug: str, limit: int = 25) -> List[CandidateTrack]:
    stmt = (
        select(
            Track.id,
            Track.slug,
            Track.duration,
            Track.likes_count,
            Show.date.label("show_date"),
            Track.metadata_cache,
        )
        .join(SongTrack, SongTrack.track_id == Track.id)
        .join(Song, SongTrack.song_id == Song.id)
        .outerjoin(Show, Show.id == Track.show_id)
        .where(Song.slug == song_slug)
        .order_by(Track.likes_count.desc(), Track.id.desc())
        .limit(limit)
    )
    rows = db_session.execute(stmt).all()
    return [
        CandidateTrack(
            track_id=row.id,
            slug=row.slug,
            duration=row.duration,
            show_date=row.show_date,
            likes_count=row.likes_count or 0,
            metadata_cache=row.metadata_cache,
        )
        for row in rows
        if row.id is not None
    ]


def query_set_ending_tracks_for_song(
    db_session: Session,
    song_slug: str,
    canonical_set: str,
    limit: int = 25
) -> List[CandidateTrack]:
    """
    Query tracks for a song that were performed as set closers using prebuilt lookup.
    
    Args:
        db_session: Database session
        song_slug: Slug of the song to query
        canonical_set: Canonical set label (set1, set2, set3, encore)
        limit: Maximum number of tracks to return
    
    Returns:
        List of CandidateTrack objects for performances that ended the specified set
    """
    import pandas as pd
    from pathlib import Path
    
    # Load set-ending tracks lookup
    lookup_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "analytics" / "features" / "set_ending_tracks.parquet"
    
    if not lookup_path.exists():
        # Fall back to regular tracks if lookup doesn't exist
        return []
    
    df = pd.read_parquet(lookup_path)
    
    # Filter by song_slug and canonical_set
    filtered = df[
        (df["song_slug"] == song_slug) &
        (df["canonical_set"] == canonical_set)
    ].sort_values("likes_count", ascending=False).head(limit)
    
    if len(filtered) == 0:
        return []
    
    # Convert to CandidateTrack objects
    candidates = []
    for _, row in filtered.iterrows():
        candidates.append(
            CandidateTrack(
                track_id=int(row["track_id"]),
                slug=row["track_slug"],
                duration=int(row["duration"]) if pd.notna(row["duration"]) else None,
                show_date=row["show_date"].date() if pd.notna(row["show_date"]) else None,
                likes_count=int(row["likes_count"]),
                metadata_cache=None,  # Not stored in lookup
            )
        )
    
    return candidates


def fetch_remote_track_metadata(
    *,
    track_id: Optional[int],
    song_slug: str,
    rng: Random,
    strict: bool,
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    last_error: Optional[Exception] = None

    if track_id is not None:
        logger.info(
            "phish.in request endpoint=%s url=%s track_id=%s",
            "tracks/{id}",
            f"https://phish.in/api/v2/tracks/{track_id}.json",
            track_id,
        )
        url = f"https://phish.in/api/v2/tracks/{track_id}.json"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "track" in data:
                data = data.get("track", {})
            mp3_url = data.get("mp3_url") or data.get("mp3")
            duration_raw = data.get("duration")
            duration_seconds = int(duration_raw // 1000) if isinstance(duration_raw, (int, float)) else None
            show_date = data.get("show_date")
            if mp3_url:
                logger.info(
                    "phish.in response endpoint=tracks/{id} status=%s mp3=%s",
                    resp.status_code,
                    bool(mp3_url),
                )
                return mp3_url, duration_seconds, show_date
            else:
                logger.warning(
                    "phish.in response missing mp3_url endpoint=tracks/{id} status=%s track_id=%s",
                    resp.status_code,
                    track_id,
                )
        except requests.RequestException as exc:
            last_error = exc

    params = {
        "song_slug": song_slug,
        "per_page": 30,
        "sort": "likes_count:desc",
        "audio_status": "complete_or_partial",
    }
    logger.info(
        "phish.in request endpoint=%s url=%s params=%s",
        "tracks",
        "https://phish.in/api/v2/tracks.json",
        params,
    )
    try:
        resp = requests.get("https://phish.in/api/v2/tracks.json", params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        if strict and last_error is None:
            raise PlaylistServiceError(f"Unable to fetch track metadata for song '{song_slug}'.") from exc
        return None, None, None

    tracks = resp.json().get("tracks", [])
    candidates = [track for track in tracks if track.get("mp3_url")]
    logger.info(
        "phish.in response endpoint=tracks status=%s candidates=%s",
        resp.status_code,
        len(candidates),
    )
    if not candidates:
        if strict and last_error is not None:
            raise PlaylistServiceError(f"Unable to fetch track metadata for track id '{track_id}'.") from last_error
        return None, None, None

    selection = rng.choice(candidates)
    mp3_url = selection.get("mp3_url")
    duration_raw = selection.get("duration")
    duration_seconds = int(duration_raw // 1000) if isinstance(duration_raw, (int, float)) else None
    show_date = selection.get("show_date")
    return mp3_url, duration_seconds, show_date


def _cached_metadata_valid(cache: dict) -> bool:
    url = cache.get("mp3_url")
    if not url:
        return False
    try:
        head_resp = requests.head(url, timeout=5, allow_redirects=True)
        if head_resp.status_code >= 400:
            return False
    except requests.RequestException:
        return False
    return True


def _update_track_cache(
    session: Session,
    track_id: int,
    *,
    mp3_url: Optional[str],
    duration: Optional[int],
    show_date: Optional[str],
) -> None:
    values = {
        "mp3_url": mp3_url,
        "duration": duration,
        "show_date": show_date,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    session.execute(
        update(Track)
        .where(Track.id == track_id)
        .values(metadata_cache=values)
    )
    session.flush()


def resolve_track_metadata(
    session: Session,
    candidate: CandidateTrack,
    *,
    song_slug: str,
    rng: Random,
    strict: bool,
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    cache = candidate.metadata_cache or {}
    if cache and _cached_metadata_valid(cache):
        return (
            cache.get("mp3_url"),
            cache.get("duration"),
            cache.get("show_date"),
        )

    mp3_url, duration, show_date = fetch_remote_track_metadata(
        track_id=candidate.track_id,
        song_slug=song_slug,
        rng=rng,
        strict=strict,
    )

    if mp3_url:
        _update_track_cache(
            session,
            candidate.track_id,
            mp3_url=mp3_url,
            duration=duration,
            show_date=show_date,
        )

    return mp3_url, duration, show_date
