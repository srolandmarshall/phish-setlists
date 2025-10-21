"""FastAPI dependencies for database sessions."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from ..db import get_session_factory


def get_session() -> Iterable[Session]:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
