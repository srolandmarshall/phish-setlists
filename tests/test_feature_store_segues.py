"""Tests for feature store segue groups loading."""

import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import Mock, patch


pytestmark = pytest.mark.segue


@pytest.fixture
def segue_parquet_files(tmp_path):
    """Create test parquet files with segue data."""
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
            'tracks': [2, 3],
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
            'tracks': [3, 4],
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
            'tracks': [30447, 30448],
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
    
    df_mandatory = pd.DataFrame(mandatory_data)
    df_rare = pd.DataFrame(rare_data)
    
    df_mandatory.to_parquet(features_dir / "segue_groups.parquet", index=False)
    df_rare.to_parquet(features_dir / "rare_segues.parquet", index=False)
    
    return features_dir


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


class TestFeatureStoreSegueLoading:
    """Test feature store loads segue data correctly."""
    
    def test_loads_mandatory_segues(self, segue_parquet_files, mock_feature_loaders):
        """Should load mandatory segue groups from parquet."""
        from phish_setlist_maker.analysis.feature_store import FeatureStore
        
        fs = FeatureStore(segue_parquet_files)
        fs.load()
        
        # Should have loaded 2 mandatory segues
        assert fs._segue_groups is not None
        assert len(fs._segue_groups) == 2
        
        # Check structure
        first_segue = fs._segue_groups[0]
        assert 'segue_id' in first_segue
        assert 'pattern' in first_segue
        assert 'tracks' in first_segue
        assert first_segue['frequency'] == 'mandatory'
    
    def test_loads_rare_segues(self, segue_parquet_files, mock_feature_loaders):
        """Should load rare segues (lottery tickets) from parquet."""
        from phish_setlist_maker.analysis.feature_store import FeatureStore
        
        fs = FeatureStore(segue_parquet_files)
        fs.load()
        
        # Should have loaded 1 rare segue
        assert fs._rare_segues is not None
        assert len(fs._rare_segues) == 1
        
        # Check lottery metadata
        rare = fs._rare_segues[0]
        assert rare['frequency'] == 'rare'
        assert rare['is_lottery_ticket'] is True
        assert 'rarity_score' in rare
        assert 'lottery_weight' in rare
    
    def test_builds_segue_by_song_index(self, segue_parquet_files, mock_feature_loaders):
        """Should build index mapping songs to segue IDs."""
        from phish_setlist_maker.analysis.feature_store import FeatureStore
        
        fs = FeatureStore(segue_parquet_files)
        fs.load()
        
        # Mike's Song should map to its segue
        assert "Mike's Song" in fs._segue_by_song
        assert len(fs._segue_by_song["Mike's Song"]) >= 1
        
        # I Am Hydrogen should map to both its segues
        assert "I Am Hydrogen" in fs._segue_by_song
        assert len(fs._segue_by_song["I Am Hydrogen"]) >= 2
    
    def test_builds_segue_by_track_index(self, segue_parquet_files, mock_feature_loaders):
        """Should build index mapping track IDs to rare segues."""
        from phish_setlist_maker.analysis.feature_store import FeatureStore
        
        fs = FeatureStore(segue_parquet_files)
        fs.load()
        
        # Track 30447 (Tweezer 2015-08-22) should map to Caspian segue
        assert 30447 in fs._segue_by_track
        assert len(fs._segue_by_track[30447]) == 1
        assert fs._segue_by_track[30447][0]['pattern'] == 'Tweezer -> Prince Caspian'
    
    def test_get_mandatory_segues_for_song(self, segue_parquet_files, mock_feature_loaders):
        """Should retrieve mandatory segues for a given song."""
        from phish_setlist_maker.analysis.feature_store import FeatureStore
        
        fs = FeatureStore(segue_parquet_files)
        fs.load()
        
        # Get segues starting with Mike's Song
        segues = fs.get_mandatory_segues("Mike's Song")
        
        assert len(segues) >= 1
        assert all(s['frequency'] == 'mandatory' for s in segues)
        assert any("Mike's Song" in s['pattern'] for s in segues)
    
    def test_get_rare_segues_from_track(self, segue_parquet_files, mock_feature_loaders):
        """Should retrieve rare segues for a specific track ID."""
        from phish_setlist_maker.analysis.feature_store import FeatureStore
        
        fs = FeatureStore(segue_parquet_files)
        fs.load()
        
        # Get rare segues from Tweezer track 30447
        segues = fs.get_rare_segues_from_track(30447)
        
        assert len(segues) == 1
        assert segues[0]['pattern'] == 'Tweezer -> Prince Caspian'
        assert segues[0]['is_lottery_ticket'] is True
    
    def test_returns_empty_when_no_segues(self, segue_parquet_files, mock_feature_loaders):
        """Should return empty list for songs with no segues."""
        from phish_setlist_maker.analysis.feature_store import FeatureStore
        
        fs = FeatureStore(segue_parquet_files)
        fs.load()
        
        # Non-existent song
        segues = fs.get_mandatory_segues("Nonexistent Song")
        assert segues == []
        
        # Non-existent track
        rare = fs.get_rare_segues_from_track(99999)
        assert rare == []
    
    def test_graceful_fallback_when_files_missing(self, tmp_path, mock_feature_loaders):
        """Should handle missing segue files gracefully."""
        from phish_setlist_maker.analysis.feature_store import FeatureStore
        
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        fs = FeatureStore(empty_dir)
        fs.load()
        
        # Should initialize empty structures
        assert fs._segue_groups == []
        assert fs._rare_segues == []
        assert fs._segue_by_song == {}
        assert fs._segue_by_track == {}
    
    def test_tracks_field_preserved_as_list(self, segue_parquet_files, mock_feature_loaders):
        """Should preserve tracks field as list of integers."""
        from phish_setlist_maker.analysis.feature_store import FeatureStore
        
        fs = FeatureStore(segue_parquet_files)
        fs.load()
        
        segue = fs._segue_groups[0]
        assert isinstance(segue['tracks'], list)
        assert len(segue['tracks']) == 2
        assert all(isinstance(t, int) for t in segue['tracks'])
    
    def test_songs_field_preserved_as_list(self, segue_parquet_files, mock_feature_loaders):
        """Should preserve songs field as list of strings."""
        from phish_setlist_maker.analysis.feature_store import FeatureStore
        
        fs = FeatureStore(segue_parquet_files)
        fs.load()
        
        segue = fs._segue_groups[0]
        assert isinstance(segue['songs'], list)
        assert len(segue['songs']) == 2
        assert all(isinstance(s, str) for s in segue['songs'])


