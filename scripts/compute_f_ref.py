"""Compute best-known values (f_ref) for problems without a known optimum.

Runs CMA-ES with restarts and SciPy differential evolution in-process (trusted code,
no sandbox) with a large budget and keeps the best value per (problem, dim, instance).
Results are merged into data/f_ref.json; an existing better value is never replaced.

    python scripts/compute_f_ref.py --dims 5 10 20 --instances 1 2 3
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from judge.baselines import cmaes, differential_evolution  # noqa: E402
from judge.functions import PROBLEMS  # noqa: E402
from judge.instance import Instance, make_instance  # noqa: E402

OUT = ROOT / "data" / "f_ref.json"


class _Done(Exception):
    pass


def best_value(inst: Instance, optimize, budget: int, seed: int) -> float:
    best, used = np.inf, 0

    def f(X):
        nonlocal best, used
        asked = np.clip(np.atleast_2d(X), inst.lower, inst.upper)
        P = asked[: budget - used]
        if len(P):
            values = inst(P)
            used += len(P)
            best = min(best, float(np.nanmin(values)))
        if len(P) < len(asked):
            raise _Done
        return float(values[0]) if np.ndim(X) == 1 else values

    try:
        optimize(f, inst.dim, inst.lower, inst.upper, budget, np.random.default_rng(seed))
    except _Done:
        pass
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--problems", nargs="+",
                    default=[p for p, v in PROBLEMS.items() if v.z_opt is None])
    ap.add_argument("--dims", type=int, nargs="+", default=[5, 10, 20])
    ap.add_argument("--instances", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--budget-per-dim", type=int, default=20000)
    ap.add_argument("--repeats", type=int, default=2)
    args = ap.parse_args()

    store = json.loads(OUT.read_text()) if OUT.exists() else {}
    for pid in args.problems:
        for dim in args.dims:
            for iseed in args.instances:
                inst = make_instance(PROBLEMS[pid], dim, iseed)
                found = min(
                    best_value(inst, algo.optimize, args.budget_per_dim * dim, rep)
                    for algo in (cmaes, differential_evolution)
                    for rep in range(args.repeats)
                )
                slot = store.setdefault(pid, {}).setdefault(str(dim), {})
                slot[str(iseed)] = min(found, slot.get(str(iseed), np.inf))
                print(f"{pid} dim={dim} instance={iseed}: {slot[str(iseed)]:.10g}", flush=True)
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(store, indent=1))


if __name__ == "__main__":
    main()
