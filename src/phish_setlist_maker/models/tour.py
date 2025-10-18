"""ORM model for Phish tour metadata."""

from __future__ import annotations

from datetime import date
from typing import List

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Tour(Base):
    """Grouping of shows sharing a tour run."""

    __tablename__ = "tours"
    repr_attrs = ("id", "name")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    shows_count: Mapped[int] = mapped_column(Integer, default=0)

    shows: Mapped[List["Show"]] = relationship("Show", back_populates="tour")

