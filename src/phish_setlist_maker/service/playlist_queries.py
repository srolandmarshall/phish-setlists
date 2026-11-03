"""Bounded database reads used during playlist artifact assembly."""

from __future__ import annotations

from typing import Dict, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Song, SongTrack, Track


def _load_track_song_metadata(db_session: Session, track_ids: Sequence[int]) -> Dict[int, object]:
    """Load continuation performance and song metadata in one bounded query."""
    unique_ids = list(dict.fromkeys(track_ids))
    if not unique_ids:
        return {}

    statement = (
        select(
            Track.id.label("track_id"),
            Track.slug.label("track_slug"),
            Track.duration,
            Track.likes_count,
            Track.metadata_cache,
            Song.id.label("song_id"),
            Song.title.label("song_title"),
            Song.slug.label("song_slug"),
        )
        .outerjoin(SongTrack, SongTrack.track_id == Track.id)
        .outerjoin(Song, Song.id == SongTrack.song_id)
        .where(Track.id.in_(unique_ids))
    )
    rows = db_session.execute(statement).all()
    # The old path selected the first SongTrack/Song row for a performance.
    # Keep that behavior if a performance has multiple song links.
    metadata = {}
    for row in rows:
        metadata.setdefault(row.track_id, row)
    return metadata


def _load_song_duration_stats(db_session: Session, song_slugs: Sequence[str]) -> Dict[str, object]:
    """Load average duration and likes for all songs used in compensation."""
    unique_slugs = list(dict.fromkeys(song_slugs))
    if not unique_slugs:
        return {}

    statement = (
        select(
            Song.slug.label("song_slug"),
            func.avg(Track.duration).label("avg_duration"),
            func.avg(Track.likes_count).label("avg_likes"),
        )
        .join(SongTrack, SongTrack.song_id == Song.id)
        .join(Track, Track.id == SongTrack.track_id)
        .where(Song.slug.in_(unique_slugs))
        .group_by(Song.slug)
    )
    return {row.song_slug: row for row in db_session.execute(statement).all()}


