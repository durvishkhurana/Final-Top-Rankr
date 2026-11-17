# TopRanker, explained simply

This guide explains the whole project in plain English: what it is for, how it works,
what each part of the code does and how to run it. You do not need to know the code to
read it. The other files in `docs/` go deeper into each topic; links are given where
they help.

---

## 1. The idea in one paragraph

Many problems in science and engineering come down to "find the best setting": the
cheapest route, the strongest design, the lowest error. An **optimization algorithm**
is a method for searching for that best setting. There are hundreds of them (random
search, evolution strategies, differential evolution, CMA-ES and many more), and it is
hard to know which one is really better, because people usually test their own method
on their own computer and report their own numbers.

**TopRanker is an online judge for optimization algorithms.** You do not send an
answer; you send your algorithm, as a short Python function. The server runs it on
hidden test problems, with the same number of tries for everybody, several times with
different random seeds, and gives it a score. Everyone is measured the same way, on the
server, so the leaderboards can be trusted.

Think of it like a coding-contest site (Codeforces, LeetCode) or Kaggle, but for search
algorithms instead of programs or models.

---

## 2. Words you will see

| Word | Meaning |
|---|---|
| **Problem** | A hidden mathematical function to minimise, for example "Rosenbrock" or "Spiral Sink". You see its description, its search box and its dimensions, never its formula. |
| **Dimension** | How many numbers the algorithm has to choose at once (5, 10 or 20, or 2 for the picture demos). |
| **Search box** | The range each number must stay in, for example −5 to 5. |
| **Budget** | How many times your algorithm may try a point: 2000 × dimension. When it is used up, the run stops. |
| **Instance** | A shifted and rotated copy of a problem, so the best point is somewhere new each time and nobody can memorise it. |
| **Run** | One go of your algorithm on one instance with one random seed. Every submission gets 15 runs (3 instances × 5 seeds). |
| **Precision** | How far the best value you found is from the best value known. Smaller is better; 1e-8 (0.00000001) is the floor. |
| **AOCC** | "Area over the convergence curve": a number from 0 to 1 that rewards both getting close and getting close early. |
| **Score** | 1000 × AOCC, averaged over instances. This is the number on the leaderboards. |
| **Baseline** | A well-known algorithm the platform runs itself (random search, differential evolution, CMA-ES), so you have something to beat. |
| **Sandbox** | A locked-down container your code runs in: no internet, no disk, limited memory and time. |

---

## 3. What a user can do

### Everyone (no account needed)
- Browse the **problem catalogue**: 25 built-in problems. Ten are originals (TR-001 to
  TR-010), eight are classic test functions (STD-001 to STD-008), four are two-variable
  picture demos (D2-001 to D2-004) and three are real-world puzzles (exam timetabling,
  bus-stop placement and delivery routing).
- See **leaderboards** per problem, a **global leaderboard** (by person, country or
  institution), a **statistics** page and public **profiles**.
- Open any judged submission and see its score, its **convergence chart** (how fast it
  improved) and every run. The code itself stays private.
- Use the **research page** to compare entries with proper statistics, and **download**
  runs and leaderboards as CSV or JSON.

### Students (signed in)
- **Submit** an optimizer from the in-browser code editor, starting from a template.
- Watch it being judged live, then study the results: convergence chart compared with
  the top entries and baselines, an animated replay on the 2D demo problems, or a
  drawing of the best timetable, stop placement or routes on the real-world problems.
- Ask the optional **AI helpers**: "what algorithm is this really?" and a **run coach**
  that explains what went wrong and suggests one change.
- Join **contests** and **courses**, and take **course tests**.
- **Contribute** a new problem (a fitness function), written by hand or drafted by AI
  from a sentence or a photo of a formula.
- Confirm their email address and reset a forgotten password.

### Instructors
- Create **courses** with invite codes, and see a dashboard of every student's progress.
- Create **contests**: open, invite-only or for one course. While a contest runs, the
  public board uses the public instances. When the organiser closes it, everyone's best
  entry is re-run on **secret held-out instances** and that becomes the final ranking,
  so overfitting to the public instances does not pay.
