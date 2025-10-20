"""High-level orchestration for setlist generation and media artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from random import Random, SystemRandom
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import re

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import ERA_DEFINITIONS
from ..generator import GeneratedSetlist, SetlistGenerator, random_set_lengths
from ..generator.core import SetSegment
from ..generator.html import PlaylistLink, PlaylistSection, build_html_markup
from ..models import Show, Song, SongTrack, Track


class PlaylistServiceError(RuntimeError):
    """Raised when auxiliary playlist services are unavailable."""


@dataclass(frozen=True)
class GenerationRequest:
    """Inputs used to produce a generated setlist."""

    reference_date: Optional[date] = None
    era: Optional[str] = None
    year: Optional[int] = None
    num_sets: int = 2
    include_encore: bool = True
    set_lengths: Optional[Dict[str, int]] = None
    allow_previous_show: bool = False
    seed: Optional[int] = None
    include_playlist: bool = False
    include_html: bool = False
    prefetch_track_metadata: bool = True
    fail_on_playlist_error: bool = False


@dataclass(frozen=True)
class SongDisplay:
    """Presentation-friendly metadata for a single song appearance."""

    title: str
    mp3_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    origin: Optional[str] = None
    show_date: Optional[str] = None

    @property
    def duration_label(self) -> Optional[str]:
        if self.duration_seconds is None or self.duration_seconds < 0:
            return None
        minutes, seconds = divmod(self.duration_seconds, 60)
        return f"{minutes}:{seconds:02d}"


@dataclass(slots=True)
class SegmentDetails:
    """Expanded view of a generated segment (raw titles + flattened songs)."""

    label: str
    songs: List[str]
    tracks: List[SongDisplay]


@dataclass(slots=True)
class PlaylistArtifacts:
    """In-memory representation of playlist data and track metadata."""

    sections: List[Tuple[str, List[SongDisplay]]]
    first_track_url: Optional[str]
    m3u_text: Optional[str]
    missing_tracks: List[str]


@dataclass(slots=True)
class HTMLArtifact:
    """Rendered HTML markup plus reference to the stylesheet."""

    markup: str
    stylesheet: str = "phish-setlist.css"


@dataclass(slots=True)
class GenerationResult:
    """Full output of the generator, including optional media artifacts."""

    seed: int
    generated_at: datetime
    generated: GeneratedSetlist
    segments: List[SegmentDetails]
    encore: Optional[SegmentDetails]
    playlist: Optional[PlaylistArtifacts]
    html: Optional[HTMLArtifact]


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


@dataclass(frozen=True)
class CandidateTrack:
    slug: str
    duration: Optional[int]
    show_date: Optional[date]


def infer_default_era(year: Optional[int]) -> Optional[str]:
    if year is None:
        return "4.0"

    selected: Optional[str] = None
    for label, definition in sorted(ERA_DEFINITIONS.items(), key=lambda item: item[1].start):
        if year >= definition.start.year:
            selected = label

    if selected is None:
        selected = min(ERA_DEFINITIONS.items(), key=lambda item: item[1].start)[0]

    return selected


def resolve_era(year: Optional[int], requested_era: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Determine the effective era, adjusting when the year predates the request."""

    if requested_era:
        definition = ERA_DEFINITIONS[requested_era]
        if year is not None and year < definition.start.year:
            inferred = infer_default_era(year)
            if inferred != requested_era:
                note = f"Adjusted era to {inferred} because year {year} predates era {requested_era}."
                return inferred, note
        return requested_era, None

    inferred = infer_default_era(year)
    return inferred, None


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


def determine_origin_from_entry(entry: SongCatalogEntry) -> Optional[str]:
    if entry.original:
        return "Phish original"

    artist = entry.artist.strip() if entry.artist else None
    if artist:
        if artist.lower() == "phish":
            return "Phish original"
        return f"Originally by {artist}"

    if entry.alias:
        alias = _parse_aliases(entry.alias)
        if alias:
            return f"Alias: {alias[0]}"

    return None


