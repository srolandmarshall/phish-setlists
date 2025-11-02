"""Shared pytest fixtures for the Phish setlist maker tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from phish_setlist_maker.models import Base  # noqa: F401 - ensure all models registered
from phish_setlist_maker.models import (  # noqa: F401 - ensure all models registered
    Show,
    Song,
    SongTrack,
    Tour,
    Track,
    Venue,
)


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """Provide an isolated in-memory SQLite session for each test."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        engine.dispose()
