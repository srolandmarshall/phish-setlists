"""FastAPI application exposing the setlist generator."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
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

app = FastAPI(title="Phish Setlist Maker API", version="0.1.0")
if STATIC_AVAILABLE:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse, tags=["status"])
def root() -> HTMLResponse:
    """Landing page with link to generate."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phish Setlist Maker</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            padding: 60px 40px;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 500px;
            text-align: center;
        }
        h1 {
            font-size: 2.5em;
            color: #333;
            margin-bottom: 20px;
        }
        p {
            font-size: 1.1em;
            color: #666;
            margin-bottom: 40px;
            line-height: 1.6;
        }
        .btn {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px 48px;
            text-decoration: none;
            border-radius: 8px;
            font-size: 1.2em;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }
        .links {
            margin-top: 30px;
            padding-top: 30px;
            border-top: 1px solid #eee;
        }
        .links a {
            color: #667eea;
            text-decoration: none;
            margin: 0 12px;
            font-size: 0.95em;
        }
        .links a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎸 Phish Setlist Maker</h1>
        <p>Generate AI-powered Phish setlists based on historical data and ML-driven placement probabilities.</p>
        <a href="/generate" class="btn">Generate Show</a>
        <div class="links">
            <a href="/docs">API Docs</a>
            <a href="/health">Status</a>
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html)


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
    allow_previous_show: bool = Query(True),
    seed: Optional[int] = Query(None),
    use_ml_features: bool = Query(True, description="Enable ML-driven feature adjustments"),
    ml_placement_weight: float = Query(0.3, ge=0.0, le=1.0, description="Weight for ML placement probabilities"),
    ml_transition_bonus: float = Query(0.1, ge=0.0, le=1.0, description="Bonus for ML transition lifts"),
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

    stylesheet_href = STATIC_STYLESHEET if (effective_include_html and STATIC_AVAILABLE) else None
    script_src = STATIC_SCRIPT if (effective_include_playlist and STATIC_AVAILABLE) else None

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
