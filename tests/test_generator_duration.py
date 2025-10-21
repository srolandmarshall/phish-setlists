"""Duration-aware generator behaviors."""

from __future__ import annotations

from datetime import date, datetime
from random import Random
from typing import Dict, Iterable, Tuple

from phish_setlist_maker.generator import random_set_lengths
from phish_setlist_maker.generator.core import SetlistGenerator
from phish_setlist_maker.models.show import Show
from phish_setlist_maker.models.track import Track
from sqlalchemy.orm import Session


def _seed_show(
    session: Session,
    show_date: date,
    sets: Dict[str, Iterable[Tuple[str, int]]],
) -> None:
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
            track = Track(
                show_id=show.id,
                title=title,
                position=position,
                duration=int(duration_seconds * 1000),
                set=set_label,
                slug=f"{title.lower().replace(' ', '-')}-{show_date.isoformat()}-{position}",
            )
            session.add(track)

    session.flush()


def test_duration_budget_limits_song_count(db_session: Session) -> None:
    """Long songs should trim the final count to keep runtime near the target window."""

    long_set = [
        ("Epic Jam I", 45 * 60),
        ("Epic Jam II", 45 * 60),
        ("Epic Jam III", 45 * 60),
    ]
    supporting_set = [
        ("Quick Tune A", 5 * 60),
        ("Quick Tune B", 5 * 60),
        ("Quick Tune C", 5 * 60),
        ("Quick Tune D", 5 * 60),
    ]
    _seed_show(
        db_session,
        date(2024, 1, 1),
        {
            "1": long_set,
            "2": supporting_set,
        },
    )

    generator = SetlistGenerator(db_session, rng=Random(1), adjacency_bonus=0.0)

    generated = generator.generate(
        reference_date=date(2024, 1, 1),
        num_sets=2,
        include_encore=False,
        set_lengths={"set1": 3, "set2": 4},
        exclude_previous_show=False,
    )

    set1 = generated.sets[0]
    assert len(set1.songs) == 2
    assert set(set1.songs).issubset({title for title, _ in long_set})

    notes = generated.metadata.notes
    assert any(note.startswith("Capped Set 1 at 2 songs") for note in notes)
    assert not any("Only selected 2/3 songs for Set 1" in note for note in notes)


def test_random_set_lengths_prefers_duration_aligned_counts(db_session: Session) -> None:
    """Histogram sampling should lean toward counts whose runtimes match target ranges."""

    long_set = [
        ("Epic Jam I", 45 * 60),
        ("Epic Jam II", 45 * 60),
        ("Epic Jam III", 45 * 60),
    ]
    balanced_set = [
        ("Balanced Jam I", 15 * 60),
        ("Balanced Jam II", 15 * 60),
        ("Balanced Jam III", 15 * 60),
        ("Balanced Jam IV", 15 * 60),
        ("Balanced Jam V", 15 * 60),
        ("Balanced Jam VI", 15 * 60),
    ]
    supporting_set = [
        ("Quick Tune A", 5 * 60),
        ("Quick Tune B", 5 * 60),
        ("Quick Tune C", 5 * 60),
        ("Quick Tune D", 5 * 60),
    ]

    _seed_show(
        db_session,
        date(2024, 1, 1),
        {
            "1": long_set,
            "2": supporting_set,
        },
    )
    _seed_show(
        db_session,
        date(2024, 1, 2),
        {
            "1": balanced_set,
            "2": supporting_set,
        },
    )

    lengths = random_set_lengths(
        db_session,
        reference_date=date(2024, 1, 2),
        num_sets=2,
        include_encore=False,
        rng=Random(7),
    )

    assert lengths["set1"] == 6
