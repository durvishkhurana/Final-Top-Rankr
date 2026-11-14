"""Judges one submission on one problem: instances x seeds runs, then the score."""

import math
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from .functions import Problem
from .instance import make_instance
from .runner import Limits, RunResult, run
from .scoring import aggregate, aocc, checkpoints, default_budget, precision

PUBLIC_INSTANCE_SEEDS = (1, 2, 3)
RUN_SEEDS = (1, 2, 3, 4, 5)


def _finite(value: float) -> float | None:
    return value if math.isfinite(value) else None  # JSON has no inf


def score_runs(runs: list[dict[str, Any]], refs: Mapping[int, float], budget: int
               ) -> dict[str, Any]:
    """Sets aocc and precision on every run from its stored trace and returns the
    submission summary. Used for fresh results and to re-score when f_ref improves."""
    points = checkpoints(budget)
    for r in runs:
        ok = r["status"] == "ok"  # failed runs score zero
        ref = refs[r["instance_seed"]]
        trace = [math.inf if v is None else v for v in r["trace"]]
        r["aocc"] = aocc(trace, ref, points) if ok else 0.0
        r["precision"] = precision(r["f_best"], ref) if ok and r["f_best"] is not None else None
    seeds = sorted({r["instance_seed"] for r in runs})
    summary = aggregate([[r["aocc"] for r in runs if r["instance_seed"] == i] for i in seeds])
    precisions = [r["precision"] for r in runs if r["precision"] is not None]
    return {**summary,
            "median_precision": float(np.median(precisions)) if precisions else None}


def judge(
    code: str,
    problem: Problem,
    dim: int,
    instance_seeds: Sequence[int] = PUBLIC_INSTANCE_SEEDS,
    run_seeds: Sequence[int] = RUN_SEEDS,
    budget: int | None = None,
    f_ref: Mapping[int, float] | None = None,
    limits: Limits | None = None,
    sandbox: bool = True,
    workers: int = 4,
) -> dict[str, Any]:
    """f_ref maps instance seed -> best-known value, for problems without a known
    optimum. If it is missing the best value of these runs is used and the result
    is marked provisional."""
    budget = budget or default_budget(dim)
    instances = {s: make_instance(problem, dim, s) for s in instance_seeds}
    jobs = [(i, s) for i in instance_seeds for s in run_seeds]

    def one(job: tuple[int, int]) -> RunResult:
        inst = instances[job[0]]
        return run(code, inst, dim, inst.lower, inst.upper, budget, job[1], limits, sandbox)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = dict(zip(jobs, pool.map(one, jobs), strict=True))

    provisional = False
    refs: dict[int, float] = {}
    for i, inst in instances.items():
        if inst.f_opt is not None:
            refs[i] = inst.f_opt
        elif f_ref is not None and i in f_ref:
            refs[i] = f_ref[i]
        else:
            provisional = True
            refs[i] = min(results[i, s].f_best for s in run_seeds)

    runs: list[dict[str, Any]] = [
        {"instance_seed": i, "seed": s, "status": r.status, "error": r.error,
         "evals": r.evals, "f_best": _finite(r.f_best), "wall_sec": r.wall_sec,
         "trace": [_finite(v) for v in r.trace], "log": r.log}
        for (i, s), r in results.items()
    ]  # fmt: skip
    return {**score_runs(runs, refs, budget), "budget": budget,
            "f_ref_provisional": provisional, "runs": runs}
