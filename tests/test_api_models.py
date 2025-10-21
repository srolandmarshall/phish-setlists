"""Tests for FastAPI request/response models."""

from __future__ import annotations

from datetime import datetime, timezone

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


def test_generate_request_model_default_year_is_utc_now(monkeypatch):
    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2030, 5, 1, tzinfo=timezone.utc)

    monkeypatch.setattr("phish_setlist_maker.api.schemas.datetime", FakeDatetime)

    model = GenerateRequestModel()
    assert model.year == 2030
