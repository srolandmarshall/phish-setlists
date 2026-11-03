"""Shared fixtures for same-show segue behavior tests."""

from datetime import date, datetime

import pytest
from sqlalchemy.orm import Session

from phish_setlist_maker.models import Show, Song, SongTrack, Track
from phish_setlist_maker.service.catalog import SongCatalogEntry


def song_to_catalog_entry(song: Song) -> SongCatalogEntry:
    """Convert a Song model to a SongCatalogEntry for testing."""
    return SongCatalogEntry(
        slug=song.slug,
        title=song.title,
        artist="Phish",
        original=True,
        alias=None,
    )

@pytest.fixture
def sample_shows_with_segues(db_session: Session, minimal_segue_data):
    """Create database with shows containing mandatory segue patterns."""
    now = datetime.now()

    # Create shows
    show1 = Show(
        id=1,
        date=date(2024, 7, 15),
        created_at=now,
        updated_at=now,
        venue_id=1,
        tour_id=1,
    )
    show2 = Show(
        id=2,
        date=date(2023, 8, 5),
        created_at=now,
        updated_at=now,
        venue_id=1,
        tour_id=1,
    )
    show3 = Show(
        id=3,
        date=date(2022, 6, 3),
        created_at=now,
        updated_at=now,
        venue_id=1,
        tour_id=1,
    )
    db_session.add_all([show1, show2, show3])

    # Create songs
    mikes_song = Song(id=1, title="Mike's Song", slug="mikes-song")
    hydrogen = Song(id=2, title="I Am Hydrogen", slug="i-am-hydrogen")
    weekapaug = Song(id=3, title="Weekapaug Groove", slug="weekapaug-groove")
    tweezer = Song(id=4, title="Tweezer", slug="tweezer")
    caspian = Song(id=5, title="Prince Caspian", slug="prince-caspian")
    maze = Song(id=6, title="Maze", slug="maze")

    db_session.add_all([mikes_song, hydrogen, weekapaug, tweezer, caspian, maze])

    # Show 1 (2024-07-15): Mike's -> Hydrogen -> Weekapaug
    track_100 = Track(
        id=100,
        show_id=1,
        title="Mike's Song",
        slug="mikes-song-2024-07-15",
        set="set2",
        position=1,
        duration=480,
        likes_count=25,
    )
    track_101 = Track(
        id=101,
        show_id=1,
        title="I Am Hydrogen",
        slug="i-am-hydrogen-2024-07-15",
        set="set2",
        position=2,
        duration=120,
        likes_count=10,
    )
    track_102 = Track(
        id=102,
        show_id=1,
        title="Weekapaug Groove",
        slug="weekapaug-groove-2024-07-15",
        set="set2",
        position=3,
        duration=540,
        likes_count=30,
    )

    # Show 2 (2023-08-05): Mike's -> Hydrogen -> Weekapaug (different show)
    track_200 = Track(
        id=200,
        show_id=2,
        title="Mike's Song",
        slug="mikes-song-2023-08-05",
        set="set2",
        position=1,
        duration=510,
        likes_count=28,
    )
    track_201 = Track(
        id=201,
        show_id=2,
        title="I Am Hydrogen",
        slug="i-am-hydrogen-2023-08-05",
        set="set2",
        position=2,
        duration=110,
        likes_count=12,
    )
    track_202 = Track(
        id=202,
        show_id=2,
        title="Weekapaug Groove",
        slug="weekapaug-groove-2023-08-05",
        set="set2",
        position=3,
        duration=550,
        likes_count=32,
    )

    # Show 3 (2022-06-03): Standalone tracks (for control)
    track_300 = Track(
        id=300,
        show_id=3,
        title="Maze",
        slug="maze-2022-06-03",
        set="set1",
        position=1,
        duration=420,
        likes_count=15,
    )

    db_session.add_all([
        track_100, track_101, track_102,
        track_200, track_201, track_202,
        track_300,
    ])

    # Create SongTrack associations
    song_track_100 = SongTrack(song=mikes_song, track=track_100)
    song_track_101 = SongTrack(song=hydrogen, track=track_101)
    song_track_102 = SongTrack(song=weekapaug, track=track_102)
    song_track_200 = SongTrack(song=mikes_song, track=track_200)
    song_track_201 = SongTrack(song=hydrogen, track=track_201)
    song_track_202 = SongTrack(song=weekapaug, track=track_202)
    song_track_300 = SongTrack(song=maze, track=track_300)

    db_session.add_all([
        song_track_100, song_track_101, song_track_102,
        song_track_200, song_track_201, song_track_202,
        song_track_300,
    ])

    db_session.commit()

    return {
        'shows': [show1, show2, show3],
        'songs': [mikes_song, hydrogen, weekapaug, tweezer, caspian, maze],
        'tracks': {
            'show1_mikes': track_100,
            'show1_hydrogen': track_101,
            'show1_weekapaug': track_102,
            'show2_mikes': track_200,
            'show2_hydrogen': track_201,
            'show2_weekapaug': track_202,
            'show3_maze': track_300,
        },
        'features_dir': minimal_segue_data,
    }
