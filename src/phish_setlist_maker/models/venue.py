"""ORM model describing show venues."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Venue(Base):
    """Physical location where shows take place."""

    __tablename__ = "venues"
    repr_attrs = ("id", "name", "city", "state")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    shows_count: Mapped[int] = mapped_column(Integer, default=0)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    abbrev: Mapped[Optional[str]] = mapped_column(String(255))

    shows: Mapped[List["Show"]] = relationship("Show", back_populates="venue")

