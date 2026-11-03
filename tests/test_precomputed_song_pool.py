from datetime import date

import pytest
from sqlalchemy import text

from phish_setlist_maker.generator.historical import song_frequencies_by_set


def test_precomputed_pool_keeps_songs_absent_from_latest_show_date(db_session):
    """A song's last cumulative row may predate the latest show date."""
    if db_session.get_bind().dialect.name != "postgresql":
        pytest.skip("Precomputed song-pool snapshots use PostgreSQL-specific SQL")

    db_session.execute(text("""
        CREATE TABLE public.generation_song_pool_snapshots (
            snapshot_date date NOT NULL,
            era text NOT NULL,
            canonical_set text NOT NULL,
            song_title text NOT NULL,
            appearance_count bigint NOT NULL,
            placement_probability double precision NOT NULL
        )
    """))
    db_session.execute(text("""
        CREATE TABLE public.generation_song_pool_metadata (
            singleton boolean PRIMARY KEY,
            source_signature text NOT NULL
        )
    """))
    db_session.execute(text("""
        INSERT INTO public.generation_song_pool_metadata (singleton, source_signature)
        VALUES (true, 'test-snapshot')
    """))
    db_session.execute(text("""
        INSERT INTO public.generation_song_pool_snapshots
            (snapshot_date, era, canonical_set, song_title, appearance_count,
             placement_probability)
        VALUES
            ('2020-01-01', '1.0', 'set1', 'Historical Song', 3, 1.0),
            ('2020-01-02', '1.0', 'set1', 'Latest Show Song', 1, 1.0)
    """))

    frequencies = song_frequencies_by_set(
        db_session,
        cutoff_date=date(2020, 1, 2),
        era="1.0",
    )

    songs = {song.title: song for song in frequencies["set1"]}
    assert set(songs) == {"Historical Song", "Latest Show Song"}
    assert songs["Historical Song"].count == 3
    assert songs["Historical Song"].weight == pytest.approx(0.75)
    assert songs["Latest Show Song"].count == 1
    assert songs["Latest Show Song"].weight == pytest.approx(0.25)
