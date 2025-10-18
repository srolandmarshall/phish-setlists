"""Shared SQLAlchemy base class configuration."""

from __future__ import annotations

from typing import Any, ClassVar, Iterable

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Project-wide declarative base with a helpful ``repr`` implementation."""

    repr_attrs: ClassVar[Iterable[str]] = ()

    def __repr__(self) -> str:
        attrs: Iterable[str]
        if self.repr_attrs:
            attrs = (f"{name}={getattr(self, name)!r}" for name in self.repr_attrs)
        else:
            # Fallback to identity when no explicit attributes are provided.
            attrs = (f"id={getattr(self, 'id', None)!r}",)
        joined = ", ".join(attrs)
        return f"<{self.__class__.__name__} {joined}>"

