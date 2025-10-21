"""Tests for track metadata helpers."""

from __future__ import annotations

from datetime import datetime
from random import Random

import responses

from phish_setlist_maker.models import Show, Song, SongTrack, Track
from phish_setlist_maker.service.tracks import fetch_remote_track_metadata, query_tracks_for_song


def _seed_data(db_session):
    show = Show(
        date=datetime(2024, 7, 1).date(),
        created_at=datetime(2024, 7, 1),
        updated_at=datetime(2024, 7, 1),
        venue_name="Test",
        duration=0,
        audio_status="complete",
    )
    song = Song(
        title="Tweezer",
        slug="tweezer",
        tracks_count=0,
        original=True,
        alias=None,
        artist="Phish",
    )
    track_best = Track(
        title="Tweezer",
        position=1,
        duration=600,
        set="Set 1",
        slug="tweezer-best",
        likes_count=10,
    )
    track_second = Track(
        title="Tweezer",
        position=1,
        duration=500,
        set="Set 1",
        slug="tweezer-second",
        likes_count=5,
    )
    link_best = SongTrack(song=song, track=track_best)
    link_second = SongTrack(song=song, track=track_second)
    track_best.show = show
    track_second.show = show

    db_session.add_all([show, song, track_best, track_second, link_best, link_second])
    db_session.commit()

    return track_best.id, track_second.id


def test_query_tracks_for_song_orders_candidates(db_session):
    first_id, second_id = _seed_data(db_session)

    candidates = query_tracks_for_song(db_session, "tweezer")

    assert len(candidates) == 2
    assert candidates[0].track_id == first_id
    assert candidates[1].track_id == second_id


def test_fetch_remote_track_metadata_falls_back_to_tracks_endpoint(db_session):
    first_id, _ = _seed_data(db_session)
    rng = Random(7)

    with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
        rsps.add(
            responses.GET,
            f"https://phish.in/api/v2/tracks/{first_id}.json",
            json={"mp3_url": None, "duration": None, "show_date": None},
            status=200,
        )
        rsps.add(
            responses.GET,
            "https://phish.in/api/v2/tracks.json",
            json={
                "tracks": [
                    {
                        "mp3_url": "https://phish.in/audio/tweezer.mp3",
                        "duration": 600000,
                        "show_date": "1999-10-31",
                    }
                ]
            },
            status=200,
        )

        mp3_url, duration, show_date = fetch_remote_track_metadata(
            track_id=first_id,
            song_slug="tweezer",
            rng=rng,
            strict=True,
        )

    assert mp3_url.endswith(".mp3")
    assert duration == 600
    assert show_date == "1999-10-31"
