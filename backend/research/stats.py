"""Statistics for comparing judged optimizers. Pure functions on per-run values.

Every submission on one problem and dimension is run on the same grid of instances and
seeds, so runs can be paired by (instance, seed). The tests here follow common practice
in benchmarking optimizers (COCO, IOHprofiler):

- Mann-Whitney U on per-run AOCC for each pair, with Holm's correction for the number
  of pairs, and the Vargha-Delaney A12 effect size;
- Friedman's test over the paired runs when three or more optimizers are compared,
  with the mean rank of each;
- a bootstrap confidence interval of the mean AOCC;
- the empirical cumulative distribution (ECDF) of evaluations to reach a set of
  precision targets, as in COCO's runtime plots.
"""

from collections.abc import Sequence
from itertools import combinations
from typing import Any

import numpy as np
from scipy import stats

TARGETS = [10.0**k for k in range(2, -9, -1)]  # 1e2 .. 1e-8
BOOTSTRAP = 2000


def bootstrap_ci(values: Sequence[float], level: float = 0.95, seed: int = 0
                 ) -> tuple[float, float]:
    """Percentile bootstrap interval of the mean. Seeded, so the page is stable."""
    x = np.asarray(values, dtype=float)
    if len(x) < 2:
        return float(x.mean()), float(x.mean())
    means = np.random.default_rng(seed).choice(x, (BOOTSTRAP, len(x))).mean(axis=1)
    tail = (1 - level) / 2 * 100
    low, high = np.percentile(means, [tail, 100 - tail])
    return float(low), float(high)


def a12(a: Sequence[float], b: Sequence[float]) -> float:
    """Probability that a run of a scores higher than a run of b (ties count half)."""
    x, y = np.asarray(a, dtype=float)[:, None], np.asarray(b, dtype=float)[None, :]
    return float(((x > y).sum() + 0.5 * (x == y).sum()) / (x.size * y.size))


def holm(p_values: Sequence[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, in the input order."""
    m = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[i]))
        adjusted[i] = running
    return adjusted.tolist()


def mann_whitney(a: Sequence[float], b: Sequence[float]) -> float:
    if len(set(a) | set(b)) == 1:  # all values equal: no evidence of a difference
        return 1.0
    return float(stats.mannwhitneyu(a, b, alternative="two-sided").pvalue)


def compare(aocc: dict[int, dict[tuple[int, int], float]], alpha: float = 0.05
            ) -> dict[str, Any]:
    """aocc[submission][(instance_seed, seed)] = AOCC of that run (0 for failed runs).

    Returns per-submission summaries, every pair, and the Friedman test over the
    (instance, seed) blocks that all submissions share."""
    ids = list(aocc)
    summary: dict[int, dict[str, Any]] = {}
    for i in ids:
        values = list(aocc[i].values())
        low, high = bootstrap_ci(values)
        summary[i] = {"runs": len(values), "mean": float(np.mean(values)),
                      "median": float(np.median(values)), "ci_low": low, "ci_high": high}

    pairs: list[dict[str, Any]] = []
    for i, j in combinations(ids, 2):
        a, b = list(aocc[i].values()), list(aocc[j].values())
        pairs.append({"a": i, "b": j, "p": mann_whitney(a, b), "a12": a12(a, b)})
    for pair, adjusted in zip(pairs, holm([p["p"] for p in pairs]), strict=True):
        pair["p_holm"] = adjusted
        pair["significant"] = adjusted < alpha
        pair["better"] = (None if not pair["significant"]
                          else pair["a"] if pair["a12"] > 0.5 else pair["b"])

    blocks = sorted(set.intersection(*(set(aocc[i]) for i in ids))) if ids else []
    friedman_p = None
    if blocks:
        table = np.array([[aocc[i][blk] for i in ids] for blk in blocks])
        # rank 1 is best (highest AOCC) within each block
        ranks = stats.rankdata(-table, axis=1)
        for k, i in enumerate(ids):
            summary[i]["mean_rank"] = float(ranks[:, k].mean())
        if len(ids) >= 3 and len(blocks) >= 2 and np.ptp(table) > 0:
            friedman_p = float(stats.friedmanchisquare(*table.T).pvalue)
    return {"summary": summary, "pairs": pairs, "blocks": len(blocks),
            "friedman_p": friedman_p, "alpha": alpha}


def ecdf(traces: Sequence[Sequence[float | None]], targets: Sequence[float] = TARGETS
         ) -> list[float]:
    """traces[r][k] = precision of run r at checkpoint k (None: failed or not yet
    evaluated). Returns, at each checkpoint, the fraction of (run, target) pairs where
    the run has reached the target."""
    if not traces:
        return []
    p = np.array([[np.inf if v is None else v for v in t] for t in traces], dtype=float)
    reached = p[:, :, None] <= np.asarray(targets)[None, None, :]
    return reached.mean(axis=(0, 2)).tolist()
