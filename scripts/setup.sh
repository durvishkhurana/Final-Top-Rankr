#!/bin/sh
# One-command local setup: sandbox image, all services, migrations, seed data.
# Needs Docker and a filled-in .env (copy .env.example). Seeding judges about 250
# submissions and takes 10 to 20 minutes the first time.
set -eu
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Create .env from .env.example first."; exit 1; }
sh scripts/build_sandbox.sh
docker compose up -d --build --wait   # the backend applies migrations on start
docker compose exec -T backend python ../scripts/seed.py --baselines --demo
