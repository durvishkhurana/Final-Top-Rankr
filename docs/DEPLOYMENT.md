# Deployment

How to run TopRanker on a server for real users. The local setup in the README is the
same stack; production adds HTTPS, production settings, backups and a few checks.

## What you need

- A Linux virtual machine with Docker Engine and the Compose plugin. 4 CPU cores and
  8 GB of memory are enough for a class of about a hundred students; each judging job
  runs up to four sandbox containers with one CPU and 512 MB each, and the worker runs
  two jobs at a time.
- A domain name whose DNS `A` (and `AAAA`) record points at the machine.
- Ports 80 and 443 open to the internet. Nothing else needs to be reachable: Postgres,
  Redis, the API and the frontend listen on `127.0.0.1` only.
- Optional: an SMTP account for email (confirmation and password-reset links), and
  Groq or Gemini API keys for the AI features.

Use a machine dedicated to TopRanker. The worker controls the host's Docker daemon to
start sandbox containers, which is equivalent to root on that host (see `SECURITY.md`).

## First installation

```bash
git clone <repository-url> topranker && cd topranker
cp .env.example .env
```

Edit `.env`:

| Setting | Value |
|---|---|
| `JWT_SECRET`, `POSTGRES_PASSWORD`, `HELDOUT_SECRET` | Long random values, each different: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL` | Keep the form of the example; its password must match `POSTGRES_PASSWORD`. Compose rewrites the host to the `postgres` service. |
| `DOMAIN` | Add this line: the public host name, for example `DOMAIN=topranker.example.edu` |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | The first admin account |
| `SMTP_*` | Your mail server. Without it, emails are written to the backend log (`docker compose logs backend`) and an admin has to pass links on by hand. |
| `REQUIRE_VERIFIED_EMAIL` | `true` once SMTP works, so only confirmed addresses can submit |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | Optional, for the AI features |

`APP_ENV=production` (secure cookies) and `FRONTEND_URL=https://<DOMAIN>` are set by
`docker-compose.prod.yml`, so you do not need to change them in `.env`.

Then build the sandbox image, start everything and seed the catalogue:

```bash
sh scripts/build_sandbox.sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --wait
docker compose exec -T backend python ../scripts/seed.py --baselines
```

`--baselines` judges random search, differential evolution and CMA-ES on every problem
(10 to 20 minutes). Leave out `--demo` in production: it creates demo users.

Open `https://<DOMAIN>`. Caddy obtains a Let's Encrypt certificate on the first request,
which takes a few seconds. Sign in with the admin account.

To save typing, put the two file names in `.env`:

```bash
echo 'COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml' >> .env
```

Every `docker compose` command below assumes this.

## What runs

| Service | Role | Port |
|---|---|---|
| `caddy` | HTTPS, compression, security headers; forwards everything to the frontend | 80, 443 (public) |
| `frontend` | Next.js; forwards `/api/*` to the backend | 127.0.0.1:3000 |
| `backend` | FastAPI; applies database migrations when it starts | 127.0.0.1:8000 |
| `worker` | Judges submissions, finalises contests, grades tests, evolves AI challengers, daily clean-up | none |
| `postgres` | Database, in the `pgdata` volume | 127.0.0.1:5432 |
| `redis` | Job queue | 127.0.0.1:6379 |

The worker's daily jobs run at 03:00 UTC (deleting old integrity signals, expired
sessions and account events) and 04:00 UTC (one generation of every active AI
challenger).

## Updating

```bash
git pull
sh scripts/build_sandbox.sh            # only if sandbox/ changed
docker compose up -d --build --wait    # migrations run when the backend starts
docker compose exec -T backend python ../scripts/seed.py   # picks up catalogue changes
```

## Backups

Everything worth keeping is in Postgres. Back it up daily, for example from cron:

```bash
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' \
    > "backup-$(date +%F).dump"
```

Restore into an empty database:

```bash
docker compose stop backend worker
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
    < backup-2026-11-17.dump
docker compose start backend worker
```

Keep copies off the machine. The `data/` folder holds only reference values produced by
`scripts/compute_f_ref.py`, which can be produced again.

## Checks after installing

- `docker compose ps` shows every service as running (healthy for postgres, redis and
  backend).
- `curl -fsS https://<DOMAIN>/api/health` returns `{"status":"ok"}`.
- Sign up with a real address: the confirmation email arrives (or appears in
  `docker compose logs backend` without SMTP).
- Submit the random-search template on a problem: it is judged within a minute.
  `docker compose logs worker` shows the job; a failed judging with a platform error
  usually means the worker cannot reach the Docker daemon or the sandbox image is
  missing.
- The browser cookies of the site are marked `Secure` and `HttpOnly`.

## Limiting sign-in attempts per IP address

The API locks an account after repeated wrong passwords, counted per email address
(`LOGIN_MAX_FAILURES`, `LOGIN_WINDOW_MIN`). Guessing across many accounts from one
address is better stopped in front of the application. Caddy has no rate limiter
built in; either use a Caddy build with the `rate_limit` module, put the site behind a
service that offers it, or use fail2ban on the access log. With nginx instead of Caddy:

```nginx
limit_req_zone $binary_remote_addr zone=signin:10m rate=10r/m;

location = /api/auth/login {
    limit_req zone=signin burst=5 nodelay;
    proxy_pass http://127.0.0.1:3000;
}
```

## Stronger isolation with gVisor

Sandbox containers share the host kernel. To run them under gVisor, which intercepts
system calls in user space, install `runsc` on the host as described in the gVisor
documentation (<https://gvisor.dev/docs/user_guide/install/>), register it with Docker
(`sudo runsc install && sudo systemctl reload docker`) and set `SANDBOX_RUNTIME=runsc`
in `.env`. The runner passes it to `docker run --runtime`. This path is supported by the
code but has not been tested in this project. Before relying on it, restart the worker
and run the hostile-code checks through it:

```bash
docker compose up -d worker
docker compose exec worker sh -c 'pip install -q pytest && pytest tests/test_sandbox.py'
docker compose exec worker python ../scripts/run_local.py --baseline cmaes --problem STD-001
```

## Scaling

- More judging: raise `max_jobs` in `worker/main.py` or start more worker containers
  on hosts with Docker; they all take jobs from the same Redis queue.
- Leaderboards and ratings are computed on each request, which is fine for thousands of
  submissions; see the note in `backend/api/ratings.py` if they become slow.
- Language-model costs are bounded by `AI_DAILY_LIMIT_PER_USER`,
  `AI_DAILY_LIMIT_GLOBAL` and `GEMINI_DAILY_LIMIT`; every call is logged in `llm_calls`.
