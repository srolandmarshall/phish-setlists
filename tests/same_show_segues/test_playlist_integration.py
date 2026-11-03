"""Playlist integration behavior for mandatory same-show segues."""

from __future__ import annotations

import random

import pytest
from sqlalchemy.orm import Session

from phish_setlist_maker.analysis.feature_store import FeatureStore
from phish_setlist_maker.models import Track

pytestmark = pytest.mark.slow


@pytest.mark.segue
def test_mandatory_segues_no_duplicates_in_playlist(
    db_session: Session,
    sample_shows_with_segues,
    mock_feature_loaders,
):
    """Test that mandatory segues don't create duplicate tracks when songs are in original array."""
    from phish_setlist_maker.service.generation import prepare_playlist_artifacts
    from phish_setlist_maker.service.catalog import build_song_catalog
    from phish_setlist_maker.generator.core import SetSegment

    feature_store = FeatureStore(features_dir=sample_shows_with_segues['features_dir'])
    feature_store.load()

    # Create a setlist with Mike's Song followed by Weekapaug and Hydrogen in songs array
    # This mimics what the generator might produce
    segments = [
        SetSegment(
            label="Set 1",
            songs=["Mike's Song", "Weekapaug Groove", "I Am Hydrogen", "Tweezer"]
        )
    ]

    catalog = build_song_catalog(db_session)
    rng = random.Random(42)

    artifacts = prepare_playlist_artifacts(
        db_session,
        segments,
        encore=None,
        catalog=catalog,
        rng=rng,
        include_m3u=True,
        strict=False,
        feature_store=feature_store,
        same_show_segues=True,
    )

    # Get Set 1 tracks
    set1_tracks = None
    for section_label, tracks in artifacts.sections:
        if section_label == "Set 1":
            set1_tracks = tracks
            break

    assert set1_tracks is not None, "Set 1 not found in sections"

    # Count occurrences of each track_id
    track_id_counts = {}
    for track in set1_tracks:
        if track.track_id:
            track_id_counts[track.track_id] = track_id_counts.get(track.track_id, 0) + 1

    # Verify no duplicates
    duplicates = {tid: count for tid, count in track_id_counts.items() if count > 1}
    assert not duplicates, f"Found duplicate track IDs: {duplicates}"

    # Verify mandatory pattern was injected (should have Mike's + continuations)
    track_titles = [t.title for t in set1_tracks]
    assert "Mike's Song" in track_titles, "Mike's Song should be in setlist"

    # Should have either full pattern or partial based on what followed in the actual show
    # At minimum, we should have injected Hydrogen or Weekapaug
    has_hydrogen = "I Am Hydrogen" in track_titles
    has_weekapaug = "Weekapaug Groove" in track_titles
    assert has_hydrogen or has_weekapaug, "Should have injected at least one mandatory continuation"

@pytest.mark.segue
def test_mandatory_segue_ordering(
    db_session: Session,
    sample_shows_with_segues,
):
    """Test that mandatory segues maintain correct song order (Mike's > Hydrogen > Weekapaug)."""
    from phish_setlist_maker.service.generation import prepare_playlist_artifacts
    from phish_setlist_maker.service.catalog import build_song_catalog
    from phish_setlist_maker.generator.core import SetSegment

    feature_store = FeatureStore(features_dir=sample_shows_with_segues['features_dir'])
    # Only load segue groups (avoid loading song_features.parquet which doesn't exist in test fixtures)
    feature_store._load_segue_groups()

    # Create a setlist with Mike's Song followed by Weekapaug and Hydrogen in WRONG order
    segments = [
        SetSegment(
            label="Set 1",
            songs=["Mike's Song", "Weekapaug Groove", "I Am Hydrogen", "Tweezer"]
        )
    ]

    catalog = build_song_catalog(db_session)
    rng = random.Random(42)

    artifacts = prepare_playlist_artifacts(
        db_session,
        segments,
        encore=None,
        catalog=catalog,
        rng=rng,
        include_m3u=True,
        strict=False,
        feature_store=feature_store,
        same_show_segues=True,
    )

    # Get Set 1 tracks
    set1_tracks = None
    for section_label, tracks in artifacts.sections:
        if section_label == "Set 1":
            set1_tracks = tracks
            break

    assert set1_tracks is not None, "Set 1 not found in sections"

    track_titles = [t.title for t in set1_tracks]

    # Find Mike's Song position
    mikes_idx = track_titles.index("Mike's Song")

    # The next songs after Mike's should be Hydrogen then Weekapaug (in that order)
    # NOT Weekapaug then Hydrogen (which would be wrong even though both appear in original array)
    assert mikes_idx + 1 < len(track_titles), "Should have songs after Mike's"
    assert mikes_idx + 2 < len(track_titles), "Should have at least 2 songs after Mike's"

    next_song = track_titles[mikes_idx + 1]
    song_after_that = track_titles[mikes_idx + 2]

    # Correct order: Mike's Song > I Am Hydrogen > Weekapaug Groove
    assert next_song == "I Am Hydrogen", f"Song after Mike's should be Hydrogen, got {next_song}"
    assert song_after_that == "Weekapaug Groove", f"Song after Hydrogen should be Weekapaug, got {song_after_that}"
