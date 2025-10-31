"""Create or refresh the analytics database workspace.

This helper uses the ANALYTICS_DB_* environment variables when present;
otherwise it falls back to the main DB credentials, allowing ad-hoc clones.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy_utils import create_database, database_exists, drop_database

from phish_setlist_maker.config import (
    get_analytics_database_settings,
    get_database_settings,
)


def ensure_database(create: bool, drop: bool) -> int:
    analytics_settings = get_analytics_database_settings()
    analytics_url_full = analytics_settings.url(hide_password=False)
    analytics_url_safe = str(analytics_settings)

    primary_settings = get_database_settings()
    primary_url_full = primary_settings.url(hide_password=False)
    primary_url_safe = str(primary_settings)

    if analytics_url_full == primary_url_full:
        print(
            "Analytics database shares credentials with the primary database.\n"
            "Configure ANALYTICS_DB_* variables to isolate a scratch workspace."
        )
        return 0

    exists = database_exists(analytics_url_full)

    if drop and exists:
        print(f"Dropping analytics database: {analytics_url_safe}")
        drop_database(analytics_url_full)
        exists = False

    if create:
        if not exists:
            print(f"Creating analytics database: {analytics_url_safe}")
            create_database(analytics_url_full)
        else:
            print("Analytics database already exists; skipping creation.")

    print("Analytics database URL:", analytics_url_safe)
    print("Primary database URL  :", primary_url_safe)
    print(
        "\nNext steps:\n"
        "  • Use pg_dump/pg_restore (or psql COPY) to seed the analytics DB.\n"
        "  • Run scripts/audit_database.py with ANALYTICS_DB_* vars set to validate the copy."
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap the analytics database workspace."
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="Create the analytics database if it does not exist.",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop the analytics database before creation.",
    )
    args = parser.parse_args()

    if not args.create and not args.drop:
        parser.error("Specify --create and/or --drop to modify the analytics database.")

    raise SystemExit(ensure_database(create=args.create, drop=args.drop))


if __name__ == "__main__":
    main()
