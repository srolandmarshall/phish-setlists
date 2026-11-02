"""Tests for FastAPI request/response models."""

from __future__ import annotations

import pytest

from phish_setlist_maker.api import GenerateRequestModel


def test_generate_request_model_normalizes_set_lengths():
    model = GenerateRequestModel(
        set_lengths={"Set1": 10, "encore": 3},
        include_html=False,
        include_playlist=False,
    )

    assert model.set_lengths == {"set1": 10, "encore": 3}


def test_generate_request_model_rejects_invalid_label():
    with pytest.raises(ValueError):
        GenerateRequestModel(set_lengths={"weird": 5})


def test_generate_request_model_leaves_year_resolution_to_service():
    model = GenerateRequestModel()
    assert model.year is None
