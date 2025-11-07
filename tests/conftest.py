"""Shared pytest fixtures for the Phish setlist maker tests."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from phish_setlist_maker.models import Base  # noqa: F401 - ensure all models registered
from phish_setlist_maker.models import (  # noqa: F401 - ensure all models registered
    Show,
    Song,
    SongTrack,
    Tour,
    Track,
    Venue,
)


# Add scripts directory to Python path for importing build_segue_groups
def pytest_configure(config):
    """Configure pytest to add scripts dir to path."""
    repo_root = Path(__file__).parent.parent
    scripts_dir = repo_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """Provide an isolated in-memory SQLite session for each test."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        engine.dispose()


# ============================================================================
# Segue Test Fixtures (shared across segue tests)
# ============================================================================

@pytest.fixture
def mock_feature_loaders():
    """Mock all non-segue feature loaders to avoid file dependencies."""
    with patch.object(__import__('phish_setlist_maker.analysis.feature_store', fromlist=['FeatureStore']).FeatureStore, '_load_song_features'), \
         patch.object(__import__('phish_setlist_maker.analysis.feature_store', fromlist=['FeatureStore']).FeatureStore, '_load_transition_lifts'), \
         patch.object(__import__('phish_setlist_maker.analysis.feature_store', fromlist=['FeatureStore']).FeatureStore, '_load_multi_home_songs'), \
         patch.object(__import__('phish_setlist_maker.analysis.feature_store', fromlist=['FeatureStore']).FeatureStore, '_load_directional_rules'), \
         patch.object(__import__('phish_setlist_maker.analysis.feature_store', fromlist=['FeatureStore']).FeatureStore, '_load_ordering_constraints'), \
         patch.object(__import__('phish_setlist_maker.analysis.feature_store', fromlist=['FeatureStore']).FeatureStore, '_load_cross_set_dependencies'), \
         patch.object(__import__('phish_setlist_maker.analysis.feature_store', fromlist=['FeatureStore']).FeatureStore, '_load_set_ending_frequencies'):
        yield


@pytest.fixture
def minimal_segue_data(tmp_path):
    """Create minimal segue data for testing."""
    features_dir = tmp_path / "features"
    features_dir.mkdir()
    
    # Mandatory segues
    mandatory_data = [
        {
            'segue_id': 'mikes_song_i_am_hydrogen_2024-07-15_set2',
            'segue_type': 'pair',
            'pattern': "Mike's Song -> I Am Hydrogen",
            'show_id': 1,
            'show_date': '2024-07-15',
            'set_label': 'set2',
            'tracks': [100, 101],
            'songs': ["Mike's Song", "I Am Hydrogen"],
            'total_duration': 600,
            'likes_count': 35,
            'historical_occurrences': 313,
            'frequency': 'mandatory',
            'confidence': 0.95,
        },
        {
            'segue_id': 'i_am_hydrogen_weekapaug_groove_2024-07-15_set2',
            'segue_type': 'pair',
            'pattern': 'I Am Hydrogen -> Weekapaug Groove',
            'show_id': 1,
            'show_date': '2024-07-15',
            'set_label': 'set2',
            'tracks': [101, 102],
            'songs': ['I Am Hydrogen', 'Weekapaug Groove'],
            'total_duration': 660,
            'likes_count': 40,
            'historical_occurrences': 321,
            'frequency': 'mandatory',
            'confidence': 0.95,
        },
    ]
    
    # Rare segues (lottery tickets)
    rare_data = [
        {
            'segue_id': 'tweezer_prince_caspian_2015-08-22_set2',
            'segue_type': 'pair',
            'pattern': 'Tweezer -> Prince Caspian',
            'show_id': 1836,
            'show_date': '2015-08-22',
            'set_label': 'set2',
            'tracks': [200, 201],
            'songs': ['Tweezer', 'Prince Caspian'],
            'total_duration': 2068,
            'likes_count': 339,
            'historical_occurrences': 8,
            'frequency': 'rare',
            'rarity_score': 0.0038,
            'is_lottery_ticket': True,
            'lottery_weight': 339,
        },
    ]
    
    pd.DataFrame(mandatory_data).to_parquet(features_dir / "segue_groups.parquet", index=False)
    pd.DataFrame(rare_data).to_parquet(features_dir / "rare_segues.parquet", index=False)
    
    return features_dir