def _parse_aliases(raw_alias: Optional[str]) -> List[str]:
    if not raw_alias:
        return []
    # Alias fields occasionally contain multiple entries separated by punctuation.
    parts = re.split(r"[;/,]+", raw_alias)
    return [part.strip() for part in parts if part.strip()]


def build_song_catalog(db_session: Session) -> SongCatalog:
    """Construct lookups for titles/aliases to song metadata."""

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

    return SongCatalog(by_title=by_title, by_slug=by_slug)


def _query_tracks_for_song(db_session: Session, song_slug: str, limit: int = 30) -> List[CandidateTrack]:
    stmt = (
        select(
            Track.slug,
            Track.duration,
            Show.date.label("show_date"),
        )
        .join(SongTrack, SongTrack.track_id == Track.id)
        .join(Song, SongTrack.song_id == Song.id)
        .outerjoin(Show, Show.id == Track.show_id)
        .where(Song.slug == song_slug)
        .order_by(Track.likes_count.desc(), Track.id.desc())
        .limit(limit)
    )
    rows = db_session.execute(stmt).all()
    return [CandidateTrack(slug=row.slug, duration=row.duration, show_date=row.show_date) for row in rows]


def _fetch_remote_track_metadata(track_slug: str, *, strict: bool) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    url = f"https://phish.in/api/v2/tracks/{track_slug}.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        if strict:
            raise PlaylistServiceError(f"Unable to fetch track metadata for '{track_slug}'.") from exc
        return None, None, None

    data = resp.json().get("track", {})
    mp3_url = data.get("mp3_url") or data.get("mp3")
    duration_raw = data.get("duration")
    duration_seconds: Optional[int]
    if isinstance(duration_raw, (int, float)):
        duration_seconds = int(duration_raw // 1000)
    else:
        duration_seconds = None
    show_date = data.get("show_date")
    return mp3_url, duration_seconds, show_date


def _select_track_display(
    db_session: Session,
    *,
    song_title: str,
    entry: SongCatalogEntry,
    rng: Random,
    strict: bool,
    missing: Dict[str, int],
) -> Optional[SongDisplay]:
    candidates = _query_tracks_for_song(db_session, entry.slug)
    if not candidates:
        missing[song_title] = missing.get(song_title, 0) + 1
        if strict:
            raise PlaylistServiceError(f"No track recordings available for '{song_title}'.")
        return None

    sample_size = min(len(candidates), 10)
    selection = rng.choice(candidates[:sample_size])

    mp3_url, remote_duration, remote_show_date = _fetch_remote_track_metadata(selection.slug, strict=strict)
    if not mp3_url:
        missing[song_title] = missing.get(song_title, 0) + 1
        if strict:
            raise PlaylistServiceError(f"Track '{song_title}' lacks an accessible audio URL.")
        return None

    duration_seconds = selection.duration if isinstance(selection.duration, int) and selection.duration > 0 else None
    if duration_seconds is None and isinstance(remote_duration, int) and remote_duration > 0:
        duration_seconds = remote_duration

    show_date = selection.show_date.isoformat() if selection.show_date else remote_show_date

    origin_text = determine_origin_from_entry(entry)

    return SongDisplay(
        title=song_title,
        mp3_url=mp3_url,
        duration_seconds=duration_seconds,
        origin=origin_text,
        show_date=show_date,
    )


def prepare_playlist_artifacts(
    db_session: Session,
    segments: Sequence[SetSegment],
    encore: Optional[SetSegment],
    *,
    catalog: SongCatalog,
    rng: Random,
    include_m3u: bool,
    strict: bool,
) -> PlaylistArtifacts:
    track_cache: Dict[str, Optional[SongDisplay]] = {}
    missing: Dict[str, int] = {}
    playlist_lines: List[str] = ["#EXTM3U"] if include_m3u else []
    first_track_url: Optional[str] = None

    def append_track(song_title: str) -> None:
        nonlocal first_track_url

        normalized = normalize_title(song_title)
        if normalized in track_cache:
            display = track_cache[normalized]
        else:
            entry = catalog.by_title.get(normalized)
            if entry is None:
                missing[song_title] = missing.get(song_title, 0) + 1
                track_cache[normalized] = None
                if strict:
                    raise PlaylistServiceError(f"No song metadata available for '{song_title}'.")
                display = None
            else:
                display = _select_track_display(
                    db_session,
                    song_title=song_title,
                    entry=entry,
                    rng=rng,
                    strict=strict,
                    missing=missing,
                )
                track_cache[normalized] = display

        if not display or not display.mp3_url:
            if include_m3u:
                playlist_lines.append(f"#EXTINF:-1,{song_title} (unavailable)")
                playlist_lines.append(f"# Missing: {song_title}")
            return

        duration_sec = display.duration_seconds if display.duration_seconds is not None else -1
        show_date = display.show_date or "unknown date"

        if include_m3u:
            playlist_lines.append(f"#EXTINF:{duration_sec},{song_title} [{show_date}]")
            playlist_lines.append(display.mp3_url)

        if first_track_url is None:
            first_track_url = display.mp3_url

    for segment in segments:
        for raw_song in segment.songs:
            for title in split_song_titles(raw_song):
                append_track(title)

    if encore:
        for raw_song in encore.songs:
            for title in split_song_titles(raw_song):
                append_track(title)

    sections: List[Tuple[str, List[SongDisplay]]] = []
    for segment in segments:
        rows: List[SongDisplay] = []
        for raw_song in segment.songs:
            for title in split_song_titles(raw_song):
                key = normalize_title(title)
                display = track_cache.get(key)
                if display:
                    rows.append(display)
                else:
                    entry = catalog.by_title.get(key)
                    origin = determine_origin_from_entry(entry) if entry else None
                    rows.append(SongDisplay(title=title, origin=origin))
        sections.append((segment.label, rows))

    if encore:
        encore_rows: List[SongDisplay] = []
        for raw_song in encore.songs:
            for title in split_song_titles(raw_song):
                key = normalize_title(title)
                display = track_cache.get(key)
                if display:
                    encore_rows.append(display)
                else:
                    entry = catalog.by_title.get(key)
                    origin = determine_origin_from_entry(entry) if entry else None
                    encore_rows.append(SongDisplay(title=title, origin=origin))
        sections.append((encore.label, encore_rows))

    m3u_text = "\n".join(playlist_lines) if include_m3u else None
    missing_titles = list(missing.keys())
    return PlaylistArtifacts(
        sections=sections,
        first_track_url=first_track_url,
        m3u_text=m3u_text,
        missing_tracks=missing_titles,
    )


def _expand_tracks(raw_songs: Sequence[str], track_lookup: Dict[str, SongDisplay]) -> List[SongDisplay]:
    expanded: List[SongDisplay] = []
    for raw_song in raw_songs:
        for title in split_song_titles(raw_song):
            key = normalize_title(title)
            track = track_lookup.get(key)
            if track:
                expanded.append(track)
            else:
                expanded.append(SongDisplay(title=title))
    return expanded


def _segments_to_playlist_sections(
    segments: Sequence[SegmentDetails],
    encore: Optional[SegmentDetails],
    *,
    include_audio_links: bool,
) -> List[PlaylistSection]:
    sections: List[PlaylistSection] = []
    for segment in segments:
        links = [
            PlaylistLink(
                title=song.title,
                mp3_url=song.mp3_url if include_audio_links else None,
                duration=song.duration_label,
                origin=song.origin,
            )
            for song in segment.tracks
        ]
        sections.append(PlaylistSection(title=segment.label, tracks=links))

    if encore:
        encore_links = [
            PlaylistLink(
                title=song.title,
                mp3_url=song.mp3_url if include_audio_links else None,
                duration=song.duration_label,
                origin=song.origin,
            )
            for song in encore.tracks
        ]
        sections.append(PlaylistSection(title=encore.label, tracks=encore_links))

    return sections


def generate_show(session: Session, request: GenerationRequest) -> GenerationResult:
    """Generate a setlist and any requested media artifacts."""

    effective_era, era_adjustment = resolve_era(request.year, request.era)

    seed = request.seed if request.seed is not None else SystemRandom().randint(0, 2**32 - 1)
    rng = Random(seed)
    length_rng = Random(seed)

    allow_previous_show = request.allow_previous_show
    current_year = datetime.now().year
    if request.year is not None and request.year < current_year and not request.allow_previous_show:
        allow_previous_show = True

    generator = SetlistGenerator(session, rng=rng)

    if request.set_lengths:
        set_lengths = dict(request.set_lengths)
    else:
        set_lengths = random_set_lengths(
            session,
            reference_date=request.reference_date,
            era=effective_era,
            year=request.year,
            num_sets=request.num_sets,
            include_encore=request.include_encore,
            rng=length_rng,
        )

    generated = generator.generate(
        reference_date=request.reference_date,
        era=effective_era,
        year=request.year,
        num_sets=request.num_sets,
        include_encore=request.include_encore,
        set_lengths=set_lengths,
        exclude_previous_show=not allow_previous_show,
    )

    metadata = generated.metadata
    if era_adjustment and era_adjustment not in metadata.notes:
        metadata.notes.append(era_adjustment)

    if allow_previous_show and not request.allow_previous_show:
        note = "Allowed previous show songs because the selected year predates the current year."
        if note not in metadata.notes:
            metadata.notes.append(note)

    generated_at = datetime.now(timezone.utc)

    needs_playlist = (
        request.include_playlist
        or request.include_html
        or request.prefetch_track_metadata
    )

    playlist_artifacts: Optional[PlaylistArtifacts] = None
    if needs_playlist:
        catalog = build_song_catalog(session)
        playlist_artifacts = prepare_playlist_artifacts(
            session,
            generated.sets,
            generated.encore,
            catalog=catalog,
            rng=rng,
            include_m3u=request.include_playlist,
            strict=request.fail_on_playlist_error,
        )

    track_lookup: Dict[str, SongDisplay] = {}
    if playlist_artifacts:
        for _, songs in playlist_artifacts.sections:
            for song in songs:
                track_lookup[normalize_title(song.title)] = song

    segments_details: List[SegmentDetails] = [
        SegmentDetails(
            label=segment.label,
            songs=list(segment.songs),
            tracks=_expand_tracks(segment.songs, track_lookup),
        )
        for segment in generated.sets
    ]

    encore_details: Optional[SegmentDetails] = None
    if generated.encore:
        encore_details = SegmentDetails(
            label=generated.encore.label,
            songs=list(generated.encore.songs),
            tracks=_expand_tracks(generated.encore.songs, track_lookup),
        )

    if request.include_playlist and playlist_artifacts:
        for title in playlist_artifacts.missing_tracks:
            note = f"Playlist missing audio for {title} in local archive"
            if note not in metadata.notes:
                metadata.notes.append(note)

    html_artifact: Optional[HTMLArtifact] = None
    if request.include_html:
        include_audio_links = bool(request.include_playlist and playlist_artifacts)
        sections_for_html = _segments_to_playlist_sections(
            segments_details,
            encore_details,
            include_audio_links=include_audio_links,
        )

        playlist_filename = "playlist.m3u" if include_audio_links else None
        first_track_url = (
            playlist_artifacts.first_track_url if include_audio_links and playlist_artifacts else None
        )

        html_markup = build_html_markup(
            generated,
            generated_at,
            playlist_filename=playlist_filename,
            first_track_url=first_track_url,
            playlist_sections=sections_for_html,
        )
        html_artifact = HTMLArtifact(markup=html_markup)

    return GenerationResult(
        seed=seed,
        generated_at=generated_at,
        generated=generated,
        segments=segments_details,
        encore=encore_details,
        playlist=playlist_artifacts,
        html=html_artifact,
    )
