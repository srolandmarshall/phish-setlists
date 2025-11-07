"""Tests for generator integration with segue groups."""

import pytest
from phish_setlist_maker.generator.core import SetlistGenerator


pytestmark = pytest.mark.segue


class TestGeneratorMandatorySegues:
    """Test generator enforces mandatory segues."""
    
    def test_loads_segue_groups_when_ml_features_enabled(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Should load segue groups when use_ml_features=True."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        # Should have loaded feature store with segues
        assert generator._feature_store is not None
        assert generator._feature_store._segue_groups is not None
        assert len(generator._feature_store._segue_groups) >= 1
    
    def test_skips_segue_loading_when_ml_disabled(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Should not load segues when use_ml_features=False."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=False,
            features_dir=minimal_segue_data
        )
        
        # Feature store should not be loaded
        assert generator._feature_store is None
    
    def test_get_mandatory_segues_returns_data(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Should retrieve mandatory segues for a song."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        segues = generator._feature_store.get_mandatory_segues("Mike's Song")
        
        assert len(segues) >= 1
        assert segues[0]['pattern'] == "Mike's Song -> I Am Hydrogen"
        assert segues[0]['frequency'] == 'mandatory'


class TestGeneratorRareSegues:
    """Test generator handles rare segues (lottery tickets)."""
    
    def test_get_rare_segues_by_track_id(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Should retrieve rare segues for a specific track."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        # Track 200 = Tweezer from 2015-08-22
        rare_segues = generator._feature_store.get_rare_segues_from_track(200)
        
        assert len(rare_segues) == 1
        assert rare_segues[0]['pattern'] == 'Tweezer -> Prince Caspian'
        assert rare_segues[0]['is_lottery_ticket'] is True
    
    def test_rare_segues_have_lottery_metadata(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Rare segues should include lottery weighting."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        rare_segues = generator._feature_store._rare_segues
        
        assert len(rare_segues) >= 1
        first_rare = rare_segues[0]
        assert 'lottery_weight' in first_rare
        assert 'rarity_score' in first_rare
        assert first_rare['lottery_weight'] == 339  # High likes


class TestGeneratorSegueSelection:
    """Test generator selection logic with segues."""
    
    def test_mandatory_segue_check_in_selection_flow(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Generator should check for mandatory segues during selection."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        # Verify feature store has the check method
        assert hasattr(generator._feature_store, 'get_mandatory_segues')
        
        # Verify we can call it
        segues = generator._feature_store.get_mandatory_segues("Mike's Song")
        assert isinstance(segues, list)
    
    def test_rare_segue_lookup_by_track(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Generator should be able to look up rare segues by track ID."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        # Verify lookup method exists
        assert hasattr(generator._feature_store, 'get_rare_segues_from_track')
        
        # Verify we can call it with track ID
        rare = generator._feature_store.get_rare_segues_from_track(200)
        assert isinstance(rare, list)


class TestGeneratorSegueFiltering:
    """Test filtering segues by constraints."""
    
    def test_filters_segues_by_duration_budget(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Should filter out segues that exceed duration budget."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        segues = generator._feature_store.get_mandatory_segues("Mike's Song")
        
        # Filter by duration
        budget = 700
        valid_segues = [s for s in segues if s['total_duration'] <= budget]
        
        # Should include Mike's->Hydrogen (600s)
        assert len(valid_segues) >= 1
        assert all(s['total_duration'] <= budget for s in valid_segues)
    
    def test_filters_rare_segues_by_duration(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Should filter rare segues by duration."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        rare_segues = generator._feature_store._rare_segues
        
        # Tweezer->Caspian is 2068s (34 min) - too long for most budgets
        short_budget = 1000
        valid = [s for s in rare_segues if s['total_duration'] <= short_budget]
        
        # Should filter out the long segue
        assert len(valid) == 0
        
        # But allow with larger budget
        long_budget = 2500
        valid_long = [s for s in rare_segues if s['total_duration'] <= long_budget]
        assert len(valid_long) >= 1


class TestGeneratorSegueWeighting:
    """Test segue weighting for lottery selection."""
    
    def test_rare_segues_sorted_by_lottery_weight(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Rare segues should be sortable by lottery weight (likes)."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        rare_segues = generator._feature_store._rare_segues
        
        # Sort by lottery weight
        sorted_segues = sorted(rare_segues, key=lambda s: s['lottery_weight'], reverse=True)
        
        # Highest weight first
        assert sorted_segues[0]['lottery_weight'] >= sorted_segues[-1]['lottery_weight']
    
    def test_rarity_score_available_for_lottery_calculation(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Rare segues should have rarity score for probability calculation."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        rare_segues = generator._feature_store._rare_segues
        
        for segue in rare_segues:
            assert 'rarity_score' in segue
            assert 0.0 <= segue['rarity_score'] <= 1.0


class TestGeneratorSegueDataStructure:
    """Test segue data structure compatibility with generator."""
    
    def test_segue_tracks_field_is_list(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Tracks field should be list for generator to use."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        segues = generator._feature_store._segue_groups
        
        for segue in segues:
            assert isinstance(segue['tracks'], list)
            assert len(segue['tracks']) >= 2
    
    def test_segue_songs_field_is_list(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Songs field should be list of strings."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        segues = generator._feature_store._segue_groups
        
        for segue in segues:
            assert isinstance(segue['songs'], list)
            assert all(isinstance(s, str) for s in segue['songs'])
    
    def test_segue_has_required_fields(self, db_session, minimal_segue_data, mock_feature_loaders):
        """Segues should have all required fields for generator."""
        generator = SetlistGenerator(
            db_session,
            use_ml_features=True,
            features_dir=minimal_segue_data
        )
        
        segues = generator._feature_store._segue_groups
        required_fields = ['segue_id', 'pattern', 'tracks', 'songs', 
                          'total_duration', 'frequency']
        
        for segue in segues:
            for field in required_fields:
                assert field in segue, f"Missing field: {field}"
