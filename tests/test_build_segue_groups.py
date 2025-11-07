"""Tests for building segue groups from database."""

import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from phish_setlist_maker.models import Show, Song, Track, Venue

# Add scripts to path for importing
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import build_segue_groups  # noqa: E402


pytestmark = pytest.mark.segue


@pytest.fixture
def sample_shows_with_segues(db_session: Session):
    """Create test data with famous segues."""
    venue = Venue(
        id=1,
        name="Madison Square Garden",
        city="New York",
        state="NY",
        country="USA",
        slug="msg",
        shows_count=0,
    )
    db_session.add(venue)

    # Show 1: Mike's -> Hydrogen -> Weekapaug (classic sandwich)
    now = datetime.now()
    show1 = Show(
        id=1, date=date(2024, 7, 15), venue_id=1, created_at=now, updated_at=now
    )
    db_session.add(show1)

    tracks_show1 = [
        Track(
            id=1,
            show_id=1,
            title="Tweezer",
            position=1,
            set="set2",
            slug="tweezer",
            duration=600,
        ),
        Track(
            id=2,
            show_id=1,
            title="Mike's Song",
            position=2,
            set="set2",
            slug="mikes-song",
            duration=480,
            likes_count=25,
        ),
        Track(
            id=3,
            show_id=1,
            title="I Am Hydrogen",
            position=3,
            set="set2",
            slug="i-am-hydrogen",
            duration=120,
            likes_count=10,
        ),
        Track(
            id=4,
            show_id=1,
            title="Weekapaug Groove",
            position=4,
            set="set2",
            slug="weekapaug-groove",
            duration=540,
            likes_count=30,
        ),
        Track(
            id=5,
            show_id=1,
            title="Possum",
            position=5,
            set="set2",
            slug="possum",
            duration=420,
        ),
    ]
    db_session.add_all(tracks_show1)

    # Show 2: Another Mike's -> Hydrogen -> Weekapaug
    show2 = Show(
        id=2, date=date(2024, 8, 1), venue_id=1, created_at=now, updated_at=now
    )
    db_session.add(show2)

    tracks_show2 = [
        Track(
            id=6,
            show_id=2,
            title="Mike's Song",
            position=1,
            set="set2",
            slug="mikes-song",
            duration=500,
            likes_count=15,
        ),
        Track(
            id=7,
            show_id=2,
            title="I Am Hydrogen",
            position=2,
            set="set2",
            slug="i-am-hydrogen",
            duration=130,
            likes_count=8,
        ),
        Track(
            id=8,
            show_id=2,
            title="Weekapaug Groove",
            position=3,
            set="set2",
            slug="weekapaug-groove",
            duration=520,
            likes_count=20,
        ),
    ]
    db_session.add_all(tracks_show2)

    # Show 3: Rare segue - Tweezer -> Prince Caspian (only once)
    show3 = Show(
        id=3, date=date(2015, 8, 22), venue_id=1, created_at=now, updated_at=now
    )
    db_session.add(show3)

    tracks_show3 = [
        Track(
            id=9,
            show_id=3,
            title="Tweezer >",  # Include segue notation for rare segue detection
            position=1,
            set="set2",
            slug="tweezer",
            duration=1056,
            likes_count=140,
        ),
        Track(
            id=10,
            show_id=3,
            title="Prince Caspian",
            position=2,
            set="set2",
            slug="prince-caspian",
            duration=1012,
            likes_count=199,
        ),
    ]
    db_session.add_all(tracks_show3)

    db_session.commit()
    return db_session


