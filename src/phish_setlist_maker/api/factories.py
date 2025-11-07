"""Helpers for constructing generation requests from API payloads."""

from __future__ import annotations

from ..service import GenerationRequest
from .schemas import GenerateRequestModel


def build_generation_request(
    model: GenerateRequestModel,
    *,
    include_playlist: bool,
    fail_on_playlist_error: bool,
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
        prefetch_track_metadata=include_playlist,
        fail_on_playlist_error=fail_on_playlist_error,
        use_ml_features=model.use_ml_features,
        ml_placement_weight=model.ml_placement_weight,
        ml_transition_bonus=model.ml_transition_bonus,
        jamminess=model.jamminess,
        same_show_segues=model.same_show_segues,
    )
