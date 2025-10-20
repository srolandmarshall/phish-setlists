"""High-level orchestration for setlist generation and media artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from random import Random, SystemRandom
from typing import Dict, List, Optional, Sequence, Tuple

import requests
from sqlalchemy.orm import Session

from ..constants import ERA_DEFINITIONS
from ..generator import GeneratedSetlist, SetlistGenerator, random_set_lengths
from ..generator.core import SetSegment
from ..generator.html import PlaylistLink, PlaylistSection, build_html_markup


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


def populate_slug_cache(
    session: requests.Session,
    slug_cache: Dict[str, Optional[str]],
    *,
    strict: bool,
) -> None:
    if slug_cache.get("__loaded"):
        return

    page = 1
    while True:
        params = {"page": page, "per_page": 1000}
        try:
            resp = session.get("https://phish.in/api/v2/songs.json", params=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - network defensive
            slug_cache["__loaded"] = True
            if strict:
                raise PlaylistServiceError("Unable to load song catalog from phish.in") from exc
            return

        data = resp.json()
        for song in data.get("songs", []):
            key = normalize_title(song.get("title", ""))
            if key and key not in slug_cache:
                slug_cache[key] = song.get("slug")
            alias = song.get("alias")
            if alias:
                alias_key = normalize_title(alias)
                if alias_key and alias_key not in slug_cache:
                    slug_cache[alias_key] = song.get("slug")

        total_pages = data.get("total_pages") or page
        if page >= total_pages:
            break
        page += 1

    slug_cache["__loaded"] = True


def fetch_song_slug(
    title: str,
    session: requests.Session,
    slug_cache: Dict[str, Optional[str]],
    *,
    strict: bool,
) -> Optional[str]:
    key = normalize_title(title)
    if key in slug_cache:
        return slug_cache[key]

    populate_slug_cache(session, slug_cache, strict=strict)
    slug_cache.setdefault(key, None)
    return slug_cache[key]


def fetch_track_for_song(
    title: str,
    session: requests.Session,
    track_cache: Dict[str, Optional[SongDisplay]],
    slug_cache: Dict[str, Optional[str]],
    rng: Random,
    *,
    strict: bool,
) -> Optional[SongDisplay]:
    key = normalize_title(title)
    if key in track_cache:
        return track_cache[key]

    slug = fetch_song_slug(title, session, slug_cache, strict=strict)
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
    except requests.RequestException as exc:  # pragma: no cover - network defensive
        if strict:
            raise PlaylistServiceError(f"Unable to fetch tracks for '{title}' from phish.in") from exc
        track_cache[key] = None
        return None

    tracks = resp.json().get("tracks", [])
    candidates = [
        track
        for track in tracks
        if track.get("mp3_url") and track.get("audio_status") in {"complete", "partial"}
    ]
    track = rng.choice(candidates) if candidates else (tracks[0] if tracks else None)
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


def prepare_playlist_artifacts(
    segments: Sequence[SetSegment],
    encore: Optional[SetSegment],
    *,
    rng: Random,
    include_m3u: bool,
    strict: bool,
    http_session: Optional[requests.Session] = None,
) -> PlaylistArtifacts:
    session = http_session or requests.Session()
    created_session = http_session is None

    track_cache: Dict[str, Optional[SongDisplay]] = {}
    slug_cache: Dict[str, Optional[str]] = {}
    missing: Dict[str, int] = {}
    playlist_lines: List[str] = ["#EXTM3U"] if include_m3u else []
    first_track_url: Optional[str] = None

    def append_track(song_title: str) -> None:
        nonlocal first_track_url

        track = fetch_track_for_song(
            song_title,
            session,
            track_cache,
            slug_cache,
            rng,
            strict=strict,
        )

        if not track or not track.mp3_url:
            missing[song_title] = missing.get(song_title, 0) + 1
            if include_m3u:
                playlist_lines.append(f"#EXTINF:-1,{song_title} (unavailable)")
                playlist_lines.append(f"# Missing: {song_title}")
            return

        duration_sec = track.duration_seconds if track.duration_seconds is not None else -1
        show_date = track.show_date or "unknown date"

        if include_m3u:
            playlist_lines.append(f"#EXTINF:{duration_sec},{song_title} [{show_date}]")
            playlist_lines.append(track.mp3_url)

        if first_track_url is None:
            first_track_url = track.mp3_url

    try:
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
                    track = track_cache.get(key)
                    if track:
                        rows.append(track)
                    else:
                        rows.append(SongDisplay(title=title))
            sections.append((segment.label, rows))

        if encore:
            encore_rows: List[SongDisplay] = []
            for raw_song in encore.songs:
                for title in split_song_titles(raw_song):
                    key = normalize_title(title)
                    track = track_cache.get(key)
                    if track:
                        encore_rows.append(track)
                    else:
                        encore_rows.append(SongDisplay(title=title))
            sections.append((encore.label, encore_rows))

        m3u_text = "\n".join(playlist_lines) if include_m3u else None
        missing_titles = list(missing.keys())
        return PlaylistArtifacts(
            sections=sections,
            first_track_url=first_track_url,
            m3u_text=m3u_text,
            missing_tracks=missing_titles,
        )
    finally:
        if created_session:
            session.close()


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
        playlist_artifacts = prepare_playlist_artifacts(
            generated.sets,
            generated.encore,
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
            note = f"Playlist missing audio for {title} on phish.in"
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
