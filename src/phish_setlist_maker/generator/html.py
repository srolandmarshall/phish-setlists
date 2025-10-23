"""HTML rendering helpers for generated setlists and playlists."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

from html import escape

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
        f"Cutoff date: {meta.cutoff_date}",
        f"Era: {meta.era or 'All history'}",
        f"Year limit: {meta.year if meta.year else 'Full run'}",
    ]
    rows = "\n".join(f"          <li>{value}</li>" for value in items)
    return (
        '      <section class="card">\n'
        "        <h2>Context</h2>\n"
        "        <ul>\n"
        f"{rows}\n"
        "        </ul>\n"
        '        <p style="margin-top: 1em; font-size: 0.9em; color: #666;">\n'
        '          Data source: <a href="https://phish.in/" target="_blank">Phish.in</a> (MIT License)\n'
        "        </p>\n"
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
            href = escape(link.mp3_url, quote=True)
            cell_parts.append(
                f'<a href="#" data-audio-url="{href}">{display_title}</a>'
            )
        elif link.mp3_url and not include_links:
            href = escape(link.mp3_url, quote=True)
            cell_parts.append(f'<a href="{href}">{display_title}</a>')
        else:
            cell_parts.append(display_title)

        if link.origin:
            cell_parts.append(f'<div class="song-origin"><em>{link.origin}</em></div>')

        rows.append(f"            <li>{''.join(cell_parts)}</li>")

    body = "\n".join(rows)
    return (
        '      <section class="card">\n'
        f"        <h2>{section.title}</h2>\n"
        "        <ol>\n"
        f"{body}\n"
        "        </ol>\n"
        "      </section>\n"
    )


def _render_notes(notes: Iterable[str]) -> str:
    rows = "\n".join(f"          <li>{note}</li>" for note in notes)
    return (
        '      <section class="card">\n'
        "        <h2>Notes</h2>\n"
        "        <ul>\n"
        f"{rows}\n"
        "        </ul>\n"
        "      </section>\n"
    )


def _render_player(playlist_href: str, first_track_url: Optional[str]) -> str:
    audio_src = escape(first_track_url or "", quote=True)
    data_initial = escape(first_track_url or "", quote=True)
    href_attr = escape(playlist_href, quote=True)
    return (
        '      <section class="card">\n'
        "        <h2>Playlist</h2>\n"
        f'        <audio id="playlist-player" controls preload="none" src="{audio_src}" data-initial-url="{data_initial}">\n'
        "          Your browser does not support the audio element.\n"
        "        </audio>\n"
        "        <p>\n"
        f'          <a href="{href_attr}" download>Download M3U playlist</a>\n'
        "        </p>\n"
        "      </section>\n"
    )


def _render_script(first_track_url: Optional[str]) -> str:
    return (
        "    <script>\n"
        "      const player = document.getElementById('playlist-player');\n"
        "      if (player) {\n"
        "        const links = Array.from(document.querySelectorAll('a[data-audio-url]'));\n"
        "        const urls = links.map(link => link.dataset.audioUrl || '');\n"
        "        const initialUrl = player.dataset.initialUrl || '';\n"
        "        let currentIndex = urls.indexOf(initialUrl);\n"
        "        if (currentIndex === -1) {\n"
        "          currentIndex = 0;\n"
        "        }\n"
        "        if ((!player.getAttribute('src') || player.getAttribute('src') === '') && urls.length) {\n"
        "          player.src = urls[currentIndex];\n"
        "        }\n"
        "        const setActiveLink = () => {\n"
        "          links.forEach((link, idx) => {\n"
        "            if (idx === currentIndex) {\n"
        "              link.classList.add('active');\n"
        "            } else {\n"
        "              link.classList.remove('active');\n"
        "            }\n"
        "          });\n"
        "        };\n"
        "        setActiveLink();\n"
        "        const updateCurrentIndex = (url) => {\n"
        "          const idx = urls.indexOf(url);\n"
        "          if (idx !== -1) {\n"
        "            currentIndex = idx;\n"
        "            setActiveLink();\n"
        "          }\n"
        "        };\n"
        "        links.forEach((link, idx) => {\n"
        "          link.addEventListener('click', event => {\n"
        "            event.preventDefault();\n"
        "            const url = link.dataset.audioUrl;\n"
        "            if (!url) return;\n"
        "            updateCurrentIndex(url);\n"
        "            player.src = url;\n"
        "            player.play().catch(() => {});\n"
        "          });\n"
        "        });\n"
        "        player.addEventListener('ended', () => {\n"
        "          if (urls.length === 0) return;\n"
        "          const nextIndex = currentIndex + 1;\n"
        "          if (nextIndex < urls.length) {\n"
        "            currentIndex = nextIndex;\n"
        "            const nextUrl = urls[currentIndex];\n"
        "            if (nextUrl) {\n"
        "              player.src = nextUrl;\n"
        "              player.play().catch(() => {});\n"
        "              setActiveLink();\n"
        "            }\n"
        "          }\n"
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
        # If the caller supplied custom playlist sections (links), assume they
        # include any encore section they want. Don't auto-append another
        # encore to avoid duplication.
        yield from links
        return
    else:
        for segment in segments:
            yield PlaylistSection(
                title=segment.label,
                tracks=[PlaylistLink(title=song) for song in segment.songs],
            )

    if encore:
        encore_section = PlaylistSection(
            title=encore.label,
            tracks=(
                encore_links
                if encore_links is not None
                else [PlaylistLink(title=song) for song in encore.songs]
            ),
        )
        yield encore_section


def build_html_markup(
    generated: GeneratedSetlist,
    generated_at: datetime,
    *,
    playlist_filename: Optional[str] = None,
    first_track_url: Optional[str] = None,
    playlist_sections: Optional[Sequence[PlaylistSection]] = None,
    encore_links: Optional[Sequence[PlaylistLink]] = None,
    stylesheet_href: str = "phish-setlist.css",
    script_src: Optional[str] = None,
    venue_name: Optional[str] = None,
    venue_city: Optional[str] = None,
) -> str:
    """Compose the HTML markup for a generated setlist."""

    sections = list(
        _build_playlist_sections(
            generated.sets,
            generated.encore,
            playlist_sections,
            encore_links,
        )
    )

    include_playlist_links = playlist_filename is not None

    top_row: List[str] = []
    top_row.append(_render_context(generated, generated_at))
    if playlist_filename:
        top_row.append(_render_player(playlist_filename, first_track_url))

    sets_count = len(sections)
    sets_cols = sets_count if sets_count >= 2 else 1

    body: List[str] = []
    body.append("    <main>\n")

    if len(top_row) == 2:
        body.append('      <div class="top-row two-cols">\n')
        body.extend(top_row)
        body.append("      </div>\n")
    else:
        body.append('      <div class="top-row one-col">\n')
        body.append(top_row[0])
        body.append("      </div>\n")

    body.append(f'      <div class="sets-row" style="--sets-cols: {sets_cols};">\n')
    for section in sections:
        body.append(_render_section(section, include_links=include_playlist_links))
    body.append("      </div>\n")

    if generated.metadata.notes:
        body.append('      <div class="notes-row">\n')
        body.append(_render_notes(generated.metadata.notes))
        body.append("      </div>\n")

    body.append("    </main>\n")

    if playlist_filename:
        if script_src:
            script_href = escape(script_src, quote=True)
            body.append(f'    <script src="{script_href}"></script>\n')
        else:
            body.append(_render_script(first_track_url))

    stylesheet_attr = escape(stylesheet_href, quote=True)
    
    # Build title with venue and date
    today = generated_at.strftime("%B %d, %Y")
    if venue_name and venue_city:
        page_title = f"Inphinite Setlist - {venue_name}, {venue_city} - {today}"
    else:
        page_title = f"Inphinite Setlist - {today}"

    html_parts = [
        "<!DOCTYPE html>\n",
        '<html lang="en">\n',
        "<head>\n",
        '  <meta charset="utf-8" />\n',
        f"  <title>{escape(page_title)}</title>\n",
        f'  <link rel="stylesheet" href="{stylesheet_attr}">\n',
        "</head>\n",
        "<body>\n",
        f"  <h1>{escape(page_title)}</h1>\n",
        "".join(body),
        "</body>\n",
        "</html>\n",
    ]

    return "".join(html_parts)


def render_html(
    output_path: Path,
    generated: GeneratedSetlist,
    generated_at: datetime,
    *,
    playlist_path: Optional[Path] = None,
    first_track_url: Optional[str] = None,
    playlist_sections: Optional[Sequence[PlaylistSection]] = None,
    encore_links: Optional[Sequence[PlaylistLink]] = None,
    stylesheet_href: str = "phish-setlist.css",
    script_src: Optional[str] = None,
    venue_name: Optional[str] = None,
    venue_city: Optional[str] = None,
) -> None:
    """Render the generated setlist to an HTML file."""

    playlist_filename = playlist_path.name if playlist_path else None
    html_text = build_html_markup(
        generated,
        generated_at,
        playlist_filename=playlist_filename,
        first_track_url=first_track_url,
        playlist_sections=playlist_sections,
        encore_links=encore_links,
        stylesheet_href=stylesheet_href,
        script_src=script_src,
        venue_name=venue_name,
        venue_city=venue_city,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure output dir exists and write the CSS file next to the generated HTML so the link works
    css_source = Path(__file__).with_name("phish-setlist.css")
    css_target = output_path.parent / css_source.name
    try:
        css_text = css_source.read_text(encoding="utf-8")
        css_target.write_text(css_text, encoding="utf-8")
    except Exception:
        # If we can't copy the stylesheet for any reason, continue and still write the HTML
        pass

    if script_src:
        js_source = Path(__file__).with_name(script_src)
        js_target = output_path.parent / js_source.name
        try:
            js_text = js_source.read_text(encoding="utf-8")
            js_target.write_text(js_text, encoding="utf-8")
        except Exception:
            pass

    output_path.write_text(html_text, encoding="utf-8")
