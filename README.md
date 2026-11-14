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

Early development. What exists today: repository skeleton, local Postgres and Redis via
Docker Compose, and a CI workflow for the backend. Nothing else described above is built yet.

## Local services

Requires Docker Desktop (WSL2 backend on Windows).

```bash
cp .env.example .env   # then replace the change-me values
docker compose up -d
```

## Roadmap

- Judge core: sandboxed runs, instance transformations, budget enforcement, AOCC scoring, baselines
- Web platform: accounts, problems, code submission, leaderboards
- Convergence charts, 2D landscape animation, real-world problem packs
- Contests and courses
- AI baseline, algorithm analysis, run coach, problem builder
- Instructor tests and integrity signals
- Research statistics and exports

## License

Not yet chosen.
