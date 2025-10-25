"""Helpers for constructing generation requests from API payloads."""

from __future__ import annotations

from typing import Optional

from ..service import GenerationRequest
from .schemas import GenerateRequestModel


def build_generation_request(
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
        use_ml_features=model.use_ml_features,
        ml_placement_weight=model.ml_placement_weight,
        ml_transition_bonus=model.ml_transition_bonus,
        jamminess=model.jamminess,
    )
