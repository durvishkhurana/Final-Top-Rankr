# Getting started: run and test TopRanker on your laptop

This guide takes you from nothing to a running copy of TopRanker with demo data on
every page, then through testing it. It takes about 30 minutes, most of it waiting.
Putting it on a server is covered at the end.

## 1. Install

| What | Windows / macOS | Linux |
|---|---|---|
| Git | <https://git-scm.com/downloads> (on Windows this also installs **Git Bash**) | your package manager |
| Docker | **Docker Desktop**: <https://www.docker.com/products/docker-desktop/>, then start it | Docker Engine and the Compose plugin: <https://docs.docker.com/engine/install/> |

You need about 8 GB of memory and 10 GB of free disk. On Windows, run every command
below in **Git Bash** (or a WSL terminal), not in PowerShell or cmd. Docker Desktop must
be running before you start.

## 2. Get the code and the settings file

```bash
git clone https://github.com/durvishkhurana/Final-Top-Rankr.git topranker
cd topranker
cp .env.example .env
```

Open `.env` in any editor and change these lines:

| Setting | What to put |
|---|---|
| `JWT_SECRET` | Any random text of at least 32 characters |
| `POSTGRES_PASSWORD` | Any password, and the **same** password in place of `change-me` inside `DATABASE_URL` |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Optional: your own admin account. The demo data also has one (step 4) |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | Optional: free keys from <https://console.groq.com/keys> and <https://aistudio.google.com/apikey>. Without them everything works except the AI buttons |

Optional: if a teammate gives you `f_ref.json`, put it in a folder called `data/` in
the project. Scores on the problems without a known optimum are then measured against
the reference values; without it, against the best value found so far.

## 3. Build, start and fill with demo data

```bash
sh scripts/setup.sh
```

This builds the sandbox and the app, starts everything in Docker, then judges the
baseline algorithms on every problem and creates the demo data. The first run takes
15 to 30 minutes. At the end it prints the logins: **copy the demo password**, it is
shown only once.

## 4. Open it

Go to <http://localhost:3000>. The API documentation is at <http://localhost:8000/docs>.

All demo accounts use the password printed in step 3.

| Account | Email | Role |
|---|---|---|
| Admin | `admin@example.org` | Admin pages, approving contributed problems, AI challenger |
| Instructor | `instructor@example.org` | Owns both demo courses, the contests and the tests |
| Students | `demo1@example.org` to `demo8@example.org` | Submissions, contest entries, test attempts |

## 5. What the demo data contains

| Page | What to look at |
|---|---|
| Problems | 25 problems; each has a leaderboard with the three baselines and demo students |
| A submission | Score, convergence chart, run table and downloads. D2 problems show an animated replay; RW problems show the best timetable, facility placement or routes |
| Leaderboard | People, countries, institutions and problem setters |
| Statistics, profiles | Platform totals; a profile has an activity heatmap |
| Research | Compare entries on STD-001, dimension 5; downloads in CSV, JSON, LaTeX and IOHanalyzer format |
| Contests | **Weekly Challenge** (running, five entrants), **Course Sprint** (closed, with a final ranking on held-out instances), **Invitational** (starts in three days, invite only) |
| Courses (as instructor) | **Optimization Algorithms** (six students) and **Metaheuristics Lab** (four), each with an invite code and a progress dashboard. The code-similarity panel for STD-001, dimension 5, shows one pair of students with near-identical code |
| Tests (as instructor) | **Quiz 1**: closed and graded, with five attempts, one reasoning answer still to grade by hand, integrity events and a grade audit log. **Quiz 2**: open now, so a student can take it. **Lab test**: a draft to edit |
| Tests (as a student) | `demo1` sees the graded Quiz 1 and can take Quiz 2 |
| Contribute (as a student) | `demo4` has an approved problem (now in the catalogue, with entries), `demo7` one waiting for review, `demo8` one that failed its automatic check |
| Admin (as admin) | Users and roles, problem visibility, baselines, the contribution waiting for review, starting an AI challenger |

The AI features (algorithm analysis, run coach, write-up, distractors, viva questions,
the problem builder and the AI challenger) need a key from step 2 and are tried live.

## 6. Test checklist

Work through these and note anything that does not behave as described.

**Signed out**
- [ ] Home, Problems, a problem page, Leaderboard (all four tabs), Statistics, Research and Contests open without errors
- [ ] Courses, Tests and Contribute send you to sign in