class TestFeatureStoreSegueFiltering:
    """Test filtering and lookup methods."""
    
    def test_filters_by_duration_budget(self, segue_parquet_files, mock_feature_loaders):
        """Should filter segues that fit duration budget."""
        from phish_setlist_maker.analysis.feature_store import FeatureStore
        
        fs = FeatureStore(segue_parquet_files)
        fs.load()
        
        segues = fs.get_mandatory_segues("I Am Hydrogen")
        
        # Filter to segues under 700 seconds
        short_segues = [s for s in segues if s['total_duration'] < 700]
        assert len(short_segues) >= 1
        
        # Verify all are under budget
        assert all(s['total_duration'] < 700 for s in short_segues)
    
    def test_sorts_by_likes_for_lottery(self, segue_parquet_files, mock_feature_loaders):
        """Should enable sorting rare segues by likes_count."""
        from phish_setlist_maker.analysis.feature_store import FeatureStore
        
        fs = FeatureStore(segue_parquet_files)
        fs.load()
        
        rare_segues = fs._rare_segues
        
        # Sort by lottery_weight (likes_count)
        sorted_segues = sorted(rare_segues, key=lambda s: s['lottery_weight'], reverse=True)
        
        # Highest weight should be first
        assert sorted_segues[0]['lottery_weight'] >= sorted_segues[-1]['lottery_weight']
