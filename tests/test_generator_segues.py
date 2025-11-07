"""Regression tests for segue-aware generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from random import Random
from typing import Dict, Iterable, List, Sequence, Tuple

from phish_setlist_maker.generator.core import SetlistGenerator
from phish_setlist_maker.models.show import Show
from phish_setlist_maker.models.track import Track
from sqlalchemy.orm import Session


def _seed_show(
    session: Session,
    show_date: date,
    sets: Dict[str, Sequence[Tuple[str, int]]],
) -> None:
    """Minimal helper to seed tracks for testing."""
    timestamp = datetime.combine(show_date, datetime.min.time())
    show = Show(
        date=show_date,
        created_at=timestamp,
        updated_at=timestamp,
        venue_name="Test Venue",
        duration=0,
    )
    session.add(show)
    session.flush()

    for set_label, tracks in sets.items():
        for position, (title, duration_seconds) in enumerate(tracks, start=1):
            session.add(
                Track(
                    show_id=show.id,
                    title=title,
                    position=position,
                    duration=duration_seconds * 1000,
                    set=set_label,
                    slug=f"{title.lower().replace(' ', '-')}-{show_date.isoformat()}-{position}",
                )
            )

    session.flush()


@dataclass
class _DummyTransition:
    lift: float = 0.0


class _FakeFeatureStore:
    """Lightweight stub containing two mandatory segue chains."""

    def __init__(self) -> None:
        self._patterns: List[List[str]] = [
            ["Song Alpha", "Song Beta"],
            ["Song Gamma", "Song Delta"],
        ]

    def get_mandatory_segues(self, song_title: str) -> List[Dict[str, List[str]]]:
        return [{"songs": pattern} for pattern in self._patterns if song_title in pattern]

    def get_mandatory_next_songs(self, from_song: str) -> set[str]:
        next_songs: set[str] = set()
        for pattern in self._patterns:
            if from_song in pattern:
                idx = pattern.index(from_song)
                if idx + 1 < len(pattern):
                    next_songs.add(pattern[idx + 1])
        return next_songs

    def violates_ordering_constraint(self, songs_so_far: List[str], candidate_song: str) -> bool:
        return False

    def violates_cross_set_dependency(
        self,
        candidate_song: str,
        target_set: str,
        previous_sets_songs: Dict[str, List[str]],
    ) -> bool:
        return False

    def is_forbidden_transition(self, from_song: str, to_song: str) -> bool:
        return False

    def get_transition_lift(self, from_song: str, to_song: str) -> _DummyTransition | None:
        return None

    def get_placement_probability(self, song_title: str, target_set: str) -> float:
        return 0.0

    def get_song_features(self, song_title: str):
        return None

    def get_set_enders_for_set(self, canonical_set: str, min_probability: float = 0.0) -> list:
        return []


class _DeterministicGenerator(SetlistGenerator):
    """Override weighted pick so we can control the selection order."""

    def __init__(self, *args, planned_choices: Sequence[str], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._planned_choices = list(planned_choices)
        self._choice_idx = 0

    def _weighted_pick(self, *args, **kwargs):
        if self._choice_idx < len(self._planned_choices):
            choice = self._planned_choices[self._choice_idx]
            self._choice_idx += 1
            return choice
        return super()._weighted_pick(*args, **kwargs)


def test_generator_respects_max_segues_per_set(db_session: Session) -> None:
    """Even without playlist prep, generator should stop adding new patterns after the cap."""

    show_date = date(2024, 1, 1)
    _seed_show(
        db_session,
        show_date,
        {
            "1": [
                ("Song Alpha", 300),
                ("Song Beta", 300),
                ("Song Gamma", 300),
                ("Song Delta", 300),
                ("Song Other 1", 240),
                ("Song Other 2", 240),
                ("Song Other 3", 240),
                ("Song Other 4", 240),
            ],
            "2": [("Song Encore Seed", 200)],
        },
    )

    generator = _DeterministicGenerator(
        db_session,
        rng=Random(0),
        adjacency_bonus=0.0,
            planned_choices=[
                "Song Alpha",  # First mandatory chain should be allowed
                "Song Gamma",  # Second mandatory chain should be skipped due to cap
                "Song Other 1",
                "Song Other 2",
                "Song Other 3",
                "Song Other 4",
            ],
        )
    generator._feature_store = _FakeFeatureStore()
    generator._use_ml_features = True

    generated = generator.generate(
        reference_date=show_date,
        num_sets=2,
        include_encore=False,
        set_lengths={"set1": 6, "set2": 1},
        exclude_previous_show=False,
        max_segues_per_set=1,
    )

    set1_songs = generated.sets[0].songs

    # First pattern should survive intact
    assert "Song Alpha" in set1_songs
    assert "Song Beta" in set1_songs

    # Second pattern must be rejected once the cap is reached
    assert "Song Gamma" not in set1_songs
    assert "Song Delta" not in set1_songs

    # Remaining slots should be filled with other songs
    assert any(song.startswith("Song Other") for song in set1_songs)
    assert len(set1_songs) == 6
