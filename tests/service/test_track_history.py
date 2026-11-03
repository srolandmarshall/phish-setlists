from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from phish_setlist_maker.models import Base, Track
from phish_setlist_maker.service.track_history import query_following_tracks_from_show


@pytest.fixture
def track_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_query_following_tracks_stays_within_same_show_and_set(track_session):
    track_session.add_all(
        [
            Track(id=1, show_id=10, title="Source", position=1, set="set1", slug="source"),
            Track(id=2, show_id=10, title="Next", position=2, set="set1", slug="next"),
            Track(id=3, show_id=10, title="Other Set", position=3, set="set2", slug="other-set"),
            Track(id=4, show_id=11, title="Other Show", position=2, set="set1", slug="other-show"),
            Track(id=5, show_id=10, title="Later", position=4, set="set1", slug="later"),
        ]
    )
    track_session.flush()

    following = query_following_tracks_from_show(track_session, track_id=1, max_tracks=1)

    assert following == [{"track_id": 2, "title": "Next", "position": 2}]


def test_query_following_tracks_returns_empty_for_missing_source(track_session):
    assert query_following_tracks_from_show(track_session, track_id=999) == []
