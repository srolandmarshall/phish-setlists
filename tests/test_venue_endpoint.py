"""Tests for venue API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from phish_setlist_maker.api import app
from phish_setlist_maker.api.dependencies import get_session
from phish_setlist_maker.models.venue import Venue


@pytest.fixture()
def api_client(db_session) -> TestClient:
    """Provide a FastAPI test client with a mocked session dependency."""

    def override_session():
        try:
            yield db_session
        finally:
            db_session.rollback()

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        client.close()


def test_random_venue_returns_venue(api_client: TestClient, db_session) -> None:
    """Test that /venue/random returns a random venue."""
    # Add some venues to the database
    venue1 = Venue(
        name="Madison Square Garden",
        city="New York",
        state="NY",
        country="USA",
        slug="madison-square-garden",
        shows_count=42,
        latitude=40.7505,
        longitude=-73.9934,
        abbrev="MSG",
    )
    venue2 = Venue(
        name="Red Rocks Amphitheatre",
        city="Morrison",
        state="CO",
        country="USA",
        slug="red-rocks-amphitheatre",
        shows_count=15,
        latitude=39.6653,
        longitude=-105.2054,
    )
    db_session.add_all([venue1, venue2])
    db_session.commit()

    response = api_client.get("/venue/random")

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "name" in data
    assert "city" in data
    assert "state" in data
    assert "country" in data
    assert "slug" in data
    assert "shows_count" in data
    assert data["name"] in ["Madison Square Garden", "Red Rocks Amphitheatre"]


def test_random_venue_returns_404_when_no_venues(api_client: TestClient) -> None:
    """Test that /venue/random returns 404 when database is empty."""
    response = api_client.get("/venue/random")

    assert response.status_code == 404
    assert response.json()["detail"] == "No venues found in database"


def test_random_venue_includes_all_fields(api_client: TestClient, db_session) -> None:
    """Test that /venue/random includes all venue fields."""
    venue = Venue(
        name="The Gorge Amphitheatre",
        city="George",
        state="WA",
        country="USA",
        slug="the-gorge-amphitheatre",
        shows_count=10,
        latitude=47.0989,
        longitude=-119.9728,
        abbrev="Gorge",
    )
    db_session.add(venue)
    db_session.commit()

    response = api_client.get("/venue/random")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "The Gorge Amphitheatre"
    assert data["city"] == "George"
    assert data["state"] == "WA"
    assert data["country"] == "USA"
    assert data["slug"] == "the-gorge-amphitheatre"
    assert data["shows_count"] == 10
    assert data["latitude"] == pytest.approx(47.0989)
    assert data["longitude"] == pytest.approx(-119.9728)
    assert data["abbrev"] == "Gorge"


def test_random_venue_handles_missing_optional_fields(api_client: TestClient, db_session) -> None:
    """Test that /venue/random handles venues with missing optional fields."""
    venue = Venue(
        name="Unknown Venue",
        city="Unknown City",
        state="XX",
        country="USA",
        slug="unknown-venue",
        shows_count=1,
        latitude=None,
        longitude=None,
        abbrev=None,
    )
    db_session.add(venue)
    db_session.commit()

    response = api_client.get("/venue/random")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Unknown Venue"
    assert data["latitude"] is None
    assert data["longitude"] is None
    assert data["abbrev"] is None
