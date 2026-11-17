#!/bin/sh
# Browser tests against a production build of the whole stack: migrates and seeds the
# database in DATABASE_URL (use a throwaway one), starts the API, the worker and the
# frontend, runs Playwright, then stops them. Arguments are passed to Playwright.
#
# Needs: Postgres and Redis running (docker compose up -d postgres redis), the sandbox
# image (scripts/build_sandbox.sh), the backend installed (pip install -e "backend[dev]"),
# the frontend dependencies (npm ci) and a Chromium for Playwright
# (npx playwright install chromium). Set ADMIN_EMAIL and ADMIN_PASSWORD to include the
# admin tests.
set -eu
cd "$(dirname "$0")/.."
LOGS=${E2E_LOGS:-/tmp/topranker-e2e}
mkdir -p "$LOGS"
export E2E_API_LOG="$LOGS/api.log" SMTP_HOST="" E2E_ADMIN_EMAIL="${ADMIN_EMAIL:-}" \
    E2E_ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"

(cd backend && alembic upgrade head && python ../scripts/seed.py) >"$LOGS/seed.log" 2>&1
(cd frontend && node_modules/.bin/next build) >"$LOGS/build.log" 2>&1

(cd backend && exec uvicorn api.main:app --port 8000) >"$E2E_API_LOG" 2>&1 &
api=$!
(cd backend && PYTHONPATH=..:. exec arq worker.main.WorkerSettings) >"$LOGS/worker.log" 2>&1 &
worker=$!
(cd frontend && exec node_modules/.bin/next start --port 3000) >"$LOGS/web.log" 2>&1 &
web=$!
trap 'kill $api $worker $web 2>/dev/null' EXIT

for _ in $(seq 60); do
    curl -sf http://localhost:3000/api/health >/dev/null && break
    sleep 2
done
cd frontend && node_modules/.bin/playwright test "$@"
