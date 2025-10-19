"""HTML rendering helpers for generated setlists and playlists."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

from .core import GeneratedSetlist, SetSegment


@dataclass(frozen=True)
class PlaylistLink:
    """Linking information for a single song in the rendered output."""

    title: str
    mp3_url: Optional[str] = None
    duration: Optional[str] = None
    origin: Optional[str] = None


@dataclass(frozen=True)
class PlaylistSection:
    """Grouping of songs (e.g., Set 1, Encore) with optional audio links."""

    title: str
    tracks: Sequence[PlaylistLink]


def _render_context(generated: GeneratedSetlist, generated_at: datetime) -> str:
    meta = generated.metadata
    items = [
        f"Generated at: {generated_at.isoformat(timespec='seconds')}",
        f"Reference date: {meta.reference_date}",
        f"Cutoff date: {meta.cutoff_date}",
        f"Era: {meta.era or 'All history'}",
        f"Year limit: {meta.year if meta.year else 'Full run'}",
    ]
    rows = "\n".join(f"          <li>{value}</li>" for value in items)
    return (
        "      <section class=\"card\">\n"
        "        <h2>Context</h2>\n"
        "        <ul>\n"
        f"{rows}\n"
        "        </ul>\n"
        "      </section>\n"
    )


def _render_section(section: PlaylistSection, include_links: bool) -> str:
    rows = []
    for link in section.tracks:
        display_title = link.title
        if link.duration:
            display_title = f"{display_title} [{link.duration}]"

        cell_parts = []
        if include_links and link.mp3_url:
            cell_parts.append(
                f"<a href=\"#\" data-audio-url=\"{link.mp3_url}\">{display_title}</a>"
            )
        elif link.mp3_url and not include_links:
            cell_parts.append(f"<a href=\"{link.mp3_url}\">{display_title}</a>")
        else:
            cell_parts.append(display_title)

        if link.origin:
            cell_parts.append(f"<div class=\"song-origin\"><em>{link.origin}</em></div>")

        rows.append(f"            <li>{''.join(cell_parts)}</li>")

    body = "\n".join(rows)
    return (
        "      <section class=\"card\">\n"
        f"        <h2>{section.title}</h2>\n"
        "        <ol>\n"
        f"{body}\n"
        "        </ol>\n"
        "      </section>\n"
    )


def _render_notes(notes: Iterable[str]) -> str:
    rows = "\n".join(f"          <li>{note}</li>" for note in notes)
    return (
        "      <section class=\"card\">\n"
        "        <h2>Notes</h2>\n"
        "        <ul>\n"
        f"{rows}\n"
        "        </ul>\n"
        "      </section>\n"
    )


def _render_player(m3u_path: Path, first_track_url: Optional[str]) -> str:
    audio_src = first_track_url or m3u_path.name
    return (
        "      <section class=\"card\">\n"
        "        <h2>Playlist</h2>\n"
        f"        <audio id=\"playlist-player\" controls autoplay preload=\"none\" src=\"{audio_src}\">\n"
        "          Your browser does not support the audio element.\n"
        "        </audio>\n"
        "        <p>\n"
        f"          <a href=\"{m3u_path.name}\" download>Download M3U playlist</a>\n"
        "        </p>\n"
        "      </section>\n"
    )


def _render_script() -> str:
    return (
        "    <script>\n"
        "      const player = document.getElementById('playlist-player');\n"
        "      if (player) {\n"
        "        document.querySelectorAll('a[data-audio-url]').forEach(link => {\n"
        "          link.addEventListener('click', event => {\n"
        "            event.preventDefault();\n"
        "            const url = link.getAttribute('data-audio-url');\n"
        "            if (!url) return;\n"
        "            player.src = url;\n"
        "            player.play().catch(() => {});\n"
        "          });\n"
        "        });\n"
        "      }\n"
        "    </script>\n"
    )


def _build_playlist_sections(
    segments: Sequence[SetSegment],
    encore: Optional[SetSegment],
    links: Optional[Sequence[PlaylistSection]],
    encore_links: Optional[Sequence[PlaylistLink]],
) -> Iterable[PlaylistSection]:
    if links:
        yield from links
    else:
        for segment in segments:
            yield PlaylistSection(
                title=segment.label,
                tracks=[PlaylistLink(title=song) for song in segment.songs],
            )
    if encore:
        encore_section = PlaylistSection(
            title=encore.label,
            tracks=encore_links
            if encore_links is not None
            else [PlaylistLink(title=song) for song in encore.songs],
        )
        yield encore_section


def render_html(
    output_path: Path,
    generated: GeneratedSetlist,
    generated_at: datetime,
    *,
    playlist_path: Optional[Path] = None,
    first_track_url: Optional[str] = None,
    playlist_sections: Optional[Sequence[PlaylistSection]] = None,
    encore_links: Optional[Sequence[PlaylistLink]] = None,
) -> None:
    """Render the generated setlist to an HTML file."""

    sections = list(
        _build_playlist_sections(
            generated.sets,
            generated.encore,
            playlist_sections,
            encore_links,
        )
    )

    include_playlist_links = playlist_path is not None

    body_parts = [
        "    <main>\n",
        _render_context(generated, generated_at),
    ]

    if playlist_path:
        body_parts.append(_render_player(playlist_path, first_track_url))

    for section in sections:
        body_parts.append(_render_section(section, include_links=include_playlist_links))

    if generated.metadata.notes:
        body_parts.append(_render_notes(generated.metadata.notes))

    body_parts.append("    </main>\n")
    if playlist_path:
        body_parts.append(_render_script())

    html = [
        "<!DOCTYPE html>\n",
        "<html lang=\"en\">\n",
        "<head>\n",
        "  <meta charset=\"utf-8\" />\n",
        "  <title>Generated Setlist</title>\n",
        "  <style>\n",
        "    :root { color-scheme: light dark; --card-bg: rgba(255,255,255,0.85); --border: rgba(0,0,0,0.1); }\n",
        "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;\n",
        "          margin: 0 auto; padding: 2rem; max-width: 960px; background: #f5f5f5; }\n",
        "    h1 { margin-bottom: 1.5rem; text-align: center; }\n",
        "    h2 { margin-top: 0; }\n",
        "    main { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));\n",
        "           gap: 1.5rem; }\n",
        "    .card { background: var(--card-bg); border-radius: 12px; padding: 1.2rem; box-shadow: 0 8px 24px rgba(0,0,0,0.08);\n",
        "            border: 1px solid var(--border); display: flex; flex-direction: column; gap: 0.75rem; }\n",
        "    ul, ol { margin: 0; padding-left: 1.25rem; }\n",
        "    audio { width: 100%; }\n",
        "    a { color: #0b7285; text-decoration: none; }\n",
        "    a:hover { text-decoration: underline; }\n",
        "    .song-origin { display: block; margin-top: 0.25rem; font-size: 0.9em; color: #495057; }\n",
        "  </style>\n",
        "</head>\n",
        "<body>\n",
        "  <h1>Generated Setlist</h1>\n",
        "".join(body_parts),
        "</body>\n",
        "</html>\n",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(html), encoding="utf-8")
