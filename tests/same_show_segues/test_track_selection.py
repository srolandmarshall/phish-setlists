"""Track selection behavior for same-show segues."""

from __future__ import annotations

from datetime import date
import random

import pytest
from sqlalchemy.orm import Session

from phish_setlist_maker.analysis.feature_store import FeatureStore
from phish_setlist_maker.generator.core import GeneratedSetlist, GenerationMetadata, SetSegment
from phish_setlist_maker.models import Song, Track
from phish_setlist_maker.service.generation import _select_track_display

pytestmark = pytest.mark.slow


@pytest.mark.segue
def test_same_show_segues_filters_candidates_by_show_id(
    db_session: Session,
    sample_shows_with_segues,
    mock_feature_loaders,
):
    """Test that same_show_segues=True filters track candidates to same show."""
    feature_store = FeatureStore(features_dir=sample_shows_with_segues['features_dir'])
    feature_store.load()

    # Get Mike's Song entry
    mikes_song = db_session.query(Song).filter(Song.slug == "mikes-song").first()
    assert mikes_song is not None
    mikes_entry = song_to_catalog_entry(mikes_song)

    # Create a GeneratedSetlist that includes the segue pattern
    generated_setlist = GeneratedSetlist(
        sets=[SetSegment(label="Set 1", songs=["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"])],
        encore=None,
        metadata=GenerationMetadata(
            reference_date=date(2024, 12, 1),
            cutoff_date=date(2024, 12, 1),
            era="4.0",
            year=2024,
            notes=[],
        ),
    )

    # Test with same_show_segues=True
    rng = random.Random(42)
    display = _select_track_display(
        db_session=db_session,
        entry=mikes_entry,
        song_title="Mike's Song",
        rng=rng,
        strict=False,
        missing={},
        is_set_ender=False,
        canonical_set=None,
        feature_store=feature_store,
        same_show_segues=True,  # ENABLED
        generated_setlist=generated_setlist,
    )

    assert display is not None
    assert display.track_id in {100, 200}, (
        f"Expected track from show with complete segue (100 or 200), got {display.track_id}"
    )

    # Verify the selected track's show has the complete segue
    track = db_session.query(Track).filter(Track.id == display.track_id).first()
    show_id = track.show_id

    # Query all tracks from this show in set2
    show_tracks = db_session.query(Track).filter(
        Track.show_id == show_id,
        Track.set == "set2"
    ).order_by(Track.position).all()

    song_titles = [t.title for t in show_tracks[:3]]

    assert "Mike's Song" in song_titles
    assert "I Am Hydrogen" in song_titles
    assert "Weekapaug Groove" in song_titles

@pytest.mark.segue
def test_same_show_segues_disabled_allows_any_candidate(
    db_session: Session,
    sample_shows_with_segues,
    mock_feature_loaders,
):
    """Test that same_show_segues=False allows any track candidate (no filtering)."""
    feature_store = FeatureStore(features_dir=sample_shows_with_segues['features_dir'])
    feature_store.load()

    mikes_song = db_session.query(Song).filter(Song.slug == "mikes-song").first()
    assert mikes_song is not None
    mikes_entry = song_to_catalog_entry(mikes_song)

    generated_setlist = GeneratedSetlist(
        sets=[SetSegment(label="Set 1", songs=["Mike's Song"])],
        encore=None,
        metadata=GenerationMetadata(
            reference_date=date(2024, 12, 1),
            cutoff_date=date(2024, 12, 1),
            era="4.0",
            year=2024,
            notes=[],
        ),
    )

    # Test with same_show_segues=False
    rng = random.Random(99)
    display = _select_track_display(
        db_session=db_session,
        entry=mikes_entry,
        song_title="Mike's Song",
        rng=rng,
        strict=False,
        missing={},
        feature_store=feature_store,
        same_show_segues=False,  # DISABLED
        generated_setlist=generated_setlist,
    )

    assert display is not None
    # With same_show_segues=False, any Mike's Song track can be selected
    assert display.track_id in {100, 200}

@pytest.mark.segue
def test_complete_segue_tracks_from_same_show(
    db_session: Session,
    sample_shows_with_segues,
    mock_feature_loaders,
):
    """Test that selecting all 3 segue songs with same_show_segues=True gives same show."""
    feature_store = FeatureStore(features_dir=sample_shows_with_segues['features_dir'])
    feature_store.load()

    generated_setlist = GeneratedSetlist(
        sets=[SetSegment(label="Set 1", songs=["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"])],
        encore=None,
        metadata=GenerationMetadata(
            reference_date=date(2024, 12, 1),
            cutoff_date=date(2024, 12, 1),
            era="4.0",
            year=2024,
            notes=[],
        ),
    )

    # Use a fixed RNG seed for reproducibility
    rng = random.Random(123)

    # Get all the song entries
    mikes_song = db_session.query(Song).filter(Song.slug == "mikes-song").first()
    hydrogen_song = db_session.query(Song).filter(Song.slug == "i-am-hydrogen").first()
    weekapaug_song = db_session.query(Song).filter(Song.slug == "weekapaug-groove").first()

    # Select all three tracks
    mikes_display = _select_track_display(
        db_session=db_session,
        entry=song_to_catalog_entry(mikes_song),
        song_title="Mike's Song",
        rng=rng,
        strict=False,
        missing={},
        feature_store=feature_store,
        same_show_segues=True,
        generated_setlist=generated_setlist,
    )

    hydrogen_display = _select_track_display(
        db_session=db_session,
        entry=song_to_catalog_entry(hydrogen_song),
        song_title="I Am Hydrogen",
        rng=rng,
        strict=False,
        missing={},
        feature_store=feature_store,
        same_show_segues=True,
        generated_setlist=generated_setlist,
    )

    weekapaug_display = _select_track_display(
        db_session=db_session,
        entry=song_to_catalog_entry(weekapaug_song),
        song_title="Weekapaug Groove",
        rng=rng,
        strict=False,
        missing={},
        feature_store=feature_store,
        same_show_segues=True,
        generated_setlist=generated_setlist,
    )

    # All should be selected
    assert mikes_display is not None
    assert hydrogen_display is not None
    assert weekapaug_display is not None

    # Get show_ids
    mikes_track = db_session.query(Track).filter(Track.id == mikes_display.track_id).first()
    hydrogen_track = db_session.query(Track).filter(Track.id == hydrogen_display.track_id).first()
    weekapaug_track = db_session.query(Track).filter(Track.id == weekapaug_display.track_id).first()

    # CRITICAL ASSERTION: All from same show
    assert mikes_track.show_id == hydrogen_track.show_id == weekapaug_track.show_id, (
        f"FAILED: Tracks from different shows! "
        f"Mike's: show {mikes_track.show_id}, "
        f"Hydrogen: show {hydrogen_track.show_id}, "
        f"Weekapaug: show {weekapaug_track.show_id}"
    )

