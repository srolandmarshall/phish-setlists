"""Database loading and row normalization for historical segue artifacts."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def load_ordered_track_rows(session: Session) -> list[Any]:
    """Load tracks in show, set, and position order for chain formation."""
    query = text("""
        SELECT
            t.id as track_id,
            t.title as song,
            t.duration,
            t.likes_count,
            t.show_id,
            t."set" as set_label,
            t.position,
            s.date as show_date
        FROM tracks t
        JOIN shows s ON s.id = t.show_id
        ORDER BY t.show_id, t."set", t.position
    """)
    return session.execute(query).fetchall()


def load_adjacent_pair_rows(session: Session) -> list[Any]:
    """Load adjacent track-pair rows in the historical date order."""
    query = text("""
        SELECT
            s.id as show_id,
            s.date as show_date,
            t1.id as track1_id,
            t1.title as song1,
            t1.duration as duration1,
            t1.likes_count as likes1,
            t1."set" as set_label,
            t2.id as track2_id,
            t2.title as song2,
            t2.duration as duration2,
            t2.likes_count as likes2
        FROM tracks t1
        JOIN tracks t2 ON t2.show_id = t1.show_id
            AND t2."set" = t1."set"
            AND t2.position = t1.position + 1
        JOIN shows s ON s.id = t1.show_id
        ORDER BY s.date DESC
    """)
    return session.execute(query).fetchall()


