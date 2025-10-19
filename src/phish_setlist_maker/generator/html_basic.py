"""Compatibility wrapper: reuse the richer renderer in `html.py`.

This module preserves the thin `render_html_report` API used elsewhere but
delegates to `render_html` for the actual work. It keeps the simple table-style
HTML callers working without duplicating templates or styles.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from .core import GeneratedSetlist
from .html import render_html, PlaylistSection, PlaylistLink


def render_html_report(
    *,
    output_path: Path,
    generated: GeneratedSetlist,
    generated_at: datetime,
    playlist_path: Optional[Path] = None,
    first_track_url: Optional[str] = None,
    playlist_sections: Optional[Sequence[PlaylistSection]] = None,
) -> None:
    """Delegate to `render_html` while keeping the old function signature.

    The heavier renderer already supports providing `playlist_sections`, so we
    simply forward arguments and let it handle writing the stylesheet.
    """

    # Forward to the canonical renderer. html.render_html writes the CSS next to
    # the `output_path`, so callers get the linked stylesheet automatically.
    render_html(
        output_path=output_path,
        generated=generated,
        generated_at=generated_at,
        playlist_path=playlist_path,
        first_track_url=first_track_url,
        playlist_sections=playlist_sections,
    )
