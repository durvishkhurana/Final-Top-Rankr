"""Trace checkpoints and AOCC scoring. See docs/JUDGE.md for the formulas."""

from collections.abc import Sequence

import numpy as np

from .functions import Array

P_MIN, P_MAX = 1e-8, 1e2
N_CHECKPOINTS = 64


def default_budget(dim: int) -> int:
    return 2000 * dim


def checkpoints(budget: int) -> list[int]:
    """Log-spaced evaluation counts from 1 to budget, strictly increasing."""
    pts = np.unique(np.round(np.logspace(0, np.log10(budget), N_CHECKPOINTS)).astype(int))
    return [int(p) for p in pts]


def precision(f_best: float, f_ref: float) -> float:
    return max(f_best - f_ref, P_MIN)


def aocc(trace: Sequence[float] | Array, f_ref: float, points: Sequence[int] | None = None
         ) -> float:
    """Area over the convergence curve in [0, 1]; higher is better.

    trace is best-so-far at each checkpoint in points (evaluation counts; default
    1, 2, 3, ...). The curve is how far log10(precision) has dropped from P_MAX
    towards P_MIN, averaged over the evaluation axis: the value at a checkpoint
    holds until the next one.
    """
    if len(trace) == 0:
        return 0.0
    weights = np.diff(points, append=points[-1] + 1) if points is not None else None
    p = np.clip(np.asarray(trace, dtype=float) - f_ref, P_MIN, P_MAX)
    p = np.nan_to_num(p, nan=P_MAX)
    span = np.log10(P_MAX) - np.log10(P_MIN)
    return float(np.average((np.log10(P_MAX) - np.log10(p)) / span, weights=weights))


def aggregate(per_instance: Sequence[Sequence[float]]) -> dict[str, float]:
    """per_instance[i][s] = AOCC of seed s on instance i.

    Median across seeds, then mean across instances. IQR across seeds is the
    robustness measure, averaged over instances.
    """
    medians = [float(np.median(seeds)) for seeds in per_instance]
    iqrs = [float(np.subtract(*np.percentile(seeds, [75, 25]))) for seeds in per_instance]
    agg = float(np.mean(medians))
    return {"aocc": agg, "score": float(round(1000 * agg)), "iqr": float(np.mean(iqrs))}


def best_so_far_at(values: Array, start_best: float, start_evals: int, points: Sequence[int]
                   ) -> list[float]:
    """Best-so-far at the checkpoints falling inside one batch of evaluations.

    values are the batch results for evaluations start_evals+1 .. start_evals+len(values).
    """
    running = np.minimum.accumulate(np.minimum(values, start_best))
    return [float(running[p - start_evals - 1])
            for p in points if start_evals < p <= start_evals + len(values)]
