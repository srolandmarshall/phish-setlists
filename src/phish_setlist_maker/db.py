"""Helpers for working with the project database."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_analytics_database_settings, get_database_settings

_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None
_analytics_engine: Optional[Engine] = None
_AnalyticsSessionFactory: Optional[sessionmaker] = None


def get_engine(echo: bool = False) -> Engine:
    """Create (or reuse) the SQLAlchemy engine."""

    global _engine
    if _engine is None:
        db_settings = get_database_settings()
        _engine = create_engine(db_settings.url(), echo=echo, future=True)
    return _engine


def get_session_factory(echo: bool = False) -> sessionmaker:
    """Return the configured session factory."""

    global _SessionFactory
    if _SessionFactory is None:
        engine = get_engine(echo=echo)
        _SessionFactory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return _SessionFactory


def get_analytics_engine(echo: bool = False) -> Engine:
    """Engine for the analytics workspace (falls back to primary DB)."""

    global _analytics_engine
    if _analytics_engine is None:
        db_settings = get_analytics_database_settings()
        _analytics_engine = create_engine(db_settings.url(), echo=echo, future=True)
    return _analytics_engine


def get_analytics_session_factory(echo: bool = False) -> sessionmaker:
    """Session factory bound to the analytics database."""

    global _AnalyticsSessionFactory
    if _AnalyticsSessionFactory is None:
        engine = get_analytics_engine(echo=echo)
        _AnalyticsSessionFactory = sessionmaker(
            bind=engine,
            expire_on_commit=False,
            future=True,
        )
    return _AnalyticsSessionFactory


@contextmanager
def session_scope(echo: bool = False) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""

    session_cls = get_session_factory(echo=echo)
    session = session_cls()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def analytics_session_scope(echo: bool = False) -> Generator[Session, None, None]:
    """Transactional scope for the analytics database."""

    session_cls = get_analytics_session_factory(echo=echo)
    session = session_cls()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
