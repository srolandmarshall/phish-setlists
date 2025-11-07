"""ORM model for individual track appearances within a show."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship, deferred

from .base import Base


class Track(Base):
    """Represents a single track (song performance) within a show."""

    __tablename__ = "tracks"
    repr_attrs = ("id", "title", "set", "position")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    show_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shows.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column("position", Integer, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    set: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    tags_count: Mapped[int] = mapped_column(Integer, default=0)
    jam_starts_at_second: Mapped[Optional[int]] = mapped_column(Integer)
    audio_file_data: Mapped[Optional[str]] = mapped_column(Text, deferred=True, nullable=True)
    waveform_png_data: Mapped[Optional[str]] = mapped_column(Text, deferred=True, nullable=True)
    metadata_cache: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    show: Mapped[Optional["Show"]] = relationship("Show", back_populates="tracks")
    song_links: Mapped[List["SongTrack"]] = relationship(
        "SongTrack", back_populates="track", cascade="all, delete-orphan"
    )
    songs: Mapped[List["Song"]] = relationship(
        "Song",
        secondary="songs_tracks",
        back_populates="tracks",
        viewonly=True,
    )
