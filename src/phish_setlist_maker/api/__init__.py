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
    version="0.2.1",
    description="""
Generate authentic Phish setlists with ML-enhanced song selection, weighted set closers, and intelligent frequency caps.

## New in v0.2.1: Segue Groups
Songs that traditionally segue together (like Mike's Song → I Am Hydrogen → Weekapaug Groove) are now kept from the same show performance, preserving the authentic segue experience.

### Features:
- **Mandatory Segues**: Songs that almost always appear together (≥50 occurrences)
- **Lottery Tickets**: Rare one-off segues (5% injection rate) that bring famous historical moments back to life
  - **Note**: Lottery tickets only appear when `same_show_segues=true` to ensure authentic same-show continuations
- **Track-Level Selection**: Actual performances, not just song titles, for authentic authenticity
- **Rich Segue Metadata**: Each track includes full segue pattern, rarity score, and performance history

### Request Parameter: `same_show_segues`
- **Default**: `false` - Current behavior (segue songs may be from different shows, no lottery tickets)
- **When true**:
  - Ensures songs in mandatory segues come from the same show performance
  - Enables lottery ticket injection (5% chance) for rare historical segues
  - Example: Mike's Song → I Am Hydrogen → Weekapaug Groove will all be from the same 2024-07-15 show, not mixed from different performances

### Response Segue Metadata
Each track in the response includes segue context via these fields:
- `is_segue`: Whether this track is part of a segue
- `segue_type`: "mandatory" (always together), "rare" (historical <50 occurrences), or "lottery_ticket" (rare with high community engagement)
- `segue_pattern`: Full segue sequence (e.g., "Steam -> Poor Heart")
- `segue_position`: Position in sequence (1st, 2nd, 3rd track of segue)
- `segue_group_id`: Unique ID grouping all songs in this segue
- `historical_occurrences`: How many times this segue has occurred
- `rarity_score`: 0.0-1.0 score (lower = rarer)

### Segue Notes in Metadata
The response includes segue-related notes in `metadata.notes`:
- **Mandatory Segues**: When enabled, notes indicate which segues were preserved as complete patterns from the same show
- **Lottery Tickets**: 🎰 symbols indicate rare segues that were randomly injected (e.g., "🎰 Lottery ticket! Rare Tweezer → Prince Caspian from 08/22/2015")

These notes provide insight into what makes the generated setlist authentic to Phish's actual performance history.
    """,
)

# CORS middleware for local development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://inphinite.sammarshall.us",
        "https://inphinite-phront-end.fly.dev",
        "https://inphinite-staging.fly.dev",
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
        "version": "0.2.1",
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
