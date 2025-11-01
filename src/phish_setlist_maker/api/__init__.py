"""FastAPI application exposing the setlist generator."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from ..service import PlaylistServiceError, generate_show
from ..service.generation import GenerationRequest  # re-export convenience
from .dependencies import get_session
from .factories import build_generation_request
from .schemas import (
    GenerateRequestModel,
    GenerateResponse,
    HealthResponse,
)
from .serializers import result_to_response

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_AVAILABLE = STATIC_DIR.exists()
STATIC_STYLESHEET = "/static/phish-setlist.css"
STATIC_SCRIPT = "/static/player.js"

app = FastAPI(
    title="Inphinite - The Phish Setlist Generator API",
    version="0.2.0",
    description="Generate authentic Phish setlists with ML-enhanced song selection, weighted set closers, and intelligent frequency caps.",
)

# CORS middleware for local development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://inphinite.sammarshall.us",
        "https://inphinite-phront-end.fly.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_AVAILABLE:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse, tags=["status"])
def root() -> HTMLResponse:
    """Landing page with link to generate."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
    # Fallback if static file missing
    return HTMLResponse(
        content="<h1>Inphinite API</h1><p><a href='/docs'>API Docs</a></p>"
    )


@app.get("/health", response_model=HealthResponse, tags=["status"])
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/features", response_class=HTMLResponse, tags=["status"])
def features() -> HTMLResponse:
    """Features page with comprehensive feature list."""
    features_path = STATIC_DIR / "features.html"
    if features_path.exists():
        return HTMLResponse(content=features_path.read_text())
    # Fallback if static file missing
    return HTMLResponse(content="<h1>Features</h1><p><a href='/'>Home</a></p>")


@app.get("/generate", response_class=HTMLResponse, tags=["generation"])
def generate_html(
    reference_date: Optional[date] = Query(None),
    era: Optional[Literal["1.0", "2.0", "3.0", "4.0"]] = Query(None),
    year: Optional[int] = Query(None),
    num_sets: int = Query(2, ge=2, le=3),
    include_encore: bool = Query(True),
    allow_previous_show: bool = Query(True),
    seed: Optional[int] = Query(None),
    use_ml_features: bool = Query(
        True, description="Enable ML-driven feature adjustments"
    ),
    ml_placement_weight: float = Query(
        0.3, ge=0.0, le=1.0, description="Weight for ML placement probabilities"
    ),
    ml_transition_bonus: float = Query(
        0.1, ge=0.0, le=1.0, description="Bonus for ML transition lifts"
    ),
    jamminess: Optional[float] = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description="Jam intensity override (0=tight/concise, 0.5=balanced, 1.0=max jam).",
    ),
    session: Session = Depends(get_session),
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
        use_ml_features=use_ml_features,
        ml_placement_weight=ml_placement_weight,
        ml_transition_bonus=ml_transition_bonus,
        jamminess=jamminess,
    )

    generation_request = build_generation_request(
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
    session: Session = Depends(get_session),
) -> Response:
    format_param = request.query_params.get("format", "").lower()
    accept_header = request.headers.get("accept", "")
    wants_html = False
    if format_param in {"html", "text/html"}:
        wants_html = True
    elif format_param in {"json", "application/json"}:
        wants_html = False
    else:
        lowered = accept_header.lower()
        if "text/html" in lowered and "application/json" not in lowered:
            wants_html = True

    effective_include_html = payload.include_html or wants_html
    effective_include_playlist = payload.include_playlist or wants_html

    stylesheet_href = (
        STATIC_STYLESHEET if (effective_include_html and STATIC_AVAILABLE) else None
    )
    script_src = (
        STATIC_SCRIPT if (effective_include_playlist and STATIC_AVAILABLE) else None
    )

    generation_request = build_generation_request(
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

    response_payload = result_to_response(result)
    return response_payload


__all__ = [
    "app",
    "GenerateRequestModel",
    "GenerateResponse",
    "HealthResponse",
]