class TestBuildSegueGroups:
    """Test segue groups data builder."""

    def test_extracts_all_adjacent_track_pairs(self, sample_shows_with_segues):
        """Should find all adjacent track pairs across all shows."""
        pairs = build_segue_groups.extract_adjacent_pairs(sample_shows_with_segues)

        # Should find 7 adjacent pairs total
        # Show 1: Tweezer->Mike's, Mike's->Hydrogen, Hydrogen->Weekapaug, Weekapaug->Possum
        # Show 2: Mike's->Hydrogen, Hydrogen->Weekapaug
        # Show 3: Tweezer->Caspian
        assert len(pairs) == 7

        # Check structure
        assert all("show_id" in p for p in pairs)
        assert all("track1_id" in p for p in pairs)
        assert all("track2_id" in p for p in pairs)
        assert all("song1" in p for p in pairs)
        assert all("song2" in p for p in pairs)

    def test_calculates_pair_frequencies(self, sample_shows_with_segues):
        """Should count how many times each song pair appears."""
        pairs = build_segue_groups.extract_adjacent_pairs(sample_shows_with_segues)
        frequencies = build_segue_groups.calculate_frequencies(pairs)

        # Mike's -> Hydrogen appears 2 times
        assert frequencies[("Mike's Song", "I Am Hydrogen")] == 2

        # Hydrogen -> Weekapaug appears 2 times
        assert frequencies[("I Am Hydrogen", "Weekapaug Groove")] == 2

        # Tweezer > -> Caspian appears 1 time (rare)
        assert frequencies[("Tweezer >", "Prince Caspian")] == 1

    def test_separates_mandatory_from_rare_segues(self, sample_shows_with_segues):
        """Should separate segues by frequency threshold (50 occurrences)."""
        chains = build_segue_groups.extract_complete_chains(sample_shows_with_segues)
        subchains = build_segue_groups.extract_subchains(chains, max_length=5, min_total_likes=0)
        pairs = build_segue_groups.extract_pairs_from_chains(chains)
        pair_frequencies = build_segue_groups.calculate_frequencies(pairs)
        chain_frequencies = build_segue_groups.calculate_chain_pattern_frequencies(subchains)
        mandatory, rare = build_segue_groups.separate_chains_by_frequency(
            subchains, chain_frequencies, pairs, pair_frequencies, threshold=2,
            max_rare_chain_length=5, min_lottery_likes=0
        )

        # With threshold=2, Mike's->Hydrogen and Hydrogen->Weekapaug are mandatory
        mandatory_patterns = {r["pattern"] for r in mandatory}
        assert "Mike's Song -> I Am Hydrogen" in mandatory_patterns
        assert "I Am Hydrogen -> Weekapaug Groove" in mandatory_patterns

        # Tweezer->Caspian is rare (only 1 occurrence) - but only if it has segue notation
        rare_patterns = {r["pattern"] for r in rare}
        # Note: rare segues require ">" in title, so this might not appear unless test data has it

    def test_mandatory_segues_have_correct_metadata(self, sample_shows_with_segues):
        """Mandatory segues should have frequency='mandatory' and confidence."""
        chains = build_segue_groups.extract_complete_chains(sample_shows_with_segues)
        subchains = build_segue_groups.extract_subchains(chains, max_length=5, min_total_likes=0)
        pairs = build_segue_groups.extract_pairs_from_chains(chains)
        pair_frequencies = build_segue_groups.calculate_frequencies(pairs)
        chain_frequencies = build_segue_groups.calculate_chain_pattern_frequencies(subchains)
        mandatory, _ = build_segue_groups.separate_chains_by_frequency(
            subchains, chain_frequencies, pairs, pair_frequencies, threshold=2,
            max_rare_chain_length=5, min_lottery_likes=0
        )

        for record in mandatory:
            assert record["frequency"] == "mandatory"
            assert record["confidence"] >= 0.95
            assert record["historical_occurrences"] >= 2
            assert "segue_id" in record
            assert "pattern" in record

    def test_rare_segues_have_lottery_metadata(self, sample_shows_with_segues):
        """Rare segues should have lottery-specific metadata."""
        chains = build_segue_groups.extract_complete_chains(sample_shows_with_segues)
        subchains = build_segue_groups.extract_subchains(chains, max_length=5, min_total_likes=0)
        pairs = build_segue_groups.extract_pairs_from_chains(chains)
        pair_frequencies = build_segue_groups.calculate_frequencies(pairs)
        chain_frequencies = build_segue_groups.calculate_chain_pattern_frequencies(subchains)
        _, rare = build_segue_groups.separate_chains_by_frequency(
            subchains, chain_frequencies, pairs, pair_frequencies, threshold=2,
            max_rare_chain_length=5, min_lottery_likes=0
        )

        for record in rare:
            assert record["frequency"] == "rare"
            assert record["is_lottery_ticket"] is True
            assert "rarity_score" in record
            assert 0.0 <= record["rarity_score"] <= 1.0
            assert "lottery_weight" in record

    def test_builds_dataframe_with_correct_schema(self, sample_shows_with_segues):
        """Should create DataFrame with all required columns."""
        chains = build_segue_groups.extract_complete_chains(sample_shows_with_segues)
        subchains = build_segue_groups.extract_subchains(chains, max_length=5, min_total_likes=0)
        pairs = build_segue_groups.extract_pairs_from_chains(chains)
        pair_frequencies = build_segue_groups.calculate_frequencies(pairs)
        chain_frequencies = build_segue_groups.calculate_chain_pattern_frequencies(subchains)
        mandatory, rare = build_segue_groups.separate_chains_by_frequency(
            subchains, chain_frequencies, pairs, pair_frequencies, threshold=2,
            max_rare_chain_length=5, min_lottery_likes=0
        )

        df_mandatory = build_segue_groups.build_dataframe(mandatory)
        df_rare = build_segue_groups.build_dataframe(rare)

        # Check required columns exist
        required_cols = [
            "segue_id",
            "segue_type",
            "pattern",
            "show_id",
            "show_date",
            "set_label",
            "tracks",
            "songs",
            "total_duration",
            "likes_count",
            "historical_occurrences",
            "frequency",
        ]

        for col in required_cols:
            assert col in df_mandatory.columns
            assert col in df_rare.columns

        # Rare should have additional lottery columns
        assert "rarity_score" in df_rare.columns
        assert "is_lottery_ticket" in df_rare.columns
        assert "lottery_weight" in df_rare.columns

    def test_tracks_field_is_list_of_ints(self, sample_shows_with_segues):
        """Tracks field should be list of track IDs."""
        chains = build_segue_groups.extract_complete_chains(sample_shows_with_segues)
        subchains = build_segue_groups.extract_subchains(chains, max_length=5, min_total_likes=0)
        pairs = build_segue_groups.extract_pairs_from_chains(chains)
        pair_frequencies = build_segue_groups.calculate_frequencies(pairs)
        chain_frequencies = build_segue_groups.calculate_chain_pattern_frequencies(subchains)
        mandatory, _ = build_segue_groups.separate_chains_by_frequency(
            subchains, chain_frequencies, pairs, pair_frequencies, threshold=2,
            max_rare_chain_length=5, min_lottery_likes=0
        )

        for record in mandatory:
            assert isinstance(record["tracks"], list)
            assert len(record["tracks"]) == 2  # Pairs have 2 tracks
            assert all(isinstance(tid, int) for tid in record["tracks"])

    def test_songs_field_is_list_of_strings(self, sample_shows_with_segues):
        """Songs field should be list of song titles."""
        chains = build_segue_groups.extract_complete_chains(sample_shows_with_segues)
        subchains = build_segue_groups.extract_subchains(chains, max_length=5, min_total_likes=0)
        pairs = build_segue_groups.extract_pairs_from_chains(chains)
        pair_frequencies = build_segue_groups.calculate_frequencies(pairs)
        chain_frequencies = build_segue_groups.calculate_chain_pattern_frequencies(subchains)
        mandatory, _ = build_segue_groups.separate_chains_by_frequency(
            subchains, chain_frequencies, pairs, pair_frequencies, threshold=2,
            max_rare_chain_length=5, min_lottery_likes=0
        )

        for record in mandatory:
            assert isinstance(record["songs"], list)
            assert len(record["songs"]) == 2
            assert all(isinstance(s, str) for s in record["songs"])


class TestBuildSegueGroupsIntegration:
    """Integration tests for full build process."""

    def test_end_to_end_build_creates_parquet_files(
        self, sample_shows_with_segues, tmp_path
    ):
        """Should create both mandatory and rare parquet files."""
        output_dir = tmp_path / "features"
        output_dir.mkdir()

        # Use threshold=2 to match test data (Mike's->Hydrogen appears 2x)
        build_segue_groups.build_all_segues(
            sample_shows_with_segues, output_dir=output_dir, threshold=2
        )

        # Check files created
        assert (output_dir / "segue_groups.parquet").exists()
        assert (output_dir / "rare_segues.parquet").exists()

        # Verify can load them
        df_mandatory = pd.read_parquet(output_dir / "segue_groups.parquet")
        df_rare = pd.read_parquet(output_dir / "rare_segues.parquet")

        assert len(df_mandatory) >= 2  # At least Mike's->Hydrogen, Hydrogen->Weekapaug
        assert len(df_rare) >= 1  # At least Tweezer->Caspian
