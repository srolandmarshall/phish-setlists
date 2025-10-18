"""ORM model for Phish songs."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Song(Base):
    """Metadata for a song that can appear in setlists."""

    __tablename__ = "songs"
    repr_attrs = ("id", "title")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    tracks_count: Mapped[int] = mapped_column(Integer, default=0)
    original: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alias: Mapped[Optional[str]] = mapped_column(String)
    lyrics: Mapped[Optional[str]] = mapped_column(Text)
    artist: Mapped[Optional[str]] = mapped_column(String)

    track_links: Mapped[List["SongTrack"]] = relationship(
        "SongTrack", back_populates="song", cascade="all, delete-orphan"
    )
    tracks: Mapped[List["Track"]] = relationship(
        "Track",
        secondary="songs_tracks",
        back_populates="songs",
        viewonly=True,
    )

