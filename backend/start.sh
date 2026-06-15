#!/usr/bin/env bash
# Render start command: enforce the boot order without an orchestrator.
# Each step must succeed before the next runs (set -e); uvicorn is exec'd
# last, so Render's /health check only starts passing once everything
# upstream (models present, schema migrated) is actually done. If any step
# fails, the deploy is marked unhealthy and the previous instance keeps
# serving traffic.
set -euo pipefail

# 1. Firebase service-account JSON arrives base64-encoded in an env var
#    (Render has no secret-file mounts on the free plan); write it to disk
#    where the backend expects a file path. Optional: without it the API
#    still boots, only FCM pushes fail.
if [ -n "${FIREBASE_CREDENTIALS_JSON:-}" ]; then
  echo "$FIREBASE_CREDENTIALS_JSON" | base64 -d > /tmp/firebase.json
  export AQUASIGNAL_FIREBASE_CREDENTIALS_FILE=/tmp/firebase.json
  echo "start.sh: Firebase credentials written to /tmp/firebase.json"
fi

# 2. Model artifacts: download from Hugging Face Hub when HF_REPO_ID is set
#    (required -- the models are no longer committed to git; see DEPLOY.md §7).
#    Idempotent: skips files already on disk.
python -m models.download

# 3. Database schema: idempotent, brings Supabase to the latest revision.
#    Fails loudly (and aborts the boot) if the database is unreachable.
alembic upgrade head

# 4. Serve. exec replaces the shell so signals (Render restarts/stops)
#    reach uvicorn directly.
exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}"
