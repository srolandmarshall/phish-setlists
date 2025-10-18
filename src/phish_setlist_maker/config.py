"""Configuration helpers for environment-driven settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class DatabaseSettings:
    """Simple container for database connection details."""

    user: str
    password: str
    host: str = "localhost"
    port: int = 5432
    name: str = "phish-setlist-maker"

    def url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


def get_database_settings() -> DatabaseSettings:
    """Read database settings from environment variables."""

    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")

    missing = [name for name, value in [("DB_USER", user), ("DB_PASS", password)] if not value]
    if missing:
        raise RuntimeError(
            f"Missing database credentials in environment variables: {', '.join(missing)}"
        )

    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    name = os.getenv("DB_NAME", "phish-setlist-maker")

    return DatabaseSettings(user=user, password=password, host=host, port=port, name=name)
