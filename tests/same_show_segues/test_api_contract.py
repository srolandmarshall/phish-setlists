"""API request contract for same-show segue generation."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

pytestmark = pytest.mark.slow


@pytest.mark.segue
def test_api_parameter_forwards_correctly(
    db_session: Session,
    sample_shows_with_segues,
):
    """Test that GenerateRequestModel correctly forwards same_show_segues to GenerationRequest."""
    from phish_setlist_maker.api.factories import build_generation_request
    from phish_setlist_maker.api.schemas import GenerateRequestModel

    # Test with same_show_segues=True
    payload_true = GenerateRequestModel(
        same_show_segues=True,
        include_playlist=False,
    )

    request_true = build_generation_request(
        payload_true,
        include_playlist=False,
        fail_on_playlist_error=False,
    )

    assert request_true.same_show_segues is True, "Expected same_show_segues=True to be forwarded"

    # Test with same_show_segues=False (default)
    payload_false = GenerateRequestModel(
        same_show_segues=False,
        include_playlist=False,
    )

    request_false = build_generation_request(
        payload_false,
        include_playlist=False,
        fail_on_playlist_error=False,
    )

    assert request_false.same_show_segues is False, "Expected same_show_segues=False to be forwarded"
