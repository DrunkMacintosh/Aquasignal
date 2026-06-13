-- AquaSignal · Supabase one-time setup
-- Run this ONCE in the Supabase dashboard: SQL Editor → New query → paste → Run.
--
-- Only the PostGIS extension is created here. The actual schema (users,
-- districts, grid_cells, risk_scores, alert_subscriptions, alert_events,
-- including all spatial GIST indexes) is owned by Alembic migrations under
-- backend/alembic/versions/ and is applied AUTOMATICALLY every time the API
-- boots on Render (start.sh runs `alembic upgrade head`). Do not create
-- tables by hand — a second source of schema truth guarantees drift.

CREATE EXTENSION IF NOT EXISTS postgis;

-- Sanity check: should return the PostGIS version string.
SELECT postgis_full_version();

-- Note on the free tier: Supabase pauses projects after ~1 week without
-- traffic. The keepalive GitHub Actions workflow (.github/workflows/
-- keepalive.yml) runs `SELECT 1` every 3 days to keep it active.
