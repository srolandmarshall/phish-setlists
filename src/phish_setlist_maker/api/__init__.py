"""FastAPI application exposing the setlist generator."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..db import get_session_factory
from ..generator.core import GenerationMetadata
from ..service import (
    GenerationRequest,
    GenerationResult,
    PlaylistArtifacts,
    PlaylistServiceError,
    SegmentDetails,
    SongDisplay,
    generate_show,
)


def _get_session() -> Iterable[Session]:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class SongModel(BaseModel):
    title: str
    mp3_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    origin: Optional[str] = None
    show_date: Optional[str] = None


class SegmentModel(BaseModel):
    label: str
    songs: list[str]
    tracks: list[SongModel]


class MetadataModel(BaseModel):
    reference_date: date
    cutoff_date: date
    era: Optional[str]
    year: Optional[int]
    notes: list[str]


class PlaylistSectionModel(BaseModel):
    title: str
    tracks: list[SongModel]


class PlaylistModel(BaseModel):
    sections: list[PlaylistSectionModel]
    first_track_url: Optional[str] = None
    m3u_text: Optional[str] = None
    missing_tracks: list[str]


class HTMLModel(BaseModel):
    markup: str
    stylesheet: str


class GenerateResponse(BaseModel):
    seed: int
    generated_at: datetime
    metadata: MetadataModel
    sets: list[SegmentModel]
    encore: Optional[SegmentModel]
    playlist: Optional[PlaylistModel]
    html: Optional[HTMLModel]


class GenerateRequestModel(BaseModel):
    reference_date: Optional[date] = None
    era: Optional[Literal["1.0", "2.0", "3.0", "4.0"]] = None
    year: Optional[int] = Field(default_factory=lambda: datetime.utcnow().year)
    num_sets: int = Field(default=2, ge=2, le=3)
    include_encore: bool = True
    set_lengths: Optional[Dict[str, int]] = None
    allow_previous_show: bool = True
    seed: Optional[int] = None
    include_playlist: bool = True
    include_html: bool = False

    @field_validator("set_lengths")
    @classmethod
    def _validate_set_lengths(cls, value: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]:
        if value is None:
            return None
        allowed = {"set1", "set2", "set3", "encore"}
        for key in value:
            if key.lower() not in allowed:
                raise ValueError(f"Unsupported set label '{key}'. Allowed labels: {', '.join(sorted(allowed))}.")
        return {key.lower(): int(count) for key, count in value.items()}


def _metadata_to_model(metadata: GenerationMetadata) -> MetadataModel:
    return MetadataModel(
        reference_date=metadata.reference_date,
        cutoff_date=metadata.cutoff_date,
        era=metadata.era,
        year=metadata.year,
        notes=list(metadata.notes),
    )


def _segment_to_model(segment: SegmentDetails) -> SegmentModel:
    return SegmentModel(
        label=segment.label,
        songs=list(segment.songs),
        tracks=[SongModel(**song.__dict__) for song in segment.tracks],
    )


def _songdisplay_to_model(song: SongDisplay) -> SongModel:
    return SongModel(
        title=song.title,
        mp3_url=song.mp3_url,
        duration_seconds=song.duration_seconds,
        origin=song.origin,
        show_date=song.show_date,
    )


def _playlist_to_model(artifacts: PlaylistArtifacts) -> PlaylistModel:
    sections = [
        PlaylistSectionModel(
            title=title,
            tracks=[_songdisplay_to_model(song) for song in songs],
        )
        for title, songs in artifacts.sections
    ]
    return PlaylistModel(
        sections=sections,
        first_track_url=artifacts.first_track_url,
        m3u_text=artifacts.m3u_text,
        missing_tracks=list(artifacts.missing_tracks),
    )


def _result_to_response(result: GenerationResult) -> GenerateResponse:
    sets = [_segment_to_model(segment) for segment in result.segments]
    encore = _segment_to_model(result.encore) if result.encore else None

    playlist = _playlist_to_model(result.playlist) if result.playlist else None
    html = None
    if result.html:
        html = HTMLModel(markup=result.html.markup, stylesheet=result.html.stylesheet)

    return GenerateResponse(
        seed=result.seed,
        generated_at=result.generated_at,
        metadata=_metadata_to_model(result.generated.metadata),
        sets=sets,
        encore=encore,
        playlist=playlist,
        html=html,
    )


def _create_generation_request(
    model: GenerateRequestModel,
    *,
    include_playlist: bool,
    include_html: bool,
    fail_on_playlist_error: bool,
    stylesheet_href: Optional[str] = None,
    script_src: Optional[str] = None,
) -> GenerationRequest:
    return GenerationRequest(
        reference_date=model.reference_date,
        era=model.era,
        year=model.year,
        num_sets=model.num_sets,
        include_encore=model.include_encore,
        set_lengths=model.set_lengths,
        allow_previous_show=model.allow_previous_show,
        seed=model.seed,
        include_playlist=include_playlist,
        include_html=include_html,
        prefetch_track_metadata=include_playlist or include_html,
        fail_on_playlist_error=fail_on_playlist_error,
        html_stylesheet_href=stylesheet_href,
        html_script_src=script_src,
    )


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_AVAILABLE = STATIC_DIR.exists()
STATIC_STYLESHEET = "/static/phish-setlist.css"
STATIC_SCRIPT = "/static/player.js"

app = FastAPI(title="Phish Setlist Maker API", version="0.1.0")
if STATIC_AVAILABLE:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health", response_model=HealthResponse, tags=["status"])
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/generate", response_class=HTMLResponse, tags=["generation"])
def generate_html(
    reference_date: Optional[date] = Query(None),
    era: Optional[Literal["1.0", "2.0", "3.0", "4.0"]] = Query(None),
    year: Optional[int] = Query(None),
    num_sets: int = Query(2, ge=2, le=3),
    include_encore: bool = Query(True),
    allow_previous_show: bool = Query(False),
    seed: Optional[int] = Query(None),
    session: Session = Depends(_get_session),
) -> HTMLResponse:
    payload = GenerateRequestModel(
        reference_date=reference_date,
        era=era,
        year=year,
        num_sets=num_sets,
        include_encore=include_encore,
        allow_previous_show=allow_previous_show,
        seed=seed,
        include_playlist=True,
        include_html=True,
    )

    generation_request = _create_generation_request(
        payload,
        include_playlist=True,
        include_html=True,
        fail_on_playlist_error=False,
        stylesheet_href=STATIC_STYLESHEET if STATIC_AVAILABLE else None,
        script_src=STATIC_SCRIPT if STATIC_AVAILABLE else None,
    )

    try:
        result = generate_show(session, generation_request)
    except PlaylistServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not result.html:
        raise HTTPException(status_code=500, detail="Failed to render HTML output.")

    return HTMLResponse(content=result.html.markup)


@app.post("/generate", response_model=GenerateResponse, tags=["generation"])
def generate_endpoint(
    payload: GenerateRequestModel,
    request: Request,
    session: Session = Depends(_get_session),
) -> Response:
    format_param = request.query_params.get("format", "").lower()
    accept_header = request.headers.get("accept", "")
    wants_html = False
    if format_param in {"html", "text/html"}:
        wants_html = True
    elif format_param in {"json", "application/json"}:
        wants_html = False
    else:
        # Rails-style negotiation: prefer HTML when explicitly requested, otherwise default to JSON.
        lowered = accept_header.lower()
        if "text/html" in lowered and "application/json" not in lowered:
            wants_html = True

    effective_include_html = payload.include_html or wants_html
    effective_include_playlist = payload.include_playlist or wants_html

    stylesheet_href = STATIC_STYLESHEET if (effective_include_html and STATIC_AVAILABLE) else None
    script_src = STATIC_SCRIPT if (effective_include_playlist and STATIC_AVAILABLE) else None

    generation_request = _create_generation_request(
        payload,
        include_playlist=effective_include_playlist,
        include_html=effective_include_html,
        fail_on_playlist_error=effective_include_playlist,
        stylesheet_href=stylesheet_href,
        script_src=script_src,
    )

    try:
        result = generate_show(session, generation_request)
    except PlaylistServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if wants_html:
        if not result.html:
            raise HTTPException(status_code=500, detail="Failed to render HTML output.")
        return HTMLResponse(content=result.html.markup)

    response_payload = _result_to_response(result)
    return response_payload
