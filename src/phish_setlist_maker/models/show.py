"""ORM model for Phish shows."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Show(Base):
    """Represents a single Phish performance date."""

    __tablename__ = "shows"
    repr_attrs = ("id", "date")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    venue_id: Mapped[Optional[int]] = mapped_column(ForeignKey("venues.id"), nullable=True)
    tour_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tours.id"), nullable=True)
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text)
    duration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    taper_notes: Mapped[Optional[str]] = mapped_column(Text)
    tags_count: Mapped[int] = mapped_column(Integer, default=0)
    venue_name: Mapped[str] = mapped_column(String, default="", nullable=False)
    matches_pnet: Mapped[bool] = mapped_column(Boolean, default=False)
    cover_art_style: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cover_art_hue: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cover_art_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_art_parent_show_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    album_zip_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    performance_gap_value: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    audio_status: Mapped[str] = mapped_column(String, default="complete", nullable=False)

    venue: Mapped[Optional["Venue"]] = relationship("Venue", back_populates="shows")
    tour: Mapped[Optional["Tour"]] = relationship("Tour", back_populates="shows")
    tracks: Mapped[List["Track"]] = relationship(
        "Track",
        back_populates="show",
        order_by="Track.position",
        cascade="all, delete-orphan",
    )
