"""Conversion helpers between service-layer results and API schemas."""

from __future__ import annotations

from typing import Optional

from ..generator.core import GenerationMetadata
from ..service import GenerationResult, PlaylistArtifacts, SegmentDetails, SongDisplay
from .schemas import (
    GenerateResponse,
    HTMLModel,
    MetadataModel,
    PlaylistModel,
    PlaylistSectionModel,
    SegmentModel,
    SongModel,
)


def _format_total(seconds: Optional[int]) -> Optional[str]:
    if seconds is None or seconds <= 0:
        return None
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


def metadata_to_model(metadata: GenerationMetadata) -> MetadataModel:
    return MetadataModel(
        reference_date=metadata.reference_date,
        cutoff_date=metadata.cutoff_date,
        era=metadata.era,
        year=metadata.year,
        notes=list(metadata.notes),
    )


def segment_to_model(segment: SegmentDetails) -> SegmentModel:
    return SegmentModel(
        label=segment.label,
        songs=list(segment.songs),
        tracks=[SongModel(**song.__dict__) for song in segment.tracks],
        duration_seconds=segment.duration_seconds,
        duration_label=_format_total(segment.duration_seconds),
    )


def songdisplay_to_model(song: SongDisplay) -> SongModel:
    return SongModel(
        title=song.title,
        mp3_url=song.mp3_url,
        duration_seconds=song.duration_seconds,
        origin=song.origin,
        show_date=song.show_date,
    )


def playlist_to_model(artifacts: PlaylistArtifacts) -> PlaylistModel:
    sections = [
        PlaylistSectionModel(
            title=title,
            tracks=[songdisplay_to_model(song) for song in songs],
        )
        for title, songs in artifacts.sections
    ]
    return PlaylistModel(
        sections=sections,
        first_track_url=artifacts.first_track_url,
        m3u_text=artifacts.m3u_text,
        missing_tracks=list(artifacts.missing_tracks),
    )


def result_to_response(result: GenerationResult) -> GenerateResponse:
    sets = [segment_to_model(segment) for segment in result.segments]
    encore = segment_to_model(result.encore) if result.encore else None

    playlist = playlist_to_model(result.playlist) if result.playlist else None
    html = None
    if result.html:
        html = HTMLModel(markup=result.html.markup, stylesheet=result.html.stylesheet)

    return GenerateResponse(
        seed=result.seed,
        generated_at=result.generated_at,
        metadata=metadata_to_model(result.generated.metadata),
        sets=sets,
        encore=encore,
        playlist=playlist,
        html=html,
    )


__all__ = [
    "metadata_to_model",
    "segment_to_model",
    "songdisplay_to_model",
    "playlist_to_model",
    "result_to_response",
]
