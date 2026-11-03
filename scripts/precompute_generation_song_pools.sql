-- Rebuild date-addressable song frequency and set-placement snapshots.
-- Run after importing or updating the Phish.in shows/tracks/song links.
BEGIN;

CREATE TABLE IF NOT EXISTS public.generation_song_pool_snapshots (
    snapshot_date date NOT NULL,
    era text NOT NULL,
    canonical_set text NOT NULL,
    song_title text NOT NULL,
    appearance_count bigint NOT NULL,
    placement_probability double precision NOT NULL,
    PRIMARY KEY (snapshot_date, era, canonical_set, song_title)
);

ALTER TABLE public.generation_song_pool_snapshots
    ADD COLUMN IF NOT EXISTS placement_probability double precision;

CREATE TABLE IF NOT EXISTS public.generation_song_pool_metadata (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    source_signature text NOT NULL,
    built_at timestamptz NOT NULL DEFAULT now(),
    show_count bigint NOT NULL,
    track_count bigint NOT NULL,
    song_link_count bigint NOT NULL
);

TRUNCATE public.generation_song_pool_snapshots;

WITH eras(era, start_date, end_date) AS (
    VALUES
        ('all', DATE '0001-01-01', DATE '9999-12-31'),
        ('1.0', DATE '1983-01-01', DATE '1999-12-31'),
        ('2.0', DATE '2000-01-01', DATE '2004-08-15'),
        ('3.0', DATE '2009-03-06', DATE '2021-07-27'),
        ('4.0', DATE '2021-07-28', DATE '9999-12-31')
), daily AS (
    SELECT s.date AS snapshot_date,
           e.era,
           CASE lower(trim(t.set))
               WHEN '1' THEN 'set1' WHEN 'i' THEN 'set1' WHEN 'set1' THEN 'set1'
               WHEN '2' THEN 'set2' WHEN 'ii' THEN 'set2' WHEN 'set2' THEN 'set2'
               WHEN '3' THEN 'set3' WHEN 'iii' THEN 'set3' WHEN 'set3' THEN 'set3'
               WHEN 'e' THEN 'encore' WHEN 'encore' THEN 'encore'
               ELSE lower(trim(t.set))
           END AS canonical_set,
           coalesce(song.title, t.title) AS song_title,
           count(*)::bigint AS daily_count
      FROM public.shows s
      JOIN public.tracks t ON t.show_id = s.id
      JOIN eras e ON s.date BETWEEN e.start_date AND e.end_date
      LEFT JOIN public.songs_tracks st ON st.track_id = t.id
      LEFT JOIN public.songs song ON song.id = st.song_id
     GROUP BY s.date, e.era, canonical_set, song_title
), cumulative AS (
    SELECT snapshot_date, era, canonical_set, song_title,
           sum(daily_count) OVER (
               PARTITION BY era, canonical_set, song_title
               ORDER BY snapshot_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           )::bigint AS appearance_count
      FROM daily
), prepared AS (
    SELECT snapshot_date, era, canonical_set, song_title, appearance_count,
           appearance_count::double precision /
               sum(appearance_count) OVER (PARTITION BY snapshot_date, era, canonical_set)
               AS placement_probability
      FROM cumulative
)
INSERT INTO public.generation_song_pool_snapshots
    (snapshot_date, era, canonical_set, song_title, appearance_count, placement_probability)
SELECT snapshot_date, era, canonical_set, song_title, appearance_count, placement_probability
  FROM prepared;

