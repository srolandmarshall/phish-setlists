# Staging Environment Guide

This document captures the current staging workflow so we can exercise
changes end‑to‑end before touching production.

## 1. Database (Fly Postgres)

1. Create/ensure a staging cluster:
   ```bash
   fly pg create --name phish-setlist-staging-db --region iad
   ```
2. Dump the local database and restore it into staging when you need a fresh copy.

   **Dump**
   ```bash
   pg_dump --dbname=postgresql://phish:ph1sh@127.0.0.1:5432/phish-setlist-maker \
           --format=custom \
           --file=data/local_to_staging.dump
   ```

   **Restore (fastest via proxy + pg_restore)**
   ```bash
   fly pg proxy 5433 -a phish-setlist-staging-db &
   PROXY_PID=$!

   PGPASSWORD=<staging-db-password> pg_restore \
     --clean --no-owner \
     --dbname="postgres://postgres:<staging-db-password>@localhost:5433/phish_setlist_maker" \
     data/local_to_staging.dump

   kill $PROXY_PID
   ```
3. Grab the resulting `DATABASE_URL` (via `fly pg connect ... -c '\conninfo'`) and
   store it as a Fly secret for the staging API app.

## 2. API deployment

* Branching: `main` → production, `staging` → staging.
* Create the staging Fly app once:
  ```bash
  fly apps create phish-setlist-staging
  ```
* Config files:
  * `fly.toml` – production (`app = "phish-setlist-maker"`).
  * `fly.staging.toml` – staging (`app = "phish-setlist-staging"`).
* Secrets:
  ```bash
   fly secrets set DATABASE_URL="postgres://postgres:<staging-db-password>@phish-setlist-staging-db.internal:5432/phish_setlist_maker" \
     -a phish-setlist-staging
  ```
* GitHub Actions:
  * `.github/workflows/fly-deploy.yml` runs on `main` pushes (prod).
  * `.github/workflows/fly-deploy-staging.yml` runs on `staging` pushes and deploys
    with `fly.staging.toml`.

## 3. Frontend (separate repo)

* Mirror the branching model (`staging` branch).
* Provide staging env vars (e.g., `VITE_API_URL=https://phish-setlist-staging.fly.dev`).
* Create a second Fly/Netlify/Vercel app (e.g., `phish-frontend-staging`) and
  wire a GitHub Actions workflow to deploy it on `staging` pushes.

## 4. Feature files / analytics data

* Regenerate `data/analytics/*.parquet` and `data/analytics/features/*.parquet`
  whenever we refresh staging. Commit them (or publish artifacts) so the staging
  image uses the same feature store as the code under test.

## 5. Verification checklist

1. Hit `/generate` via the staging frontend with the combinations we care about
   (playlist on/off, `same_show_segues` toggled, etc.).
2. Tail staging logs: `fly logs -a phish-setlist-staging --no-tail`.
3. Confirm segues, lottery tickets, and duration caps behave as expected.
4. When ready, merge `staging` → `main` to trigger the production deploy.

That’s it—staging now mirrors prod closely without risking downtime while we test
feature-file updates, logging tweaks, or new generator heuristics.
