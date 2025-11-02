"""FastAPI application exposing the setlist generator."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.venue import Venue
from ..service import PlaylistServiceError, generate_show
from ..service.generation import GenerationRequest  # re-export convenience
from .dependencies import get_session
from .factories import build_generation_request
from .schemas import (
    GenerateRequestModel,
    GenerateResponse,
    HealthResponse,
    VenueModel,
)
from .serializers import result_to_response

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


@app.get("/", tags=["status"])
def root() -> dict:
    """API root endpoint."""
    return {
        "name": "Inphinite - The Phish Setlist Generator API",
        "version": "0.2.0",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["status"])
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/venue/random", response_model=VenueModel, tags=["venue"])
def random_venue(session: Session = Depends(get_session)) -> VenueModel:
    """Get a random venue from the database."""
    venue = session.query(Venue).order_by(func.random()).limit(1).first()
    if not venue:
        raise HTTPException(status_code=404, detail="No venues found in database")
    return VenueModel(
        id=venue.id,
        name=venue.name,
        city=venue.city,
        state=venue.state,
        country=venue.country,
        slug=venue.slug,
        shows_count=venue.shows_count,
        latitude=venue.latitude,
        longitude=venue.longitude,
        abbrev=venue.abbrev,
    )


@app.get("/venue/random", response_model=VenueModel, tags=["venue"])
def random_venue(session: Session = Depends(get_session)) -> VenueModel:
    """Get a random venue from the database."""
    venue = session.query(Venue).order_by(func.random()).limit(1).first()
    if not venue:
        raise HTTPException(status_code=404, detail="No venues found in database")
    return VenueModel(
        id=venue.id,
        name=venue.name,
        city=venue.city,
        state=venue.state,
        country=venue.country,
        slug=venue.slug,
        shows_count=venue.shows_count,
        latitude=venue.latitude,
        longitude=venue.longitude,
        abbrev=venue.abbrev,
    )


@app.post("/generate", response_model=GenerateResponse, tags=["generation"])
def generate_endpoint(
    payload: GenerateRequestModel,
    session: Session = Depends(get_session),
) -> GenerateResponse:
    generation_request = build_generation_request(
        payload,
        include_playlist=payload.include_playlist,
        fail_on_playlist_error=payload.include_playlist,
    )

    try:
        result = generate_show(session, generation_request)
    except PlaylistServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    response_payload = result_to_response(result)
    return response_payload


__all__ = [
    "app",
    "GenerateRequestModel",
    "GenerateResponse",
    "HealthResponse",
    "VenueModel",
]
