"""Ordered selection and assembly of generated playlist tracks."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from random import Random
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from ..generator.core import SetSegment
from .catalog import SongCatalog, normalize_title, split_song_titles
from .errors import PlaylistServiceError
from .models import PlaylistArtifacts, SongDisplay
from .playlist_duration import compensate_for_continuations
from .playlist_queries import _load_song_duration_stats
from .playlist_sections import _build_sections, _render_m3u
from .playlist_segue_injection import SegueInjection

logger = logging.getLogger("uvicorn.error")


def _process_segment_tracks(
    segments: Sequence[SetSegment],
    encore: Optional[SetSegment],
    append_track_with_injection: Callable[..., None],
) -> None:
    """Resolve track displays for each generated segment in set order."""
    for segment in segments:
        from ..generator.historical import normalize_set_label
        canonical = normalize_set_label(segment.label) if segment.label else None

        # Flatten segment songs for indexing
        segment_songs_flat = []
        for raw_song in segment.songs:
            segment_songs_flat.extend(split_song_titles(raw_song))

        song_idx = 0
        for idx, raw_song in enumerate(segment.songs):
            is_last = (idx == len(segment.songs) - 1)
            for title in split_song_titles(raw_song):
                append_track_with_injection(
                    title,
                    is_set_ender=is_last,
                    canonical_set=canonical,
                    current_segment_songs=segment_songs_flat,
                    current_song_index=song_idx,
                    segment_label=segment.label
                )
                song_idx += 1

    if encore:
        # Flatten encore songs for indexing
        encore_songs_flat = []
        for raw_song in encore.songs:
            encore_songs_flat.extend(split_song_titles(raw_song))

        song_idx = 0
        for idx, raw_song in enumerate(encore.songs):
            is_last = (idx == len(encore.songs) - 1)
            for title in split_song_titles(raw_song):
                append_track_with_injection(
                    title,
                    is_set_ender=is_last,
                    canonical_set="encore",
                    current_segment_songs=encore_songs_flat,
                    current_song_index=song_idx,
                    segment_label=encore.label
                )
                song_idx += 1



@dataclass
class PlaylistTrackAssembly:
    """State and ordered callbacks for selecting base tracks and segues."""

    db_session: Session
    catalog: SongCatalog
    rng: Random
    strict: bool
    track_selector: Callable
    feature_store: object
    same_show_segues: bool
    generated_setlist: object
    jamminess: Optional[float]
    set_lengths: Optional[Dict[str, int]]
    max_segues_per_set: int
    song_duration_stats: Dict[str, object]
    track_cache: Dict[str, Optional[SongDisplay]] = field(default_factory=dict)
    missing: Dict[str, int] = field(default_factory=dict)
    segue_context: Dict[str, int] = field(default_factory=dict)
    songs_to_skip: Set[Tuple[str, str]] = field(default_factory=set)
    segues_per_segment: Dict[str, int] = field(default_factory=dict)
    first_track_url: Optional[str] = None
    injection: SegueInjection = field(init=False)

    def __post_init__(self) -> None:
        self.injection = SegueInjection(
            db_session=self.db_session,
            catalog=self.catalog,
            rng=self.rng,
            feature_store=self.feature_store,
            track_cache=self.track_cache,
        )

    def select_display(
        self,
        song_title: str,
        *,
        is_set_ender: bool,
        canonical_set: Optional[str],
        segment_label: Optional[str],
    ) -> Optional[SongDisplay]:
        normalized = normalize_title(song_title)
        if normalized in self.track_cache:
            return self.track_cache[normalized]

        entry = self.catalog.by_title.get(normalized)
        if entry is None:
            self.missing[song_title] = self.missing.get(song_title, 0) + 1
            self.track_cache[normalized] = None
            if self.strict:
                raise PlaylistServiceError(f"No song metadata available for '{song_title}'.")
            return None

        display = self.track_selector(
            self.db_session,
            song_title=song_title,
            entry=entry,
            rng=self.rng,
            strict=self.strict,
            missing=self.missing,
            is_set_ender=is_set_ender,
            canonical_set=canonical_set,
            feature_store=self.feature_store,
            same_show_segues=self.same_show_segues,
            generated_setlist=self.generated_setlist,
            segue_context=self.segue_context,
            jamminess=self.jamminess,
            segues_per_segment=self.segues_per_segment,
            max_segues_per_set=self.max_segues_per_set,
            segment_label=segment_label,
        )
        self.track_cache[normalized] = display
        return display

    def append_track(
        self,
        song_title: str,
        *,
        is_set_ender: bool = False,
        canonical_set: Optional[str] = None,
        segment_label: Optional[str] = None,
    ) -> Optional[SongDisplay]:
        display = self.select_display(
            song_title,
            is_set_ender=is_set_ender,
            canonical_set=canonical_set,
            segment_label=segment_label,
        )
        if display is None or not display.mp3_url:
            return display

        if self.first_track_url is None:
            self.first_track_url = display.mp3_url
        self.injection.inject_rare(display)
        if display.mandatory_pattern_songs and segment_label:
            self.injection.inject_mandatory(display, song_title, segment_label)
        return display

    def append_track_with_injection(
        self,
        song_title: str,
        is_set_ender: bool = False,
        canonical_set: Optional[str] = None,
        current_segment_songs: Optional[List[str]] = None,
        current_song_index: int = 0,
        segment_label: Optional[str] = None,
    ) -> None:
        if segment_label and (segment_label, song_title) in self.songs_to_skip:
            logger.info("⏭️  Skipping %s/%s (lottery compensation)", segment_label, song_title)
            return
        if segment_label and (segment_label, song_title) in self.injection.mandatory_injected_songs:
            logger.info("⏭️  Skipping %s/%s (already injected as mandatory continuation)", segment_label, song_title)
            return

        self.append_track(
            song_title,
            is_set_ender=is_set_ender,
            canonical_set=canonical_set,
            segment_label=segment_label,
        )
        display = self.track_cache.get(normalize_title(song_title))
        skips = compensate_for_continuations(
            segment_label,
            current_segment_songs,
            song_title,
            display,
            self.set_lengths,
            catalog=self.catalog,
            song_duration_stats=self.song_duration_stats,
            continuation_records=self.injection.continuation_records,
        )
        self.songs_to_skip.update(skips)


def _song_slugs_for_segments(
    segments: Sequence[SetSegment], encore: Optional[SetSegment], catalog: SongCatalog
) -> List[str]:
    slugs = []
    for segment in [*segments, *([encore] if encore else [])]:
        for raw_song in segment.songs:
            for title in split_song_titles(raw_song):
                entry = catalog.by_title.get(normalize_title(title))
                if entry:
                    slugs.append(entry.slug)
    return slugs


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
    """Select tracks in order, then build sections and the optional M3U."""
    if track_selector is None:
        raise ValueError("track_selector callable is required.")

    song_stats = (
        _load_song_duration_stats(db_session, _song_slugs_for_segments(segments, encore, catalog))
        if set_lengths
        else {}
    )
    assembly = PlaylistTrackAssembly(
        db_session=db_session,
        catalog=catalog,
        rng=rng,
        strict=strict,
        track_selector=track_selector,
        feature_store=feature_store,
        same_show_segues=same_show_segues,
        generated_setlist=generated_setlist,
        jamminess=jamminess,
        set_lengths=set_lengths,
        max_segues_per_set=max_segues_per_set,
        song_duration_stats=song_stats,
    )
    _process_segment_tracks(segments, encore, assembly.append_track_with_injection)

    sections = _build_sections(
        db_session,
        segments,
        encore,
        catalog=catalog,
        track_cache=assembly.track_cache,
        songs_to_skip=assembly.songs_to_skip,
        mandatory_injected_songs=assembly.injection.mandatory_injected_songs,
        feature_store=feature_store,
        rng=rng,
        continuation_records=assembly.injection.continuation_records,
        continuation_lookup_ids=assembly.injection.continuation_lookup_ids,
        attempted_continuation_ids=assembly.injection.attempted_continuation_ids,
    )
    return PlaylistArtifacts(
        sections=sections,
        first_track_url=assembly.first_track_url,
        m3u_text=_render_m3u(sections, include_m3u),
        missing_tracks=list(assembly.missing.keys()),
        segue_notes=assembly.injection.notes,
    )
