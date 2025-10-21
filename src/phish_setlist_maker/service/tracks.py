"""Helpers for fetching track metadata from the local DB and phish.in."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from random import Random
from typing import List, Optional, Tuple

import requests
from sqlalchemy import select
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


def query_tracks_for_song(db_session: Session, song_slug: str, limit: int = 25) -> List[CandidateTrack]:
    stmt = (
        select(
            Track.id,
            Track.slug,
            Track.duration,
            Track.likes_count,
            Show.date.label("show_date"),
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
        )
        for row in rows
        if row.id is not None
    ]


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