- Build **course tests** with multiple-choice questions, personalised numeric questions
  and short reasoning questions about each student's own runs; get AI help to grade them
  against a rubric (with an audit log and the final say); see **viva questions** to ask
  in person and a **code similarity** check within the course.
- Optionally see **integrity signals** during a test (tab switches, copy and paste, and,
  only with the student's consent, on-device face-presence checks). Nothing fails a
  student automatically. See [PRIVACY.md](PRIVACY.md).

### Admins
- Change roles, hide or show problems, run the baselines, approve contributed problems.
- Start an **AI challenger** on a problem (explained in section 7).

---

## 4. How a submission is judged, step by step

1. You write a function with this exact shape:

   ```python
   def optimize(f, dim, lower, upper, budget, rng):
       # call f(points) as often as the budget allows; lower values are better
       ...
   ```

   `f` is the hidden problem. You can give it one point or a whole batch of points at
   once (batches are much faster). `rng` is a random-number generator; using it makes
   your runs repeatable.

2. You press **Submit**. The web page sends your code to the **API** (the server
   program). The API checks your daily quota and the cooldown, saves the submission
   as "queued" and puts a job on the **queue**.

3. The **worker** (a separate background program) picks up the job. For each of the 15
   runs it starts a fresh **sandbox container**, sends your code into it, and stays
   outside as the referee.

4. Inside the sandbox your code calls `f`. But `f` there is only a messenger: it sends
   the points out to the worker, the worker evaluates the hidden function, counts every
   point against the budget, records the best value so far, and sends the values back.
   **The hidden function never enters the sandbox**, so your code cannot read it.

5. When the budget runs out, or your code finishes or crashes, the run ends and the
   container is deleted. Four runs happen at the same time.

6. The worker turns each run's progress into a precision curve and an AOCC, takes the
   median over seeds and the mean over instances, and stores the **score**. Your page,
   which has been checking every second and a half, shows the result.

7. If any run found a better value than the best one known for its instance (for
   problems without a known optimum), the best-known value is updated and **every**
   submission on that problem is re-scored fairly against it.

The details and formulas are in [JUDGE.md](JUDGE.md).

---

## 5. The parts of the system

```
Browser ──> Frontend (Next.js) ──/api──> API (FastAPI) ──> PostgreSQL (data)
                                               │
                                               └──> Redis (job queue) ──> Worker ──> Sandbox containers
```

| Part | What it is | Where |
|---|---|---|
| **Frontend** | The website you see, written in TypeScript with Next.js and React. It also forwards every `/api/...` request to the API, so login cookies stay on one site. | `frontend/` |
| **API** | The server that answers the website: accounts, problems, submissions, boards, contests, courses, tests, AI features, research and admin. Written in Python with FastAPI. | `backend/api/` |
| **Judge** | The hidden functions, how instances are made, how a run is executed, and how scores are computed. | `backend/judge/` |
| **Worker** | A background program that takes jobs from the queue: judging, closing contests, smoke-testing contributed problems, grading tests, evolving AI challengers, and nightly clean-up. | `worker/main.py` |
| **Sandbox** | The tiny container image (Python, NumPy, SciPy and a small harness) that runs submitted code. | `sandbox/` |
| **Database** | PostgreSQL holds users, problems, submissions, runs, contests, courses, tests and logs. | tables in `backend/db/models.py` |
| **Queue** | Redis passes jobs from the API to the worker. | – |

### A short tour of the code

```
backend/
  api/            the web API
    main.py         creates the app and plugs in every group of routes
    deps.py         "who is signed in?", "is this an admin?" helpers
    schemas.py      the shape of every request and response
    export.py       turns a table into a CSV or JSON download
    routes/         one file per area: auth, problems, submissions, board, contests,
                    courses, exams (tests), ai, contribute, research, challengers, admin
  core/           settings (config.py), passwords and tokens (security.py), email (mail.py)
  db/             database tables (models.py), saving results and re-scoring (results.py),
                  base data and bot accounts (seed.py), contributed problems (contributed.py)
  judge/          functions.py (the hidden problems), instance.py (shift and rotate),
                  runner.py (one run in the sandbox), evaluate.py (all 15 runs),
                  scoring.py (AOCC and score), realworld.py (timetabling, bus stops,
                  routing), contributed.py (user problems), baselines/, templates/
  ai/             llm.py (the only place that talks to an AI provider), features.py
                  (answer formats and run statistics), challenger.py, prompts/
  exams/          course tests: numeric questions, personalised facts, grading,
                  code similarity
  research/       stats.py: the statistics behind the research page
  alembic/        database migrations (how the tables change over time)
  tests/          automated tests for all of the above
frontend/
  app/            one folder per page (problems, submissions, research, admin, ...)
  components/     reusable pieces (charts, tables, editor, forms, ...)
  lib/            API client, types, formatting
  e2e/            browser tests that click through the real site
sandbox/          harness.py (runs inside the container), evaluator.py, Dockerfile
worker/           main.py: the background jobs
scripts/          setup, seeding, reset, local judging, reference values, browser tests
deploy/           Caddyfile for HTTPS in production
docs/             all documentation, including this guide
```

---

## 6. Security, in plain words

Running strangers' code on your server is dangerous, so the sandbox is strict:

- **No internet** inside the container, and a **read-only** file system with only a
  tiny scratch folder.
- It runs as a **nobody user** with **no special powers**, a limit on processes (so a
  "fork bomb" cannot explode), a memory limit, one CPU and a time limit.
- What the program prints is captured and cut off at 64 kB.
- **The hidden function is never inside the container.** Only the values for the
  points you send come back.
- The worker treats everything the container says as untrusted; a broken message just
  ends that run.

Accounts are protected too:

- Passwords are stored as **Argon2** hashes, never in plain text.
- Login uses **httpOnly cookies** (JavaScript cannot read them), which are Secure on a
  real server. Refresh tokens work once.
- After **5 wrong passwords** in 15 minutes an account is locked for the rest of that
  window. A **password reset** link (valid for one hour, usable once) unlocks it and
  signs you out everywhere.
- New accounts get an **email confirmation** link. A server can require a confirmed
  email before anyone submits.
- In production the server refuses to start with a weak secret key.

What the AI is never told: hidden seeds, shifts, rotations, reference values or
held-out results. It sees code and relative numbers only. Details: [SECURITY.md](SECURITY.md).

---

## 7. The AI features

All AI features are optional. Without an API key they switch off and the pages say so.
The AI only writes **text and code**; every score and number comes from the judge.

| Feature | What it does |
|---|---|
| **Algorithm analysis** | Reads your code and says which algorithm family it really is and how it mutates, combines, selects and restarts. |
| **Run coach** | Looks at summary numbers from your runs (how fast you improved, when you got stuck) and gives one suggestion. Contest organisers can turn it off or make it give ideas only. |
| **AI baseline** | Writes an optimizer from the public description only, which is judged like anyone's. |
| **Evolving AI challenger** | The AI's own entry that **gets better over time**. Generation 1 is written from the description. Each next generation sees the best version so far, how it did, the earlier attempts and the best human score, and tries to improve. Every generation is judged in the sandbox; the best one is the challenger's leaderboard entry. It evolves once a day, or when an admin presses "Evolve now". |
| **Problem builder** | Turns a description (or a photo of a formula) into a draft problem, which is then safety-tested and reviewed by an admin. |
| **Test helpers** | Wrong-answer suggestions for multiple-choice questions, many phrasings of a reasoning question, a follow-up question, grading against the rubric, viva questions, and a second opinion on suspicious code pairs. |

Limits per user and per day keep costs predictable, and every AI call is logged.
Details: [AI_FEATURES.md](AI_FEATURES.md).

---

## 8. The research page

Because every submission on a problem runs on the **same instances and seeds**, two
optimizers can be compared run by run, the way scientific benchmarking papers do it.
Pick a problem, tick up to eight entries and press Compare. You get:

- **Mean AOCC with a 95% confidence interval**: if two intervals overlap a lot, the
  difference may just be luck.
- **Mean rank** over the shared runs, and the **Friedman test**: "do these entries
  really perform differently?"
- For every pair, the **Mann-Whitney U test** (corrected for testing many pairs with
  **Holm's method**) and the **A12 effect size**: the chance that a run of one beats a
  run of the other. A verdict says which is better, or that there is no significant
  difference.
- A **runtime distribution (ECDF)** chart: how many of 11 precision targets the runs
  have reached after a given number of evaluations.

Everything can be downloaded as CSV or JSON for your own analysis in Excel, R or
Python. Details: [RESEARCH.md](RESEARCH.md).

---

## 9. Running it on your own computer

You need **Docker**. On Windows, use Docker Desktop with WSL2, or Docker inside WSL2
(the README has the commands).

```bash
cp .env.example .env          # then replace every "change-me" with a random value
sh scripts/setup.sh           # builds everything, starts it and fills in demo data
```

The first setup judges about 250 demo submissions and takes 10 to 20 minutes. Then open
<http://localhost:3000>. The demo logins are printed once at the end. The API's own
documentation is at <http://localhost:8000/docs>.

Useful commands:

| Command | What it does |
|---|---|
| `docker compose up -d` / `down` | Start / stop everything |
| `docker compose logs -f worker` | Watch submissions being judged |
| `docker compose exec backend python ../scripts/reset.py` | Remove the demo users |
| `python scripts/run_local.py my_optimizer.py --problem TR-003 --dim 5` | Judge a file from the command line |

---

## 10. Putting it on a real server

[DEPLOYMENT.md](DEPLOYMENT.md) walks through it. In short:

1. Rent a Linux machine (4 CPUs, 8 GB memory is plenty for a class) and point a domain
   name at it.
2. Install Docker, copy the project, fill in `.env` (secrets, `DOMAIN`, admin account,
   and optionally an email server and AI keys).
3. Run
   `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --wait`.
   This adds **Caddy**, which gets a free HTTPS certificate automatically.
4. Seed the catalogue and baselines, sign in as admin, done.
5. Back up the database every day with the `pg_dump` command in the guide.

---

## 11. How the project is tested

| Kind of test | What it checks | How to run |
|---|---|---|
| Backend tests (pytest, over 200) | Scoring maths, every problem function, the judge, the API, contests, tests and grading, AI features with a fake provider, account security, research statistics, the challenger, and the sandbox against hostile code (network, root, fork bomb, memory, infinite loop, output flood) | `cd backend && pytest` |
| Code checks | Style (ruff) and types (mypy strict) for Python; ESLint and TypeScript for the frontend | see README |
| Frontend unit tests (Vitest) | Formatting and integrity-signal helpers | `cd frontend && npm test` |
| Browser tests (Playwright) | A real browser clicks through a production build: sign-up, email confirmation, password reset, account lock, submitting and seeing the judged runs, leaderboard, research comparison, downloads, admin pages, AI challenger | `sh scripts/e2e.sh` |

GitHub Actions runs all of them on every pull request.

---

## 12. Frequently asked questions

**Can my code cheat by reading the function?** No. The function is not in the
container; your code only receives values for points it sends.

**Can I see other people's code?** No. Scores, convergence and runs are public; code,
logs and errors are visible only to the author and admins.

**Why is my score lower than my friend's even though we both reached 1e-8?** AOCC also
rewards speed: reaching a good value earlier gives a larger area.

**Why did my score change without me submitting?** Someone found a better value on a
problem with no known optimum, so the reference moved and every submission was
re-scored fairly.

**What happens if my code crashes?** That run scores 0, and you see the error message.
The other runs still count.

**Does the AI see my test answers or the camera?** The AI sees answers to grade them,
never integrity signals. Camera checks run only on the student's own device and send no
images anywhere.

**Is anything decided automatically against a student?** No. Integrity signals and
similarity results are for the instructor to look at; they never change a grade by
themselves.
