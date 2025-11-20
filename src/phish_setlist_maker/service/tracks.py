"""Helpers for fetching track metadata from the local DB and phish.in."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timezone
from random import Random
from typing import Dict, List, Optional, Tuple

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


def query_tracks_for_song(
    db_session: Session,
    song_slug: str,
    limit: Optional[int] = None,
) -> List[CandidateTrack]:
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
    )
    if limit is not None and limit > 0:
        stmt = stmt.limit(limit)
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
    limit: Optional[int] = None,
) -> List[CandidateTrack]:
    """
    Query tracks for a song that were performed as set closers using prebuilt lookup.
    
    Set 2 and Encore share tracks bidirectionally (both are show closers).
    
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
    
    # For encores and Set 2, share tracks (they're both closers)
    if canonical_set == "encore":
        filtered = df[
            (df["song_slug"] == song_slug) &
            ((df["canonical_set"] == "encore") | (df["canonical_set"] == "set2"))
        ].sort_values("likes_count", ascending=False)
    elif canonical_set == "set2":
        filtered = df[
            (df["song_slug"] == song_slug) &
            ((df["canonical_set"] == "set2") | (df["canonical_set"] == "encore"))
        ].sort_values("likes_count", ascending=False)
    else:
        # For Set 1 and Set 3, only use tracks from that specific set
        filtered = df[
            (df["song_slug"] == song_slug) &
            (df["canonical_set"] == canonical_set)
        ].sort_values("likes_count", ascending=False)

    if limit is not None and limit > 0:
        filtered = filtered.head(limit)
    
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


def _cached_metadata_valid(cache: dict, ttl_hours: int = 24) -> bool:
    """Check if cached metadata is valid. Uses TTL instead of HEAD requests for performance."""
    url = cache.get("mp3_url")
    if not url:
        return False

    # Check cache age - trust cached data for ttl_hours without making HTTP requests
    fetched_at_str = cache.get("fetched_at")
    if fetched_at_str:
        try:
            fetched_at = datetime.fromisoformat(fetched_at_str)
            age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
            if age_hours < ttl_hours:
                # Cache is fresh, trust it without validation
                return True
        except (ValueError, TypeError):
            pass  # Fall through to validation if timestamp is invalid

    # Cache is old or missing timestamp - validate with HEAD request
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
    try:
        session.execute(
            update(Track)
            .where(Track.id == track_id)
            .values(metadata_cache=values)
        )
        session.flush()
    except Exception:
        # Skip cache update if database schema doesn't match
        # (e.g., missing metadata_cache column or other schema issues)
        pass


def batch_prefetch_track_metadata(
    session: Session,
    candidates: List[Tuple[CandidateTrack, str]],
    *,
    max_workers: int = 5,
    delay_between_requests: float = 0.2,
) -> None:
    """
    Prefetch metadata for multiple tracks in parallel with rate limiting.

    Args:
        session: Database session for cache updates
        candidates: List of (CandidateTrack, song_slug) tuples
        max_workers: Max concurrent requests (default 5 to be nice to phish.in)
        delay_between_requests: Seconds to wait between requests (default 0.2s = 5 req/sec)
    """
    # Filter to only uncached tracks
    to_fetch = []
    for candidate, song_slug in candidates:
        cache = candidate.metadata_cache or {}
        if not cache or not _cached_metadata_valid(cache):
            to_fetch.append((candidate, song_slug))

    if not to_fetch:
        logger.info("All %d tracks already cached, skipping prefetch", len(candidates))
        return

    logger.info("Prefetching metadata for %d uncached tracks (parallel, rate-limited)", len(to_fetch))
    start_time = time.time()

    def fetch_one(candidate: CandidateTrack, slug: str) -> Tuple[CandidateTrack, Optional[str], Optional[int], Optional[str]]:
        """Fetch metadata for a single track with rate limiting."""
        time.sleep(delay_between_requests)  # Rate limit: wait before each request
        try:
            mp3_url, duration, show_date = fetch_remote_track_metadata(
                track_id=candidate.track_id,
                song_slug=slug,
                rng=Random(),  # Not used for selection here
                strict=False,
            )
            return candidate, mp3_url, duration, show_date
        except Exception as e:
            logger.warning("Failed to fetch metadata for track_id=%s: %s", candidate.track_id, e)
            return candidate, None, None, None

    # Fetch in parallel with limited concurrency
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_one, candidate, slug): (candidate, slug)
            for candidate, slug in to_fetch
        }

        fetched_count = 0
        for future in as_completed(futures):
            candidate, mp3_url, duration, show_date = future.result()
            if mp3_url:
                _update_track_cache(
                    session,
                    candidate.track_id,
                    mp3_url=mp3_url,
                    duration=duration,
                    show_date=show_date,
                )
                fetched_count += 1

    elapsed = time.time() - start_time
    logger.info(
        "Prefetched %d/%d tracks in %.2fs (avg %.2fs/track)",
        fetched_count,
        len(to_fetch),
        elapsed,
        elapsed / len(to_fetch) if to_fetch else 0,
    )


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
