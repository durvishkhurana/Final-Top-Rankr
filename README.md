# TopRanker

TopRanker is an online judge for optimization algorithms. Users submit an optimizer
(a Python function), not an answer. The platform runs it in a sandbox against hidden
black-box fitness functions under a fixed evaluation budget, over multiple seeds and
hidden problem instances, and ranks algorithms by server-side results.

- Kaggle compares models on datasets; TopRanker compares optimization algorithms on
  hidden functions under identical budgets.
- Research benchmarking tools (COCO/BBOB, IOHprofiler) are run locally and results are
  self-reported; TopRanker runs every submission on the server under identical conditions.
- The format follows the NeurIPS 2020 Black-Box Optimization Challenge, turned into a
  permanent platform for classrooms and research groups.

## Status

Early development. What exists today:

- The judge core, usable from the command line: 18 built-in problems (TR-001 to TR-010
  and a standard set of 8) with seeded shift and rotation instances, sandboxed execution
  of submitted optimizers, budget enforcement, convergence traces, AOCC scoring, and
  three baselines (random search, differential evolution, CMA-ES). See
  [docs/JUDGE.md](docs/JUDGE.md) and [docs/SECURITY.md](docs/SECURITY.md).
- Local Postgres and Redis via Docker Compose (not used by the judge yet).
- CI running lint, type checks and tests, including the sandbox isolation tests.

There is no web application, API, database schema or job queue yet.

## Try the judge

Requires Docker and Python 3.12 with NumPy and SciPy.

```bash
sh scripts/build_sandbox.sh
python scripts/run_local.py --baseline cmaes --problem STD-001 --dim 10
python scripts/run_local.py my_optimizer.py --problem TR-003 --dim 5
```

## Tests

```bash
cd backend
pip install -e ".[dev]"
ruff check . && mypy . && pytest
```

## Local services

Requires Docker Desktop (WSL2 backend on Windows).

```bash
cp .env.example .env   # then replace the change-me values
docker compose up -d
```

## Roadmap

- Job queue worker and stored results
- Held-out instances for final rankings
- Web platform: accounts, problems, code submission, leaderboards
- Convergence charts, 2D landscape animation, real-world problem packs
- Contests and courses
- AI baseline, algorithm analysis, run coach, problem builder
- Instructor tests and integrity signals
- Research statistics and exports

## License

Not yet chosen.
