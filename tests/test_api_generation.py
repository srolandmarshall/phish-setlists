"""Smoke tests for the FastAPI generation endpoint."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from phish_setlist_maker.api import app
from phish_setlist_maker.api.dependencies import get_session
from phish_setlist_maker.generator.core import GenerationMetadata, GeneratedSetlist, SetSegment
from phish_setlist_maker.service import (
    GenerationRequest,
    GenerationResult,
    SegmentDetails,
    SongDisplay,
)


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


def _fake_generation_result() -> GenerationResult:
    metadata = GenerationMetadata(
        reference_date=date(2024, 1, 1),
        cutoff_date=date(2024, 1, 1),
        era="4.0",
        year=2024,
        notes=[],
    )
    generated = GeneratedSetlist(
        sets=[SetSegment(label="Set 1", songs=["Maze"])],
        encore=None,
        metadata=metadata,
    )
    segments = [
        SegmentDetails(
            label="Set 1",
            songs=["Maze"],
            tracks=[SongDisplay(title="Maze")],
            duration_seconds=None,
        )
    ]
    return GenerationResult(
        seed=99,
        generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        generated=generated,
        segments=segments,
        encore=None,
        playlist=None,
    )


def test_post_generate_returns_json(api_client: TestClient, mocker: MockerFixture) -> None:
    mock_generate = mocker.patch(
        "phish_setlist_maker.api.generate_show",
        return_value=_fake_generation_result(),
    )

    response = api_client.post("/generate", json={"include_playlist": False})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["seed"] == 99
    mock_request: GenerationRequest = mock_generate.call_args.args[1]
    assert mock_request.include_playlist is False


def test_post_generate_forwards_jamminess(api_client: TestClient, mocker: MockerFixture) -> None:
    mock_generate = mocker.patch(
        "phish_setlist_maker.api.generate_show",
        return_value=_fake_generation_result(),
    )

    response = api_client.post("/generate", json={"jamminess": 0.42})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    mock_request: GenerationRequest = mock_generate.call_args.args[1]
    assert mock_request.jamminess == pytest.approx(0.42)
