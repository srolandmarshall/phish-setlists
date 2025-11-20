"""Song catalog normalization and lookup helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Song


@dataclass(frozen=True)
class SongCatalogEntry:
    slug: str
    title: str
    original: bool
    artist: Optional[str]
    alias: Optional[str]


@dataclass
class SongCatalog:
    by_title: Dict[str, SongCatalogEntry]
    by_slug: Dict[str, SongCatalogEntry]


def normalize_title(title: str) -> str:
    return "".join(ch for ch in title.lower() if ch.isalnum())


def split_song_titles(raw_title: str) -> Iterable[str]:
    delimiters = ("->", ">")
    if any(marker in raw_title for marker in delimiters):
        parts = raw_title.replace("->", ">").split(">")
        for part in parts:
            stripped = part.strip()
            if stripped:
                yield stripped
    else:
        stripped = raw_title.strip()
        if stripped:
            yield stripped


def _parse_aliases(raw_alias: Optional[str]) -> List[str]:
    if not raw_alias:
        return []
    parts = re.split(r"[;/,]+", raw_alias)
    return [part.strip() for part in parts if part.strip()]


def determine_origin_from_entry(entry: SongCatalogEntry) -> Optional[str]:
    if entry.original:
        return "Phish original"

    artist = entry.artist.strip() if entry.artist else None
    if artist:
        if artist.lower() == "phish":
            return "Phish original"
        return f"Originally by {artist}"

    aliases = _parse_aliases(entry.alias)
    if aliases:
        return f"Alias: {aliases[0]}"

    return None


def build_song_catalog(db_session: Session) -> SongCatalog:
    """Construct lookups for titles/aliases to song metadata."""
    import time
    import logging
    t_start = time.time()
    logger = logging.getLogger("uvicorn.error")

    by_title: Dict[str, SongCatalogEntry] = {}
    by_slug: Dict[str, SongCatalogEntry] = {}

    stmt = select(Song.title, Song.alias, Song.slug, Song.original, Song.artist)
    for title, alias, slug, original, artist in db_session.execute(stmt):
        if not slug:
            continue
        entry = SongCatalogEntry(
            slug=slug,
            title=title,
            original=bool(original),
            artist=artist,
            alias=alias,
        )
        by_slug[slug] = entry

        normalized = normalize_title(title)
        if normalized and normalized not in by_title:
            by_title[normalized] = entry

        for alt in _parse_aliases(alias):
            normalized_alias = normalize_title(alt)
            if normalized_alias and normalized_alias not in by_title:
                by_title[normalized_alias] = entry

    logger.info("    ⏱️  Catalog query took %.2fs", time.time() - t_start)
    return SongCatalog(by_title=by_title, by_slug=by_slug)