@pytest.mark.segue
def test_lottery_tickets_only_enabled_with_same_show_segues(
    db_session: Session,
    sample_shows_with_segues,
    mock_feature_loaders,
):
    """Test that lottery logic only activates when same_show_segues=True."""
    import pandas as pd

    # Add Tweezer/Caspian tracks to show 1
    tweezer_track = Track(
        id=400,
        show_id=1,
        title="Tweezer",
        slug="tweezer-2024-07-15",
        set="set2",
        position=4,
        duration=1056,
        likes_count=140,
    )
    caspian_track = Track(
        id=401,
        show_id=1,
        title="Prince Caspian",
        slug="prince-caspian-2024-07-15",
        set="set2",
        position=5,
        duration=1012,
        likes_count=90,
    )
    db_session.add_all([tweezer_track, caspian_track])

    tweezer_song = sample_shows_with_segues['songs'][3]
    caspian_song = sample_shows_with_segues['songs'][4]

    song_track_tweezer = SongTrack(song=tweezer_song, track=tweezer_track)
    song_track_caspian = SongTrack(song=caspian_song, track=caspian_track)
    db_session.add_all([song_track_tweezer, song_track_caspian])
    db_session.commit()

    # Update rare_segues data to include this Tweezer->Caspian
    rare_data = [{
        'segue_id': 'tweezer_prince_caspian_2024-07-15_set2',
        'segue_type': 'pair',
        'pattern': 'Tweezer -> Prince Caspian',
        'show_id': 1,
        'show_date': '2024-07-15',
        'set_label': 'set2',
        'tracks': [400, 401],
        'songs': ['Tweezer', 'Prince Caspian'],
        'total_duration': 2068,
        'likes_count': 230,
        'historical_occurrences': 8,
        'frequency': 'rare',
        'rarity_score': 0.0038,
        'is_lottery_ticket': True,
        'lottery_weight': 230,
    }]
    pd.DataFrame(rare_data).to_parquet(
        sample_shows_with_segues['features_dir'] / "rare_segues.parquet",
        index=False
    )

    # Reload feature store
    feature_store = FeatureStore(features_dir=sample_shows_with_segues['features_dir'])
    feature_store.load()

    tweezer_song = db_session.query(Song).filter(Song.slug == "tweezer").first()
    assert tweezer_song is not None
    tweezer_entry = song_to_catalog_entry(tweezer_song)

    # Test 1: same_show_segues=True - lottery enabled (rare_segue_next_tracks can be populated)
    rng1 = random.Random(42)
    display_with_lottery = _select_track_display(
        db_session=db_session,
        entry=tweezer_entry,
        song_title="Tweezer",
        rng=rng1,
        strict=False,
        missing={},
        feature_store=feature_store,
        same_show_segues=True,  # ENABLED
    )

    assert display_with_lottery is not None
    # Note: rare_segue_next_tracks may or may not be set depending on 5% lottery roll
    # The important thing is that the code path is available

    # Test 2: same_show_segues=False - lottery disabled (rare_segue_next_tracks never set)
    rng2 = random.Random(99)
    display_without_lottery = _select_track_display(
        db_session=db_session,
        entry=tweezer_entry,
        song_title="Tweezer",
        rng=rng2,
        strict=False,
        missing={},
        feature_store=feature_store,
        same_show_segues=False,  # DISABLED
    )

    assert display_without_lottery is not None
    # With same_show_segues=False, rare_segue_next_tracks must be None
    assert display_without_lottery.rare_segue_next_tracks is None or len(display_without_lottery.rare_segue_next_tracks) == 0

@pytest.mark.segue
def test_same_show_segues_with_no_feature_store_gracefully_degrades(
    db_session: Session,
    sample_shows_with_segues,
):
    """Test that same_show_segues=True doesn't crash when feature_store is None."""
    mikes_song = db_session.query(Song).filter(Song.slug == "mikes-song").first()
    assert mikes_song is not None
    mikes_entry = song_to_catalog_entry(mikes_song)

    rng = random.Random(42)

    # Should not crash even with feature_store=None
    display = _select_track_display(
        db_session=db_session,
        entry=mikes_entry,
        song_title="Mike's Song",
        rng=rng,
        strict=False,
        missing={},
        feature_store=None,  # No feature store
        same_show_segues=True,  # Still enabled, but should gracefully degrade
    )

    assert display is not None
    # Just picks a random track since no feature store available
    assert display.track_id in {100, 200}
