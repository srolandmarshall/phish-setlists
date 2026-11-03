#!/usr/bin/env bash

set -euo pipefail

# Keep these values pinned to the reviewed S3 snapshot.
expected_sql_sha256="855b57333b92484e4c0d0d0d3a025b787abbeb63455e564f733bbdd76d4c81d0"
seed_s3_uri="${PHISHIN_DEV_SQL_S3_URI:-s3://srm-builds/phish-setlists/database-seeds/phishin-dev.sql}"
sql_file="${PHISHIN_DEV_SQL_FILE:-}"
temporary_sql=""

PGHOST="${PGHOST:-${DB_HOST:-localhost}}"
PGPORT="${PGPORT:-${DB_PORT:-5432}}"
PGUSER="${PGUSER:-${DB_USER:-}}"
PGPASSWORD="${PGPASSWORD:-${DB_PASS:-}}"
export PGHOST PGPORT PGUSER PGPASSWORD

if [[ -z "$PGUSER" ]]; then
  echo "Set PGUSER or DB_USER to a PostgreSQL role with CREATEDB and restore permissions." >&2
  exit 2
fi

target_db="${TARGET_DB:-phish-setlist-maker-dev-$(date +%Y%m%d)}"
if [[ ! "$target_db" =~ ^[A-Za-z0-9_-]{1,63}$ ]]; then
  echo "TARGET_DB must be a PostgreSQL identifier using letters, digits, '_' or '-' (max 63 characters)." >&2
  exit 2
fi

database_created=0
refresh_complete=0
cleanup() {
  local status=$?
  if [[ "$database_created" == "1" && "$refresh_complete" != "1" ]]; then
    dropdb --if-exists --maintenance-db=postgres "$target_db" >/dev/null 2>&1 || true
  fi
  if [[ -n "$temporary_sql" ]]; then
    rm -f -- "$temporary_sql"
  fi
  return "$status"
}
trap cleanup EXIT

if [[ -z "$sql_file" ]]; then
  temporary_sql="$(mktemp "${TMPDIR:-/tmp}/phishin-dev.XXXXXX.sql")"
  sql_file="$temporary_sql"
  aws s3 cp "$seed_s3_uri" "$sql_file" --no-progress
elif [[ ! -r "$sql_file" ]]; then
  echo "PHISHIN_DEV_SQL_FILE is not readable: $sql_file" >&2
  exit 2
fi

actual_sql_sha256="$(shasum -a 256 "$sql_file" | awk '{print $1}')"
if [[ "$actual_sql_sha256" != "$expected_sql_sha256" ]]; then
  echo "Seed SQL checksum mismatch; refusing to execute an unreviewed dump." >&2
  echo "Expected: $expected_sql_sha256" >&2
  echo "Actual:   $actual_sql_sha256" >&2
  exit 2
fi

server_version_num="$(psql -XAtq --dbname=postgres --command='SHOW server_version_num')"
if (( server_version_num < 170000 )); then
  echo "The Phish.in development dump requires PostgreSQL 17 or newer (server version: $server_version_num)." >&2
  exit 2
fi

exists="$(psql -XAtq --dbname=postgres --command="SELECT 1 FROM pg_database WHERE datname = '$target_db'")"
if [[ "$exists" == "1" ]]; then
  echo "Database '$target_db' already exists; choose a new TARGET_DB. Existing databases are never dropped." >&2
  exit 2
fi

createdb --maintenance-db=postgres --owner="$PGUSER" "$target_db"
database_created=1

psql -X --single-transaction --set ON_ERROR_STOP=on \
  --dbname="$target_db" --file="$sql_file"

# The Phish.in dump lacks the API's local metadata cache and deferred payload columns.
psql -X --set ON_ERROR_STOP=on --dbname="$target_db" <<'SQL'
ALTER TABLE public.tracks ADD COLUMN IF NOT EXISTS metadata_cache json;
ALTER TABLE public.tracks ALTER COLUMN metadata_cache TYPE json USING metadata_cache::json;
ALTER TABLE public.tracks ADD COLUMN IF NOT EXISTS audio_file_data text;
ALTER TABLE public.tracks ADD COLUMN IF NOT EXISTS waveform_png_data text;
SQL

# Build date/era-specific song pools and placement probabilities from this snapshot.
psql -X --set ON_ERROR_STOP=on --dbname="$target_db" \
  --file="$(dirname "$0")/precompute_generation_song_pools.sql"

psql -X --set ON_ERROR_STOP=on --dbname="$target_db" \
  --command="SELECT COUNT(*) AS show_count, MIN(date) AS first_show, MAX(date) AS latest_show FROM public.shows" \
  --command="SELECT COUNT(*) AS prepared_song_pool_rows, COUNT(DISTINCT (snapshot_date, era)) AS snapshots FROM public.generation_song_pool_snapshots" \
  --command="SELECT COUNT(*) AS shows_2025_2026 FROM public.shows WHERE date >= DATE '2025-01-01' AND date < DATE '2027-01-01'"

refresh_complete=1
echo "Refreshed database: $target_db"
echo "Existing databases were left unchanged. Set DB_NAME=$target_db after reviewing the counts above."
