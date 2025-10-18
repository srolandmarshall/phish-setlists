#!/usr/bin/env python3
"""CLI helper to generate a Phish setlist and emit a Markdown report."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
import re
from random import Random, SystemRandom
from typing import Dict, Iterable, Optional, Tuple

import requests
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from phish_setlist_maker.db import session_scope  # noqa: E402
from phish_setlist_maker.generator import (  # noqa: E402
    SetlistGenerator,
    random_set_lengths,
)


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


def render_markdown(output_path: Path, generated, generated_at: datetime) -> None:
    lines = ["# Generated Setlist", ""]

    metadata = generated.metadata
    lines.append("## Context")
    lines.append(format_metadata_line("Generated at", generated_at.isoformat(timespec="seconds")))
    lines.append(format_metadata_line("Reference date", str(metadata.reference_date)))
    lines.append(format_metadata_line("Cutoff date", str(metadata.cutoff_date)))
    lines.append(format_metadata_line("Era", metadata.era or "All history"))
    lines.append(format_metadata_line("Year limit", str(metadata.year) if metadata.year else "Full run"))
    lines.append("")

    for segment in generated.sets:
        lines.append(f"## {segment.label}")
        for idx, song in enumerate(segment.songs, start=1):
            lines.append(f"{idx}. {song}")
        lines.append("")

    if generated.encore:
        lines.append("## Encore")
        for idx, song in enumerate(generated.encore.songs, start=1):
            lines.append(f"{idx}. {song}")
        lines.append("")

    if metadata.notes:
        lines.append("## Notes")
        for note in metadata.notes:
            lines.append(f"- {note}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def render_html(
    output_path: Path,
    generated,
    generated_at: datetime,
    playlist: Optional[Path] = None,
    playlist_segments: Optional[Iterable[Tuple[str, Iterable[Tuple[str, Optional[str]]]]]] = None,
    playlist_encore: Optional[Iterable[Tuple[str, Optional[str]]]] = None,
    first_track_url: Optional[str] = None,
) -> None:
    metadata = generated.metadata

    parts = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\" />",
        "  <title>Generated Setlist</title>",
        "  <style>",
        "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; line-height: 1.5; }",
        "    h1, h2 { color: #2a2a2a; }",
        "    ol { padding-left: 1.5rem; }",
        "    .segment { margin-bottom: 1.5rem; }",
        "    .notes ul { list-style: disc; margin-left: 1.5rem; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>Generated Setlist</h1>",
        "  <section>",
        "    <h2>Context</h2>",
        "    <ul>",
        f"      <li>Generated at: {generated_at.isoformat(timespec='seconds')}</li>",
        f"      <li>Reference date: {metadata.reference_date}</li>",
        f"      <li>Cutoff date: {metadata.cutoff_date}</li>",
        f"      <li>Era: {metadata.era or 'All history'}</li>",
        f"      <li>Year limit: {metadata.year if metadata.year else 'Full run'}</li>",
        "    </ul>",
        "  </section>",
    ]

    if playlist:
        playlist_rel = playlist.name
        audio_src = first_track_url or playlist_rel
        parts.append("  <section class=\"player\">")
        parts.append("    <h2>Playlist</h2>")
        parts.append(f"    <audio id=\"playlist-player\" controls autoplay preload=\"none\" src=\"{audio_src}\">")
        parts.append("      Your browser does not support the audio element.")
        parts.append("    </audio>")
        parts.append("    <p>")
        parts.append(f"      <a href=\"{playlist_rel}\" download>Download M3U playlist</a>")
        parts.append("    </p>")
        parts.append("  </section>")

    if playlist_segments is None:
        iterable_segments = [(segment.label, [(song, None) for song in segment.songs]) for segment in generated.sets]
    else:
        iterable_segments = playlist_segments

    for label, songs in iterable_segments:
        parts.append("  <section class=\"segment\">")
        parts.append(f"    <h2>{label}</h2>")
        parts.append("    <ol>")
        for title, url in songs:
            if playlist and url:
                parts.append(f"      <li><a href=\"#\" data-audio-url=\"{url}\">{title}</a></li>")
            elif url:
                parts.append(f"      <li><a href=\"{url}\">{title}</a></li>")
            else:
                parts.append(f"      <li>{title}</li>")
        parts.append("    </ol>")
        parts.append("  </section>")

    encore_rows = playlist_encore
    if encore_rows is None and generated.encore:
        encore_rows = [(song, None) for song in generated.encore.songs]

    if encore_rows:
        parts.append("  <section class=\"segment\">")
        parts.append("    <h2>Encore</h2>")
        parts.append("    <ol>")
        for title, url in encore_rows:
            if playlist and url:
                parts.append(f"      <li><a href=\"#\" data-audio-url=\"{url}\">{title}</a></li>")
            elif url:
                parts.append(f"      <li><a href=\"{url}\">{title}</a></li>")
            else:
                parts.append(f"      <li>{title}</li>")
        parts.append("    </ol>")
        parts.append("  </section>")

    if metadata.notes:
        parts.append("  <section class=\"notes\">")
        parts.append("    <h2>Notes</h2>")
        parts.append("    <ul>")
        for note in metadata.notes:
            parts.append(f"      <li>{note}</li>")
        parts.append("    </ul>")
        parts.append("  </section>")

    if playlist:
        parts.append("  <script>")
        parts.append("    const player = document.getElementById('playlist-player');")
        parts.append("    if (player) {")
        parts.append("      document.querySelectorAll('a[data-audio-url]').forEach(link => {")
        parts.append("        link.addEventListener('click', event => {")
        parts.append("          event.preventDefault();")
        parts.append("          const url = link.getAttribute('data-audio-url');")
        parts.append("          if (!url) return;")
        parts.append("          player.src = url;")
        parts.append("          player.play().catch(() => {});")
        parts.append("        });")
        parts.append("      });")
        parts.append("    }")
        parts.append("  </script>")

    parts.append("</body>")
    parts.append("</html>")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def split_song_titles(raw_title: str) -> Iterable[str]:
    parts = re.split(r"\s*(?:->|>)+\s*", raw_title)
    for part in parts:
        stripped = part.strip()
        if stripped:
            yield stripped


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
    track_cache: Dict[str, Optional[Dict]],
    slug_cache: Dict[str, Optional[str]],
) -> Optional[Dict]:
    key = normalize_title(title)
    if key in track_cache:
        return track_cache[key]

    slug = fetch_song_slug(title, session, slug_cache)
    if not slug:
        track_cache[key] = None
        return None

    params = {
        "song_slug": slug,
        "per_page": 1,
        "sort": "date:desc",
        "audio_status": "complete_or_partial",
    }
    try:
        resp = session.get("https://phish.in/api/v2/tracks.json", params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        track_cache[key] = None
        return None

    tracks = resp.json().get("tracks", [])
    track = tracks[0] if tracks else None
    if track and track.get("mp3_url"):
        track_cache[key] = track
    else:
        track_cache[key] = None
    return track_cache[key]


def build_playlist(
    base_path: Path,
    timestamp: str,
    segments,
    encore,
    metadata,
) -> Tuple[Path, Iterable[Tuple[str, Iterable[Tuple[str, Optional[str]]]]], Optional[Iterable[Tuple[str, Optional[str]]]], Optional[str]]:
    session = requests.Session()
    track_cache: Dict[str, Optional[Dict]] = {}
    slug_cache: Dict[str, Optional[str]] = {}
    missing: Dict[str, int] = {}
    playlist_lines = ["#EXTM3U"]

    def append_track(song_title: str) -> None:
        normalized = normalize_title(song_title)
        track = fetch_track_for_song(song_title, session, track_cache, slug_cache)
        if not track or not track.get("mp3_url"):
            missing[song_title] = missing.get(song_title, 0) + 1
            playlist_lines.append(f"#EXTINF:-1,{song_title} (unavailable)")
            playlist_lines.append(f"# Missing: {song_title}")
            return

        duration_ms = track.get("duration") or -1000
        duration_sec = int(duration_ms // 1000) if duration_ms >= 0 else -1
        show_date = track.get("show_date", "unknown date")
        playlist_lines.append(f"#EXTINF:{duration_sec},{song_title} [{show_date}]")
        playlist_lines.append(track["mp3_url"])

    for segment in segments:
        for raw_song in segment.songs:
            for title in split_song_titles(raw_song):
                append_track(title)

    if encore:
        for raw_song in encore.songs:
            for title in split_song_titles(raw_song):
                append_track(title)

    output_dir = base_path / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    playlist_path = output_dir / f"playlist_{timestamp}.m3u"
    playlist_path.write_text("\n".join(playlist_lines), encoding="utf-8")

    html_segments = []
    first_track_url: Optional[str] = None

    for segment in segments:
        rows = []
        for raw_song in segment.songs:
            for title in split_song_titles(raw_song):
                track = track_cache.get(normalize_title(title))
                url = track.get("mp3_url") if track else None
                if url and not first_track_url:
                    first_track_url = url
                rows.append((title, url))
        html_segments.append((segment.label, rows))

    html_encore = []
    if encore:
        rows = []
        for raw_song in encore.songs:
            for title in split_song_titles(raw_song):
                track = track_cache.get(normalize_title(title))
                url = track.get("mp3_url") if track else None
                if url and not first_track_url:
                    first_track_url = url
                rows.append((title, url))
        html_encore = rows

    for title in missing:
        metadata.notes.append(f"Playlist missing audio for {title} on phish.in")

    return playlist_path, html_segments, html_encore, first_track_url


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

    playlist_path = None
    html_segments = None
    html_encore = None
    first_track_url = None
    if args.playlist:
        playlist_path, html_segments, html_encore, first_track_url = build_playlist(PROJECT_ROOT, timestamp, generated.sets, generated.encore, generated.metadata)

    if args.playlist and not args.html:
        # Re-render HTML alongside Markdown to expose the player.
        render_markdown(output_path, generated, now_utc)
        html_output = output_path.with_suffix(".html")
        render_html(
            html_output,
            generated,
            now_utc,
            playlist=playlist_path,
            playlist_segments=html_segments,
            playlist_encore=html_encore,
            first_track_url=first_track_url,
        )
    elif args.html:
        render_html(
            output_path,
            generated,
            now_utc,
            playlist=playlist_path if args.playlist else None,
            playlist_segments=html_segments,
            playlist_encore=html_encore,
            first_track_url=first_track_url,
        )
    else:
        render_markdown(output_path, generated, now_utc)

    message = f"Wrote setlist to {output_path} (seed={seed_value})"
    if playlist_path:
        message += f"; playlist -> {playlist_path}"
    print(message)


if __name__ == "__main__":
    main()
