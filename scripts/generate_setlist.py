#!/usr/bin/env python3
"""CLI helper to generate a Phish setlist and emit a Markdown report."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
import re
from random import Random, SystemRandom
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from phish_setlist_maker.db import session_scope  # noqa: E402
from phish_setlist_maker.generator import SetlistGenerator, random_set_lengths  # noqa: E402
from phish_setlist_maker.generator.html_basic import PlaylistLink, PlaylistSection, render_html_report  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Phish setlist and write it to a Markdown file."
    )
    parser.add_argument(
        "--reference-date",
        type=lambda value: datetime.strptime(value, "%Y-%m-%d").date(),
        help="Anchor the generation context (YYYY-MM-DD). Defaults to latest show in DB.",
    )
    parser.add_argument(
        "--era",
        choices=["1.0", "2.0", "3.0", "4.0"],
        default="4.0",
        help="Restrict history to a specific era (default: 4.0).",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=datetime.now().year,
        help="Only consider shows through the end of this calendar year (default: current year).",
    )
    parser.add_argument(
        "--num-sets",
        type=int,
        choices=[2, 3],
        default=2,
        help="Number of main sets to generate (default: 2).",
    )
    parser.add_argument(
        "--no-encore",
        action="store_false",
        dest="include_encore",
        help="Skip generating an encore segment.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Seed for deterministic generation. Defaults to cryptographically random when omitted.",
    )
    parser.add_argument(
        "--allow-previous-show",
        action="store_true",
        help="Allow songs from the previous show to be eligible (default excludes them).",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Render output as HTML instead of Markdown.",
    )
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Build an M3U playlist by pulling public mp3 URLs from phish.in.",
    )
    parser.add_argument(
        "--set-length",
        action="append",
        default=[],
        metavar="SET=COUNT",
        help="Override a set length (e.g., --set-length set1=11). Repeat as needed.",
    )
    return parser.parse_args()


@dataclass(frozen=True)
class SongDisplay:
    """Presentation-friendly metadata for a single song appearance."""

    title: str
    mp3_url: Optional[str]
    duration_seconds: Optional[int]
    origin: Optional[str]
    show_date: Optional[str] = None

    @property
    def duration_label(self) -> Optional[str]:
        if self.duration_seconds is None or self.duration_seconds < 0:
            return None
        minutes, seconds = divmod(self.duration_seconds, 60)
        return f"{minutes}:{seconds:02d}"


def parse_set_lengths(overrides: list[str]) -> Dict[str, int]:
    parsed: Dict[str, int] = {}
    for entry in overrides:
        if "=" not in entry:
            raise ValueError(f"Invalid set-length override '{entry}'. Expected SET=COUNT.")
        label, value = entry.split("=", 1)
        label = label.strip().lower()
        if label not in {"set1", "set2", "set3", "encore"}:
            raise ValueError(f"Unsupported set label '{label}'.")
        try:
            parsed[label] = int(value)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid count for '{label}': {value}") from exc
    return parsed


def format_metadata_line(label: str, value: Optional[str]) -> str:
    display = value if value is not None else "N/A"
    return f"- {label}: {display}"


def render_markdown(
    output_path: Path,
    generated,
    generated_at: datetime,
    *,
    sections: Optional[Sequence[Tuple[str, Sequence[SongDisplay]]]] = None,
) -> None:
    lines = ["# Generated Setlist", ""]

    metadata = generated.metadata
    lines.append("## Context")
    lines.append(format_metadata_line("Generated at", generated_at.isoformat(timespec="seconds")))
    lines.append(format_metadata_line("Reference date", str(metadata.reference_date)))
    lines.append(format_metadata_line("Cutoff date", str(metadata.cutoff_date)))
    lines.append(format_metadata_line("Era", metadata.era or "All history"))
    lines.append(format_metadata_line("Year limit", str(metadata.year) if metadata.year else "Full run"))
    lines.append("")

    section_lookup: Dict[str, Sequence[SongDisplay]] = {}
    if sections:
        for title, tracks in sections:
            section_lookup[title] = tracks

    def section_tracks(label: str, fallback_songs: Sequence[str]) -> Sequence[SongDisplay]:
        rows = section_lookup.get(label)
        if rows:
            return rows
        return [SongDisplay(title=song, mp3_url=None, duration_seconds=None, origin=None) for song in fallback_songs]

    for segment in generated.sets:
        lines.append(f"## {segment.label}")
        rows = section_tracks(segment.label, segment.songs)
        for idx, song in enumerate(rows, start=1):
            display = song.title
            if song.duration_label:
                display = f"{display} [{song.duration_label}]"
            lines.append(f"{idx}. {display}")
            if song.origin:
                lines.append(f"   *{song.origin}*")
        lines.append("")

    if generated.encore:
        lines.append("## Encore")
        encore_label = generated.encore.label if generated.encore else "Encore"
        rows = section_tracks(encore_label, generated.encore.songs if generated.encore else [])
        for idx, song in enumerate(rows, start=1):
            display = song.title
            if song.duration_label:
                display = f"{display} [{song.duration_label}]"
            lines.append(f"{idx}. {display}")
            if song.origin:
                lines.append(f"   *{song.origin}*")
        lines.append("")

    if metadata.notes:
        lines.append("## Notes")
        for note in metadata.notes:
            lines.append(f"- {note}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def split_song_titles(raw_title: str) -> Iterable[str]:
    parts = re.split(r"\s*(?:->|>)+\s*", raw_title)
    for part in parts:
        stripped = part.strip()
        if stripped:
            yield stripped


def determine_origin(track: Dict) -> Optional[str]:
    """Derive human-readable origin text from track metadata."""

    song_info = track.get("song") or {}
    if song_info.get("original"):
        return "Phish original"

    artist = song_info.get("artist") or track.get("artist")
    if artist:
        normalized = artist.strip()
        if normalized.lower() == "phish":
            return "Phish original"
        return f"Originally by {normalized}"

    alias = song_info.get("alias")
    if alias:
        return f"Alias: {alias}"

    return None


def populate_slug_cache(session: requests.Session, slug_cache: Dict[str, Optional[str]]) -> None:
    if slug_cache.get("__loaded"):
        return

    page = 1
    while True:
        params = {"page": page, "per_page": 1000}
        try:
            resp = session.get("https://phish.in/api/v2/songs.json", params=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException:
            slug_cache["__loaded"] = True
            return

        data = resp.json()
        for song in data.get("songs", []):
            key = normalize_title(song.get("title", ""))
            if key and key not in slug_cache:
                slug_cache[key] = song.get("slug")
            alias = normalize_title(song.get("alias", "")) if song.get("alias") else None
            if alias and alias not in slug_cache:
                slug_cache[alias] = song.get("slug")

        total_pages = data.get("total_pages") or page
        if page >= total_pages:
            break
        page += 1

    slug_cache["__loaded"] = True


def fetch_song_slug(title: str, session: requests.Session, slug_cache: Dict[str, Optional[str]]) -> Optional[str]:
    key = normalize_title(title)
    if key in slug_cache:
        return slug_cache[key]

    populate_slug_cache(session, slug_cache)
    slug_cache.setdefault(key, None)
    return slug_cache[key]


def fetch_track_for_song(
    title: str,
    session: requests.Session,
    track_cache: Dict[str, Optional[SongDisplay]],
    slug_cache: Dict[str, Optional[str]],
    rng: Random,
) -> Optional[SongDisplay]:
    key = normalize_title(title)
    if key in track_cache:
        return track_cache[key]

    slug = fetch_song_slug(title, session, slug_cache)
    if not slug:
        track_cache[key] = None
        return None

    params = {
        "song_slug": slug,
        "per_page": 30,
        "sort": "likes_count:desc",
        "audio_status": "complete_or_partial",
    }
    try:
        resp = session.get("https://phish.in/api/v2/tracks.json", params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        track_cache[key] = None
        return None

    tracks = resp.json().get("tracks", [])
    candidates = [
        track
        for track in tracks
        if track.get("mp3_url") and track.get("audio_status") in {"complete", "partial"}
    ]
    track = rng.choice(candidates) if candidates else None
    if track is None and tracks:
        track = tracks[0]
    if not track:
        track_cache[key] = None
        return None

    duration_ms = track.get("duration")
    duration_seconds = int(duration_ms // 1000) if isinstance(duration_ms, (int, float)) else None
    origin_text = determine_origin(track)

    song_display = SongDisplay(
        title=title,
        mp3_url=track.get("mp3_url"),
        duration_seconds=duration_seconds if duration_seconds is not None and duration_seconds >= 0 else None,
        origin=origin_text,
        show_date=track.get("show_date"),
    )
    track_cache[key] = song_display
    return song_display


def build_playlist(
    base_path: Path,
    timestamp: str,
    segments,
    encore,
    metadata,
    rng: Random,
    *,
    create_playlist_file: bool,
) -> Tuple[Optional[Path], List[Tuple[str, List[SongDisplay]]], Optional[str]]:
    session = requests.Session()
    track_cache: Dict[str, Optional[SongDisplay]] = {}
    slug_cache: Dict[str, Optional[str]] = {}
    missing: Dict[str, int] = {}
    playlist_lines: List[str] = ["#EXTM3U"]

    def append_track(song_title: str) -> None:
        normalized = normalize_title(song_title)
        track = fetch_track_for_song(song_title, session, track_cache, slug_cache, rng)
        if not track or not track.mp3_url:
            missing[song_title] = missing.get(song_title, 0) + 1
            playlist_lines.append(f"#EXTINF:-1,{song_title} (unavailable)")
            playlist_lines.append(f"# Missing: {song_title}")
            return

        duration_sec = track.duration_seconds if track.duration_seconds is not None else -1
        show_date = track.show_date or "unknown date"
        playlist_lines.append(f"#EXTINF:{duration_sec},{song_title} [{show_date}]")
        playlist_lines.append(track.mp3_url)

    for segment in segments:
        for raw_song in segment.songs:
            for title in split_song_titles(raw_song):
                append_track(title)

    if encore:
        for raw_song in encore.songs:
            for title in split_song_titles(raw_song):
                append_track(title)

    playlist_path: Optional[Path] = None
    if create_playlist_file:
        output_dir = base_path / "data"
        output_dir.mkdir(parents=True, exist_ok=True)
        playlist_path = output_dir / f"playlist_{timestamp}.m3u"
        playlist_path.write_text("\n".join(playlist_lines), encoding="utf-8")

    html_sections: List[Tuple[str, List[SongDisplay]]] = []
    first_track_url: Optional[str] = None

    for segment in segments:
        rows: List[SongDisplay] = []
        for raw_song in segment.songs:
            for title in split_song_titles(raw_song):
                track = track_cache.get(normalize_title(title))
                if track and track.mp3_url and not first_track_url:
                    first_track_url = track.mp3_url
                rows.append(
                    SongDisplay(
                        title=title,
                        mp3_url=track.mp3_url if track else None,
                        duration_seconds=track.duration_seconds if track else None,
                        origin=track.origin if track else None,
                        show_date=track.show_date if track else None,
                    )
                )
        html_sections.append((segment.label, rows))

    if encore:
        rows: List[SongDisplay] = []
        for raw_song in encore.songs:
            for title in split_song_titles(raw_song):
                track = track_cache.get(normalize_title(title))
                if track and track.mp3_url and not first_track_url:
                    first_track_url = track.mp3_url
                rows.append(
                    SongDisplay(
                        title=title,
                        mp3_url=track.mp3_url if track else None,
                        duration_seconds=track.duration_seconds if track else None,
                        origin=track.origin if track else None,
                        show_date=track.show_date if track else None,
                    )
                )
        html_sections.append((encore.label, rows))

    if create_playlist_file:
        for title in missing:
            metadata.notes.append(f"Playlist missing audio for {title} on phish.in")

    if not create_playlist_file:
        first_track_url = None

    return playlist_path, html_sections, first_track_url


def main() -> None:
    args = parse_args()

    set_length_overrides = parse_set_lengths(args.set_length)

    seed_value = args.seed if args.seed is not None else SystemRandom().randint(0, 2**32 - 1)
    rng = Random(seed_value)
    length_rng: Optional[Random] = Random(seed_value)

    with session_scope() as session:
        generator = SetlistGenerator(session, rng=rng)

        set_lengths = dict(set_length_overrides)
        if not set_lengths:
            set_lengths = random_set_lengths(
                session,
                reference_date=args.reference_date,
                era=args.era,
                year=args.year,
                num_sets=args.num_sets,
                include_encore=args.include_encore,
                rng=length_rng,
            )

        generated = generator.generate(
            reference_date=args.reference_date,
            era=args.era,
            year=args.year,
            num_sets=args.num_sets,
            include_encore=args.include_encore,
            set_lengths=set_lengths,
            exclude_previous_show=not args.allow_previous_show,
        )

    now_utc = datetime.now(timezone.utc)
    timestamp = now_utc.strftime("%Y%m%d_%H%M%S")
    output_dir = PROJECT_ROOT / "data"
    extension = "html" if args.html else "md"
    output_path = output_dir / f"setlist_{timestamp}.{extension}"

    playlist_path: Optional[Path]
    playlist_sections_data: List[Tuple[str, List[SongDisplay]]]
    first_track_url: Optional[str]

    playlist_path, playlist_sections_data, first_track_url = build_playlist(
        PROJECT_ROOT,
        timestamp,
        generated.sets,
        generated.encore,
        generated.metadata,
        rng,
        create_playlist_file=args.playlist,
    )

    def render_html_output(path: Path, include_playlist: bool) -> None:
        playlist_file = playlist_path if include_playlist else None
        track_url = first_track_url if include_playlist else None

        sections: Optional[List[PlaylistSection]] = None
        if playlist_sections_data:
            sections = [
                PlaylistSection(
                    title=section_title,
                    tracks=[
                        PlaylistLink(
                            title=song.title,
                            mp3_url=song.mp3_url if include_playlist else None,
                            duration=song.duration_label,
                            origin=song.origin,
                        )
                        for song in rows
                    ],
                )
                for section_title, rows in playlist_sections_data
            ]

        render_html_report(
            output_path=path,
            generated=generated,
            generated_at=now_utc,
            playlist_path=playlist_file,
            first_track_url=track_url,
            playlist_sections=sections,
        )

    if args.playlist:
        render_markdown(output_path, generated, now_utc, sections=playlist_sections_data)
        html_output = output_path.with_suffix(".html")
        render_html_output(html_output, include_playlist=True)
    elif args.html:
        render_html_output(output_path, include_playlist=False)
    else:
        render_markdown(output_path, generated, now_utc, sections=playlist_sections_data)

    message = f"Wrote setlist to {output_path} (seed={seed_value})"
    if playlist_path:
        message += f"; playlist -> {playlist_path}"
    print(message)


if __name__ == "__main__":
    main()