**Account**
- [ ] Create an account; a confirmation link appears in `docker compose logs backend` (no email server locally); opening it confirms the address
- [ ] Forgot password: the reset link appears in the same log and changes the password
- [ ] Five wrong passwords in a row lock sign-in for that email

**Student (`demo1`)**
- [ ] Submit a template on STD-001; it moves from queued to running to done within a minute
- [ ] Open the judged submission: chart, runs, downloads; with an AI key, "What algorithm is this?" and the run coach
- [ ] Submit on a D2 problem and watch the replay; open an RW submission and see the drawing
- [ ] Contests: enter the Weekly Challenge and submit; see the Course Sprint final ranking
- [ ] Tests: see Quiz 1 grades; take Quiz 2 (answer, switch tabs once, hand in)
- [ ] Contribute a simple function, for example `def f(X): return (X ** 2).sum(axis=1)`
- [ ] Edit your profile

**Instructor**
- [ ] Course dashboards and the similarity panel
- [ ] Quiz 1 results: grade the remaining reasoning answer, see the audit log and integrity timeline
- [ ] Create a test with each question kind and publish it; create and finalise a contest

**Admin**
- [ ] Approve or reject the waiting contribution; change a user's role; hide and show a problem
- [ ] Run the baselines on a problem; with an AI key, start an AI challenger and press "Evolve now"

**Research**
- [ ] Compare four entries; download every format; with an AI key, draft the results paragraph

## 7. Automated tests

The README lists the commands; in short:

```bash
cd backend && python -m venv .venv && . .venv/bin/activate   # .venv/Scripts/activate on Windows
pip install -e ".[dev]" && ruff check . ../scripts ../sandbox ../worker && mypy . && pytest
```

```bash
cd frontend && npm ci && npx eslint . && npm run typecheck && npm test
```

The backend tests need the Docker services running (step 3). The sandbox tests run only
where the `docker` command is available; on Windows run them inside the worker:

```bash
docker compose exec worker sh -c 'pip install -q pytest anyio && python -m pytest -q tests/test_sandbox.py'
```

Browser tests (Playwright) are described in the README. They create test accounts in
the database they run against, so point them at a throwaway database.

## 8. Everyday commands

| Command | What it does |
|---|---|
| `docker compose up -d` | Start everything (after a restart of the laptop) |
| `docker compose down` | Stop everything; the data is kept |
| `docker compose logs -f worker` | Watch submissions being judged |
| `docker compose exec -T backend python ../scripts/reset.py` | Remove the demo data |
| `docker compose exec -T backend python ../scripts/seed.py --demo` | Create it again (new password) |
| `git pull && docker compose up -d --build` | Update to the latest code |

**If something goes wrong**
- Page does not load: `docker compose ps` should show every service running; start Docker Desktop and run `docker compose up -d`.
- Submissions stay queued: `docker compose logs worker`. "image not found" means the sandbox is missing: `sh scripts/build_sandbox.sh`.
- `setup.sh` fails with a database password error: the password in `DATABASE_URL` must match `POSTGRES_PASSWORD`. Fix `.env`, then `docker compose down -v` (this deletes the local database) and run setup again.
- "AI features are disabled": add a key to `.env` and run `docker compose up -d`.

## 9. Putting it on a server

[DEPLOYMENT.md](DEPLOYMENT.md) is the full guide. In short:

1. A Linux machine with 4 cores and 8 GB of memory, used only for TopRanker, with Docker.
   Oracle Cloud's Always Free tier (an ARM machine with up to 4 cores and 24 GB) is enough
   and costs nothing; open ports 80 and 443 in its network security list **and** in the
   machine's own firewall (`iptables`).
2. A domain name pointing at the machine; a free subdomain from <https://www.duckdns.org>
   works.
3. On the machine: clone the code, fill `.env` with long random secrets, `DOMAIN=` your
   domain, an admin account, an email server (`SMTP_*`) and the AI keys, then:

   ```bash
   sh scripts/build_sandbox.sh
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --wait
   docker compose exec -T backend python ../scripts/seed.py --baselines
   ```

   Leave out `--demo` on a public server; it creates accounts with one shared password.
4. Open `https://<your domain>`; the certificate is obtained automatically. Then work
   through the checks and the daily backup in DEPLOYMENT.md.

The judge starts a Docker container for every run, so hosts that do not give you a
machine with Docker (for example Vercel or Render's free tier) cannot run the whole app.
