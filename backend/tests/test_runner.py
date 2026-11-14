"""Protocol, budget and trace tests. These run the harness as a local process
(no isolation); the isolation itself is covered by test_sandbox.py."""

import numpy as np
import pytest

from judge import baselines
from judge.evaluate import judge
from judge.functions import PROBLEMS, Array
from judge.instance import make_instance
from judge.runner import Limits, RunResult, run
from judge.scoring import checkpoints

DIM, BUDGET = 5, 600
INST = make_instance(PROBLEMS["STD-001"], DIM, 1)
RANDOM = baselines.source("random_search")


def go(code: str, budget: int = BUDGET, seed: int = 1, timeout: float = 30) -> RunResult:
    return run(code, INST, DIM, INST.lower, INST.upper, budget, seed,
               Limits(timeout_sec=timeout), sandbox=False)


def test_random_search_uses_full_budget_and_trace_is_verified() -> None:
    r = go(RANDOM)
    assert (r.status, r.evals, r.error) == ("ok", BUDGET, "")
    assert len(r.trace) == len(checkpoints(BUDGET))
    assert all(a >= b for a, b in zip(r.trace, r.trace[1:], strict=False))
    assert r.trace[-1] == r.f_best
    # the worker's record matches an independent replay of the same seeded points
    X = np.random.default_rng(1).uniform(INST.lower, INST.upper, size=(BUDGET, DIM))
    assert r.f_best == pytest.approx(float(np.min(INST(X))))


def test_same_seed_reproduces_and_other_seed_differs() -> None:
    assert go(RANDOM, seed=3).trace == go(RANDOM, seed=3).trace
    assert go(RANDOM, seed=3).trace != go(RANDOM, seed=4).trace


def test_budget_is_enforced_for_single_point_calls() -> None:
    r = go("def optimize(f, dim, lower, upper, budget, rng):\n"
           "    while True:\n"
           "        assert isinstance(f(rng.uniform(lower, upper)), float)\n")
    assert (r.status, r.evals) == ("ok", BUDGET)


def test_oversized_batch_is_cut_at_the_budget() -> None:
    r = go("def optimize(f, dim, lower, upper, budget, rng):\n"
           "    f(rng.uniform(lower, upper, size=(budget * 3, dim)))\n")
    assert (r.status, r.evals) == ("ok", BUDGET)


def test_early_return_keeps_last_best_for_remaining_checkpoints() -> None:
    r = go("def optimize(f, dim, lower, upper, budget, rng):\n"
           "    f(rng.uniform(lower, upper, size=(10, dim)))\n")
    assert (r.status, r.evals) == ("ok", 10)
    assert r.trace[-1] == r.f_best and len(r.trace) == len(checkpoints(BUDGET))


def test_prints_go_to_the_log_and_cannot_corrupt_the_protocol() -> None:
    r = go("import os, sys\n"
           "def optimize(f, dim, lower, upper, budget, rng):\n"
           "    print('hello from user')\n"
           "    os.write(1, b'\\x00\\x00\\x00\\x00raw-bytes')\n"
           "    sys.stderr.write('to stderr')\n"
           "    f(rng.uniform(lower, upper, size=(budget, dim)))\n"
           "    print('x' * 500000)\n")
    assert (r.status, r.evals) == ("ok", BUDGET)
    assert "hello from user" in r.log and "raw-bytes" in r.log and "to stderr" in r.log
    assert len(r.log) <= Limits().log_bytes


def test_user_exception_is_reported_with_traceback() -> None:
    r = go("def optimize(f, dim, lower, upper, budget, rng):\n"
           "    f(lower)\n"
           "    raise RuntimeError('boom')\n")
    assert r.status == "error" and r.evals == 1
    assert "RuntimeError: boom" in r.error and "solution.py" in r.error


@pytest.mark.parametrize("code", [
    "x = 1\n",
    "def optimize(f, dim, lower, upper, budget, rng):\n    f([1.0, 2.0])\n",
    "def optimize(f, dim, lower, upper, budget, rng):\n    raise SystemExit(0)\n",
    "def optimize(:\n",
])  # fmt: skip
def test_bad_submissions_are_errors(code: str) -> None:
    assert go(code).status == "error"


def test_points_are_clipped_and_non_finite_never_become_best() -> None:
    seen: list[Array] = []

    def f(X: Array) -> Array:
        seen.append(X.copy())
        return np.where(X[:, 0] > 4.9, np.nan, np.sum(X**2, axis=1))

    r = run("import numpy as np\n"
            "def optimize(f, dim, lower, upper, budget, rng):\n"
            "    v = f(np.array([[100.0] * dim, [1.0] * dim, [-100.0] * dim]))\n"
            "    assert np.isinf(v[0]) and v[1] == dim\n",
            f, DIM, INST.lower, INST.upper, BUDGET, 1, sandbox=False)
    assert r.status == "ok", r.error
    assert np.max(seen[0]) == 5.0 and np.min(seen[0]) == -5.0
    assert r.f_best == DIM


def test_infinite_loop_times_out() -> None:
    r = go("def optimize(f, dim, lower, upper, budget, rng):\n"
           "    f(lower)\n"
           "    while True:\n"
           "        pass\n", timeout=2)
    assert r.status == "timeout" and r.evals == 1 and r.wall_sec < 15


def test_process_death_is_reported_as_crash() -> None:
    r = go("import os\n"
           "def optimize(f, dim, lower, upper, budget, rng):\n"
           "    os._exit(9)\n")
    assert r.status == "crashed" and "exit code 9" in r.error


def test_judge_ranks_baselines_and_fails_broken_code() -> None:
    kwargs = dict(dim=DIM, instance_seeds=(1, 2), run_seeds=(1, 2, 3), budget=3000,
                  sandbox=False)
    scores = {name: judge(baselines.source(name), PROBLEMS["STD-001"], **kwargs)  # type: ignore[arg-type]
              for name in baselines.NAMES}
    assert all(len(s["runs"]) == 6 and not s["f_ref_provisional"] for s in scores.values())
    assert all(r["status"] == "ok" for s in scores.values() for r in s["runs"])
    assert scores["cmaes"]["score"] > scores["random_search"]["score"]
    assert scores["differential_evolution"]["score"] > scores["random_search"]["score"]
    assert scores["cmaes"]["median_precision"] < 1e-6

    broken = judge("def optimize(*a):\n    raise ValueError\n", PROBLEMS["STD-001"], **kwargs)  # type: ignore[arg-type]
    assert broken["score"] == 0 and broken["median_precision"] is None


def test_judge_marks_unknown_optimum_as_provisional_unless_f_ref_given() -> None:
    kwargs = dict(dim=DIM, instance_seeds=(1,), run_seeds=(1, 2), budget=500, sandbox=False)
    out = judge(RANDOM, PROBLEMS["TR-001"], **kwargs)  # type: ignore[arg-type]
    assert out["f_ref_provisional"]
    out = judge(RANDOM, PROBLEMS["TR-001"], f_ref={1: -100.0}, **kwargs)  # type: ignore[arg-type]
    assert not out["f_ref_provisional"] and out["score"] == 0
