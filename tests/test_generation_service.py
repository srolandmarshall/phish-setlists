"""Tests for the service-layer setlist generation helpers."""

from __future__ import annotations

from datetime import date, datetime

import responses
from pytest_mock import MockerFixture

from phish_setlist_maker.generator.core import GenerationMetadata, GeneratedSetlist, SetSegment
from phish_setlist_maker.models import Song, SongTrack, Track
from phish_setlist_maker.service.generation import GenerationRequest, generate_show, resolve_era


def test_resolve_era_adjusts_when_year_predates_request() -> None:
    era, note = resolve_era(1998, "4.0")
    assert era == "1.0"
    assert note == "Adjusted era to 1.0 because year 1998 predates era 4.0."


def test_generate_show_allows_previous_show_for_past_year(
    db_session,
    mocker: MockerFixture,
) -> None:
    """When a past year is requested without previous-show allowance, it is re-enabled."""

    fake_metadata = GenerationMetadata(
        reference_date=date(2024, 1, 1),
        cutoff_date=date(2024, 1, 1),
        era="4.0",
        year=1999,
        notes=[],
    )
    fake_generated = GeneratedSetlist(
        sets=[
            SetSegment(label="Set 1", songs=["Song A"]),
            SetSegment(label="Set 2", songs=["Song B"]),
        ],
        encore=None,
        metadata=fake_metadata,
    )

    generator_cls = mocker.patch("phish_setlist_maker.service.generation.SetlistGenerator")
    generator_instance = generator_cls.return_value
    generator_instance.generate.return_value = fake_generated

    request = GenerationRequest(
        era="4.0",
        year=1999,
        num_sets=2,
        include_encore=False,
        set_lengths={"set1": 10, "set2": 9},
        allow_previous_show=False,
        seed=42,
        include_playlist=False,
        include_html=False,
        prefetch_track_metadata=False,
    )

    result = generate_show(db_session, request)

    # Seed should be the explicit request seed.
    assert result.seed == 42
    assert result.playlist is None
    assert result.html is None

    kwargs = generator_instance.generate.call_args.kwargs
    assert kwargs["exclude_previous_show"] is False

    assert "Allowed previous show songs because the selected year predates the current year." in fake_metadata.notes


def test_generate_show_populates_playlist_with_remote_fallback(
    db_session,
    mocker: MockerFixture,
) -> None:
    """Playlist assembly should recover when the initial track lookup lacks audio."""

    now = datetime(2024, 7, 1, 0, 0, 0)
    song = Song(
        title="Tweezer",
        slug="tweezer",
        original=True,
        alias=None,
        artist="Phish",
    )
    track = Track(
        title="Tweezer",
        position=1,
        duration=0,
        set="Set 1",
        slug="tweezer-1999-01-01",
        likes_count=25,
    )
    link = SongTrack(song=song, track=track)

    db_session.add_all([song, track, link])
    db_session.flush()

    fake_metadata = GenerationMetadata(
        reference_date=now.date(),
        cutoff_date=now.date(),
        era="4.0",
        year=2024,
        notes=[],
    )
    fake_generated = GeneratedSetlist(
        sets=[
            SetSegment(label="Set 1", songs=["Tweezer"]),
            SetSegment(label="Set 2", songs=[]),
        ],
        encore=None,
        metadata=fake_metadata,
    )

    generator_cls = mocker.patch("phish_setlist_maker.service.generation.SetlistGenerator")
    generator_instance = generator_cls.return_value
    generator_instance.generate.return_value = fake_generated

    fallback_url = "https://phish.in/audio/tweezer.mp3"

    with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
        rsps.add(
            responses.GET,
            f"https://phish.in/api/v2/tracks/{track.id}.json",
            json={
                "mp3_url": None,
                "duration": None,
                "show_date": "1999-01-01",
            },
            status=200,
        )
        rsps.add(
            responses.GET,
            "https://phish.in/api/v2/tracks.json",
            match=[
                responses.matchers.query_param_matcher(
                    {
                        "song_slug": "tweezer",
                        "per_page": "30",
                        "sort": "likes_count:desc",
                        "audio_status": "complete_or_partial",
                    }
                )
            ],
            json={
                "tracks": [
                    {
                        "mp3_url": fallback_url,
                        "duration": 660000,
                        "show_date": "1999-10-31",
                    }
                ]
            },
            status=200,
        )

        request = GenerationRequest(
            era="4.0",
            year=2024,
            num_sets=2,
            include_encore=False,
            set_lengths={"set1": 1, "set2": 0},
            allow_previous_show=True,
            seed=7,
            include_playlist=True,
            include_html=False,
            prefetch_track_metadata=True,
        )

        result = generate_show(db_session, request)

    assert result.playlist is not None
    assert result.playlist.first_track_url == fallback_url
    assert result.playlist.missing_tracks == []
    assert result.playlist.m3u_text is not None
    assert "playlist.m3u" not in (result.html.markup if result.html else "")

    sections = dict(result.playlist.sections)
    assert "Set 1" in sections
    track_display = sections["Set 1"][0]
    assert track_display.title == "Tweezer"
    assert track_display.mp3_url == fallback_url
    assert track_display.duration_seconds == 660
    assert track_display.show_date == "1999-10-31"
