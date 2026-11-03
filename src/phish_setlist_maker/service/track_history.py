"""Database queries for historical track ordering."""

from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..models import Track


def query_following_tracks_from_show(
    session: Session, track_id: int, max_tracks: int = 5
) -> list[dict]:
    """Return tracks that followed ``track_id`` in the same show and set.

    Results preserve the historical order and contain ``track_id``, ``title``,
    and ``position``. This is a live database query; file-backed feature data
    belongs in :mod:`analysis.feature_store` instead.
    """
    source_track = session.query(Track).filter(Track.id == track_id).first()
    if source_track is None or max_tracks <= 0:
        return []

    following = (
        session.query(Track.id, Track.title, Track.position)
        .filter(
            and_(
                Track.show_id == source_track.show_id,
                Track.set == source_track.set,
                Track.position > source_track.position,
            )
        )
        .order_by(Track.position)
        .limit(max_tracks)
        .all()
    )
    return [
        {"track_id": track.id, "title": track.title, "position": track.position}
        for track in following
    ]
