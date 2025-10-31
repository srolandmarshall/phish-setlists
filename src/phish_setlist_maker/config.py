"""Configuration helpers for environment-driven settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv()


@dataclass(slots=True)
class DatabaseSettings:
    """Simple container for database connection details."""

    user: str
    password: str
    host: str = "localhost"
    port: int = 5432
    name: str = "phish-setlist-maker"

    def url(self, hide_password: bool = True) -> str:
        """Return the database URL string.

        Default is to hide the password to avoid accidental leakage when
        URLs are logged or printed. Callers that require the full URL for
        engine creation should pass `hide_password=False` explicitly.
        """
        url = URL.create(
            "postgresql+psycopg2",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.name,
        )
        return url.render_as_string(hide_password=hide_password)

    def __str__(self) -> str:
        """Redacted string representation safe for logging.

        Example: postgresql+psycopg2://user:*****@host:5432/dbname
        """
        try:
            return self.url(hide_password=True)
        except Exception:
            # Fallback to minimal redacted form if URL construction fails
            host = self.host or "<host>"
            port = self.port or 0
            name = self.name or "<db>"
            user = self.user or "<user>"
            return f"postgresql+psycopg2://{user}:*****@{host}:{port}/{name}"


def _parse_database_url(url: str) -> DatabaseSettings:
    """Parse DATABASE_URL into DatabaseSettings."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return DatabaseSettings(
        user=parsed.username or "",
        password=parsed.password or "",
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        name=parsed.path.lstrip("/") if parsed.path else "phish-setlist-maker",
    )


def _build_database_settings(
    prefix: str, *, fallback: DatabaseSettings | None = None
) -> DatabaseSettings:
    # Check for DATABASE_URL first (common in cloud deployments)
    if prefix == "DB":
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            return _parse_database_url(database_url)

    user_key = f"{prefix}_USER"
    password_key = f"{prefix}_PASS"
    host_key = f"{prefix}_HOST"
    port_key = f"{prefix}_PORT"
    name_key = f"{prefix}_NAME"

    user = os.getenv(user_key)
    password = os.getenv(password_key)

    if user and password:
        host = os.getenv(host_key, fallback.host if fallback else "localhost")
        port = int(os.getenv(port_key, str(fallback.port if fallback else 5432)))
        name = os.getenv(name_key, fallback.name if fallback else "phish-setlist-maker")
        return DatabaseSettings(
            user=user, password=password, host=host, port=port, name=name
        )

    if fallback:
        return fallback

    missing = [
        key for key, value in [(user_key, user), (password_key, password)] if not value
    ]
    raise RuntimeError(
        f"Missing database credentials in environment variables: {', '.join(missing)}"
    )


def get_database_settings() -> DatabaseSettings:
    """Read primary database settings from environment variables."""

    return _build_database_settings("DB")


def get_analytics_database_settings() -> DatabaseSettings:
    """Return settings for the analytics workspace database.

    Falls back to the primary database when dedicated analytics credentials are missing.
    """

    primary = get_database_settings()
    return _build_database_settings("ANALYTICS_DB", fallback=primary)
