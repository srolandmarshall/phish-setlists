"""Public playlist artifact builder facade."""

from __future__ import annotations

from random import Random
from typing import Callable, Dict, Optional, Sequence

from sqlalchemy.orm import Session

from ..generator.core import SetSegment
from .catalog import SongCatalog
from .models import PlaylistArtifacts
from .playlist_sections import _build_sections, _process_segment_tracks, _render_m3u
from .playlist_track_assembly import build_playlist_artifacts as _assemble_playlist_artifacts


def build_playlist_artifacts(
    db_session: Session,
    segments: Sequence[SetSegment],
    encore: Optional[SetSegment],
    *,
    catalog: SongCatalog,
    rng: Random,
    include_m3u: bool,
    strict: bool,
    feature_store=None,
    same_show_segues: bool = False,
    generated_setlist=None,
    jamminess: Optional[float] = None,
    set_lengths: Optional[Dict[str, int]] = None,
    max_segues_per_set: int = 2,
    track_selector: Callable = None,
) -> PlaylistArtifacts:
    """Build playlist artifacts while keeping the public service API stable."""
    return _assemble_playlist_artifacts(
        db_session=db_session,
        segments=segments,
        encore=encore,
        catalog=catalog,
        rng=rng,
        include_m3u=include_m3u,
        strict=strict,
        feature_store=feature_store,
        same_show_segues=same_show_segues,
        generated_setlist=generated_setlist,
        jamminess=jamminess,
        set_lengths=set_lengths,
        max_segues_per_set=max_segues_per_set,
        track_selector=track_selector,
    )
