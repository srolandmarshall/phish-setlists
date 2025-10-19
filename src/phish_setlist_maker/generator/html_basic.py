"""Minimal HTML generator using simple tables for setlists."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence

from .core import GeneratedSetlist, SetSegment


@dataclass(frozen=True)
class PlaylistLink:
    title: str
    mp3_url: Optional[str] = None


@dataclass(frozen=True)
class PlaylistSection:
    title: str
    tracks: Sequence[PlaylistLink]


def _default_sections(generated: GeneratedSetlist) -> Sequence[PlaylistSection]:
    sections = [
        PlaylistSection(
            title=segment.label,
            tracks=[PlaylistLink(title=song) for song in segment.songs],
        )
        for segment in generated.sets
    ]
    if generated.encore:
        sections.append(
            PlaylistSection(
                title=generated.encore.label,
                tracks=[PlaylistLink(title=song) for song in generated.encore.songs],
            )
        )
    return sections


def render_html_report(
    *,
    output_path: Path,
    generated: GeneratedSetlist,
    generated_at: datetime,
    playlist_path: Optional[Path] = None,
    first_track_url: Optional[str] = None,
    playlist_sections: Optional[Sequence[PlaylistSection]] = None,
) -> None:
    include_links = playlist_path is not None
    sections = playlist_sections or _default_sections(generated)

    context_rows = [
        ("Generated at", generated_at.isoformat(timespec="seconds")),
        ("Reference date", str(generated.metadata.reference_date)),
        ("Cutoff date", str(generated.metadata.cutoff_date)),
        ("Era", generated.metadata.era or "All history"),
        ("Year limit", str(generated.metadata.year) if generated.metadata.year else "Full run"),
    ]

    def render_context() -> str:
        rows = "\n".join(
            f"      <tr><th>{label}</th><td>{value}</td></tr>" for label, value in context_rows
        )
        return (
            "<table class=\"set-table\">\n"
            "  <caption>Context</caption>\n"
            "  <tbody>\n"
            f"{rows}\n"
            "  </tbody>\n"
            "</table>\n"
        )

    def render_playlist() -> str:
        if not playlist_path:
            return ""
        audio_src = first_track_url or playlist_path.name
        return (
            "<table class=\"set-table\">\n"
            "  <caption>Playlist</caption>\n"
            "  <tbody>\n"
            f"    <tr><td><audio id=\"playlist-player\" controls autoplay preload=\"none\" src=\"{audio_src}\">"
            "Your browser does not support the audio element.</audio></td></tr>\n"
            f"    <tr><td><a href=\"{playlist_path.name}\" download>Download M3U playlist</a></td></tr>\n"
            "  </tbody>\n"
            "</table>\n"
        )

    def render_section(section: PlaylistSection) -> str:
        rows = []
        for link in section.tracks:
            if include_links and link.mp3_url:
                rows.append(
                    f"      <tr><td><a href=\"#\" data-audio-url=\"{link.mp3_url}\">{link.title}</a></td></tr>"
                )
            elif link.mp3_url:
                rows.append(f"      <tr><td><a href=\"{link.mp3_url}\">{link.title}</a></td></tr>")
            else:
                rows.append(f"      <tr><td>{link.title}</td></tr>")
        body = "\n".join(rows)
        return (
            "<table class=\"set-table\">\n"
            f"  <caption>{section.title}</caption>\n"
            "  <tbody>\n"
            f"{body}\n"
            "  </tbody>\n"
            "</table>\n"
        )

    def render_notes() -> str:
        if not generated.metadata.notes:
            return ""
        rows = "\n".join(f"      <li>{note}</li>" for note in generated.metadata.notes)
        return (
            "<section class=\"notes\">\n"
            "  <h2>Notes</h2>\n"
            "  <ul>\n"
            f"{rows}\n"
            "  </ul>\n"
            "</section>\n"
        )

    content = [render_context(), render_playlist()]
    content.extend(render_section(section) for section in sections)
    notes_html = render_notes()

    html_parts = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\" />",
        "  <title>Generated Setlist</title>",
        "  <style>",
        "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8f9fa; padding: 2rem; margin: 0; }",
        "    h1 { text-align: center; margin-bottom: 1.5rem; }",
        "    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }",
        "    .set-table { width: 100%; border-collapse: collapse; background: white; border: 1px solid #dee2e6; border-radius: 6px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }",
        "    .set-table caption { background: #0b7285; color: white; font-weight: 600; padding: 0.65rem; }",
        "    .set-table td, .set-table th { padding: 0.55rem 0.75rem; border-bottom: 1px solid #dee2e6; }",
        "    .set-table tr:last-child td { border-bottom: none; }",
        "    .notes ul { margin: 0; padding-left: 1.25rem; }",
        "    audio { width: 100%; margin-top: 0.5rem; }",
        "    a { color: #0b7285; text-decoration: none; }",
        "    a:hover { text-decoration: underline; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>Generated Setlist</h1>",
        "  <div class=\"grid\">",
        *content,
        "  </div>",
        notes_html,
    ]

    if playlist_path:
        html_parts.extend(
            [
                "  <script>",
                "    const player = document.getElementById('playlist-player');",
                "    if (player) {",
                "      document.querySelectorAll('a[data-audio-url]').forEach(link => {",
                "        link.addEventListener('click', event => {",
                "          event.preventDefault();",
                "          const url = link.getAttribute('data-audio-url');",
                "          if (!url) return;",
                "          player.src = url;",
                "          player.play().catch(() => {});",
                "        });",
                "      });",
                "    }",
                "  </script>",
            ]
        )

    html_parts.extend(["</body>", "</html>"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(html_parts), encoding="utf-8")
