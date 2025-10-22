# Database Schema Audit (2025-10-20)

## Sources consulted
- `data/schema.rb` (Rails schema dump, version 2025-07-19)
- `src/phish_setlist_maker/models/*.py` (SQLAlchemy ORM definitions)

This note inventories the database tables that drive setlist generation, highlights gaps between the Python ORM and the canonical Rails schema, and outlines follow-up checks for data quality.

---

## Core performance tables

### `shows`
- **Columns**: `id`, `date`, `venue_id`, `tour_id`, `duration`, `likes_count`, `tags_count`, `venue_name`, `matches_pnet`, `cover_art_*` fields, `album_zip_requested_at`, `performance_gap_value`, `audio_status`, timestamps.
- **Indexes**: unique constraint on `date`; multiple functional indexes for month/day/year and audio filters.
- **ORM coverage**: `Show` model includes all of the above except the functional indexes (handled implicitly). No discrepancies detected.

### `tracks`
- **Columns**: `id`, `show_id`, `title`, `position`, `duration`, `set`, `likes_count`, `slug`, `tags_count`, `jam_starts_at_second`, `exclude_from_stats`, `audio_status`, timestamps.
- **Indexes**: uniqueness on `(show_id, position)` and `(show_id, slug)`; set-based filters to accelerate stats queries.
- **ORM coverage**: `Track` model **omits** `created_at`, `updated_at`, `exclude_from_stats`, and `audio_status`, but adds `audio_file_data`, `waveform_png_data`, and `metadata_cache` columns that are not present in `schema.rb`. We need to confirm whether the production DB includes these JSON/text fields or if they exist only in the Python layer.

### `songs`
- **Columns**: `id`, `title`, `slug`, `tracks_count`, `tracks_with_audio_count`, `original`, `alias`, `lyrics`, `artist`, timestamps.
- **Indexes**: uniqueness on `alias` (nullable), plus supporting indexes on `original`.
- **ORM coverage**: `Song` model misses `created_at`, `updated_at`, and `tracks_with_audio_count`. Consider extending the model or documenting that we intentionally ignore those fields.

### `songs_tracks` (association)
- **Columns**: `id`, `song_id`, `track_id`, `previous_performance_gap`, `previous_performance_slug`, `next_performance_gap`, `next_performance_slug`, plus *_with_audio variants.
- **Indexes**: uniqueness on `(track_id, song_id)` and supporting indexes for gap lookups.
- **ORM coverage**: `SongTrack` model only exposes the base gap/slug fields; *_with_audio columns are currently unavailable to Python code. Decide whether to map them or treat them as analytics-only.

---

## Supporting tables

### `tours`
- **Columns**: `id`, `name`, `starts_on`, `ends_on`, `slug`, `shows_count`, `shows_with_audio_count`, timestamps.
- **ORM coverage**: `Tour` model lacks `created_at`, `updated_at`, and `shows_with_audio_count`.

### `venues`
- **Columns**: `id`, `name`, `city`, `state`, `country`, `slug`, `shows_count`, `shows_with_audio_count`, `latitude`, `longitude`, `abbrev`, timestamps.
- **ORM coverage**: `Venue` model omits the timestamp columns and `shows_with_audio_count`.

### `track_tags`, `tags`, `playlists`, `playlist_tracks`
- Present in the schema but not represented in SQLAlchemy. They can drive future analytics (e.g., jam tags, curated playlists) if we decide to expose them.

### Rails/ancillary tables
- Authentication (`users`, `authentications`), API keys, Active Storage tables, etc. These are likely irrelevant for our ML work but worth knowing in case we ingest user-generated signals later.

---

## Data coverage checks

We attempted to run coverage queries (counts, min/max dates, missing durations) via `phish_setlist_maker.db.session_scope`, but the CLI sandbox denied TCP connections to Postgres (`OperationalError: connection ... failed: Operation not permitted`). To reproduce locally:

```bash
poetry run python scripts/audit_database.py
```

Suggested checks once connectivity is available:
- Total number of shows and date range (expect 1983‒present).
- Track volume per era and percentage with `duration = 0`.
- Count of tracks where `set` is null/empty or flagged `exclude_from_stats = true`.
- Distinct song count and proportion with missing `slug`/`alias`.

### Coverage metrics (2025-10-20)
Output from `poetry run python scripts/audit_database.py` on the local dataset:

```
=== Show Coverage ===
Total shows      : 2,104
Date range       : 1983-12-02 → 2025-09-21

=== Track Coverage ===
Total tracks             : 38,499
Tracks w/ zero duration  : 1,794
Tracks missing set label : 0
 - zero duration pct     : 4.66%
 - missing set pct       : 0.00%

=== Songs & Links ===
Total songs        : 973
Songs with alias   : 13
 - alias coverage  : 1.34%
Song↔Track links   : 39,244
```

Future audits should append fresh snapshots here to track drift.

---

## Follow-ups
1. **Resolve ORM/schema drift**: document whether `metadata_cache` and similar columns exist in the live database. Align models or add Alembic migrations if needed.
2. **Expose missing columns**: decide if we need timestamp fields or audio gap metrics in Python for analytics.
3. **Diagram**: optionally generate an ER diagram (e.g., with `schemaspy` or `sqlacodegen`) once DB access is available.