ALTER TABLE public.generation_song_pool_snapshots
    ALTER COLUMN placement_probability SET NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        WITH eras(era, start_date, end_date) AS (
            VALUES
                ('all', DATE '0001-01-01', DATE '9999-12-31'),
                ('1.0', DATE '1983-01-01', DATE '1999-12-31'),
                ('2.0', DATE '2000-01-01', DATE '2004-08-15'),
                ('3.0', DATE '2009-03-06', DATE '2021-07-27'),
                ('4.0', DATE '2021-07-28', DATE '9999-12-31')
        ), expected AS (
            SELECT e.era,
                   CASE lower(trim(t.set))
                       WHEN '1' THEN 'set1' WHEN 'i' THEN 'set1' WHEN 'set1' THEN 'set1'
                       WHEN '2' THEN 'set2' WHEN 'ii' THEN 'set2' WHEN 'set2' THEN 'set2'
                       WHEN '3' THEN 'set3' WHEN 'iii' THEN 'set3' WHEN 'set3' THEN 'set3'
                       WHEN 'e' THEN 'encore' WHEN 'encore' THEN 'encore'
                       ELSE lower(trim(t.set))
                   END AS canonical_set,
                   coalesce(song.title, t.title) AS song_title,
                   count(*)::bigint AS appearance_count
              FROM public.shows s
              JOIN public.tracks t ON t.show_id = s.id
              JOIN eras e ON s.date BETWEEN e.start_date AND e.end_date
              LEFT JOIN public.songs_tracks st ON st.track_id = t.id
              LEFT JOIN public.songs song ON song.id = st.song_id
             GROUP BY e.era, canonical_set, song_title
        ), actual AS (
            SELECT DISTINCT ON (snapshot.era, snapshot.canonical_set, snapshot.song_title)
                   snapshot.era, snapshot.canonical_set, snapshot.song_title,
                   snapshot.appearance_count
              FROM public.generation_song_pool_snapshots snapshot
             ORDER BY snapshot.era, snapshot.canonical_set, snapshot.song_title,
                      snapshot.snapshot_date DESC
        ), differences AS (
            (SELECT * FROM expected EXCEPT SELECT * FROM actual)
            UNION ALL
            (SELECT * FROM actual EXCEPT SELECT * FROM expected)
        )
        SELECT 1 FROM differences
    ) THEN
        RAISE EXCEPTION 'Prepared song-pool parity check failed against direct historical aggregates';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS generation_song_pool_lookup_idx
    ON public.generation_song_pool_snapshots (era, snapshot_date DESC, canonical_set);

WITH source AS (
    SELECT (SELECT count(*) FROM public.shows) AS show_count,
           (SELECT count(*) FROM public.tracks) AS track_count,
           (SELECT count(*) FROM public.songs_tracks) AS song_link_count,
           (SELECT coalesce(max(id), 0) FROM public.shows) AS max_show_id,
           (SELECT coalesce(max(updated_at)::text, '') FROM public.shows) AS latest_show_update,
           (SELECT coalesce(max(id), 0) FROM public.tracks) AS max_track_id,
           (SELECT coalesce(max(id), 0) FROM public.songs_tracks) AS max_song_link_id
)
INSERT INTO public.generation_song_pool_metadata
    (singleton, source_signature, built_at, show_count, track_count, song_link_count)
SELECT true,
       md5(show_count || ':' || track_count || ':' || song_link_count || ':' ||
           max_show_id || ':' || latest_show_update || ':' || max_track_id || ':' || max_song_link_id),
       now(), show_count, track_count, song_link_count
  FROM source
ON CONFLICT (singleton) DO UPDATE
    SET source_signature = EXCLUDED.source_signature,
        built_at = EXCLUDED.built_at,
        show_count = EXCLUDED.show_count,
        track_count = EXCLUDED.track_count,
        song_link_count = EXCLUDED.song_link_count;

CREATE OR REPLACE FUNCTION public.invalidate_generation_song_pool_artifacts()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE public.generation_song_pool_metadata
       SET source_signature = 'stale'
     WHERE singleton;
    RETURN NULL;
END $$;

DO $$
DECLARE source_table text;
BEGIN
    FOREACH source_table IN ARRAY ARRAY['shows', 'tracks', 'songs_tracks', 'songs'] LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS invalidate_generation_song_pool_artifacts ON public.%I',
            source_table
        );
        EXECUTE format(
            'CREATE TRIGGER invalidate_generation_song_pool_artifacts '
            'AFTER INSERT OR UPDATE OR DELETE ON public.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION public.invalidate_generation_song_pool_artifacts()',
            source_table
        );
        EXECUTE format(
            'DROP TRIGGER IF EXISTS invalidate_generation_song_pool_artifacts_truncate ON public.%I',
            source_table
        );
        EXECUTE format(
            'CREATE TRIGGER invalidate_generation_song_pool_artifacts_truncate '
            'AFTER TRUNCATE ON public.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION public.invalidate_generation_song_pool_artifacts()',
            source_table
        );
    END LOOP;
END $$;

COMMIT;
