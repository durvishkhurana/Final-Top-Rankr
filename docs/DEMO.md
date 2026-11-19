# Demo script

A walkthrough of TopRanker in about fifteen minutes, in the order that tells the story
best. It assumes a local install with demo data (`sh scripts/setup.sh`, see
[PROJECT_GUIDE.md](PROJECT_GUIDE.md#9-running-it-on-your-own-computer)). The setup
prints the demo logins once: the admin (your `ADMIN_EMAIL` and `ADMIN_PASSWORD`), the
instructor `instructor@topranker.invalid` and the students `demo1@topranker.invalid`
onwards, all sharing one generated password.

The AI steps need `GROQ_API_KEY` or `GEMINI_API_KEY` in `.env`. Without them the rest of
the demo works and the AI buttons say the features are off.

## 1. The catalogue (signed out, 1 minute)

1. Open <http://localhost:3000> and go to **Problems**. Point out the three groups:
   standard benchmark functions, the 2D picture demos (D2-...) and the real-world
   problems (RW-...: exam timetabling, facility location, vehicle routing).
2. Open **STD-001**. The description, box and budget are public; the exact function
   instance is not. Show the **Leaderboard** tab: baselines (random search, differential
   evolution, CMA-ES) are flagged and ranked alongside people.

## 2. Submitting and judging (student, 4 minutes)

1. Sign in as `demo1@topranker.invalid`.
2. On **STD-001**, pick a dimension, start from a template in the editor and submit.
   Note the quota line (cooldown and daily cap).
3. The submission page follows the judge live: 3 instances x 5 seeds, each run in its
   own locked-down container. When it finishes, show the score (AOCC), the convergence
   chart against the top entries and baselines, and the per-run table with its
   CSV/JSON download.
4. Open a **D2** problem and a judged submission on it to show the animated replay of
   the points the algorithm tried on the landscape.
5. Open an **RW** problem and a judged submission to show the drawing of the best
   timetable, facility placement or routes.
6. With AI on: ask **"What algorithm is this?"** and the **run coach**. Point out that
   the model only sees the code and relative precisions, never the hidden function.

## 3. Leaderboards and research (2 minutes)

1. **Leaderboard**: global rating by person, country and institution, and the
   problem setters. **Statistics**:
   platform totals. Click a name to open a profile with its activity heatmap.
2. **Research**: choose STD-001 and a dimension, keep the default selection (top three
   people and the baselines) and press **Compare**. Walk through the mean AOCC with
   confidence intervals, mean ranks and the Friedman test, the pairwise Mann-Whitney
   tests with Holm's correction and A12, and the ECDF chart.
3. Show the downloads: all runs as CSV/JSON, the **LaTeX** table and the
   **IOHanalyzer** zip. With AI on and signed in, press **Draft a results paragraph**:
   the text names the winners and the inconclusive pairs without a single number, which
   all stay in the tables.

## 4. Teaching (instructor, 4 minutes)

1. Sign in as `instructor@topranker.invalid`.
2. **Courses**: create a course and copy its invite code. In a second browser window,
   sign in as a student and join with the code. The instructor dashboard lists every
   student's progress.
3. **Contests**: create a contest (open, invite-only or for the course) with a problem
   or two. While it runs the board uses public instances; closing it re-runs everyone's
   best entry on held-out instances for the final ranking.
4. **Tests**: build a course test with a multiple-choice, a personalised numeric and a
   reasoning question about the student's own runs. Take it as the student, then grade
   it as the instructor: AI-suggested grades against the rubric, the override and the
   audit log, the viva questions and the code-similarity panel. Integrity signals are
   shown only as a timeline; nothing fails a student automatically.

## 5. Platform and AI challenger (admin, 3 minutes)

1. Sign in as the admin and open **Admin**: roles, problem visibility, running the
   baselines.
2. **Contribute** (any signed-in user): describe a fitness function in a sentence, let
   the AI draft it, and submit. The draft is smoke-tested in a sandbox and waits for the
   admin's approval.
3. Back on **Admin**, start an **AI challenger** on a problem and press **Evolve now**.
   Each generation is written from the champion so far and judged like any submission.
   The problem page lists every generation with its score, its approach, what changed
   and which generation it came from.

## If something goes wrong

- Nothing gets judged: `docker compose logs -f worker`, and check the sandbox image
  exists (`sh scripts/build_sandbox.sh`).
- AI buttons answer "limit reached": the per-user and global daily limits
  (`AI_DAILY_LIMIT_PER_USER`, `AI_DAILY_LIMIT_GLOBAL`, `GEMINI_DAILY_LIMIT`) reset at
  midnight UTC.
- To start over: `docker compose exec backend python ../scripts/reset.py`, then
  `sh scripts/setup.sh` again.
