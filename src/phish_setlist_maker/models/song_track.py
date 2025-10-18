"""Association table between songs and track performances."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class SongTrack(Base):
    """Join model linking songs to their track performances with gap metadata."""

    __tablename__ = "songs_tracks"
    repr_attrs = ("id", "song_id", "track_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), nullable=False)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), nullable=False)
    previous_performance_gap: Mapped[Optional[int]] = mapped_column(Integer)
    previous_performance_slug: Mapped[Optional[str]] = mapped_column(String)
    next_performance_gap: Mapped[Optional[int]] = mapped_column(Integer)
    next_performance_slug: Mapped[Optional[str]] = mapped_column(String)

    song: Mapped["Song"] = relationship("Song", back_populates="track_links")
    track: Mapped["Track"] = relationship("Track", back_populates="song_links")

