import numpy as np
import pytest

from judge.scoring import (
    P_MAX,
    P_MIN,
    aggregate,
    aocc,
    best_so_far_at,
    checkpoints,
    default_budget,
    precision,
)


@pytest.mark.parametrize("budget", [1, 2, 50, 4000, 10000, 200000])
def test_checkpoints_increase_and_end_at_budget(budget: int) -> None:
    pts = checkpoints(budget)
    assert pts[0] == 1 and pts[-1] == budget
    assert all(a < b for a, b in zip(pts, pts[1:], strict=False))
    assert default_budget(10) == 20000


def test_aocc_range_and_extremes() -> None:
    assert aocc([5.0 + P_MAX * 10] * 10, 5.0) == 0.0
    assert aocc([5.0] * 10, 5.0) == 1.0
    assert aocc([4.0] * 10, 5.0) == 1.0  # beating f_ref cannot score lower
    assert aocc([], 0.0) == 0.0
    assert aocc([np.inf, np.inf], 0.0) == 0.0
    assert aocc([1e-3] * 4, 0.0) == pytest.approx(0.5)  # halfway on the log scale
    assert precision(1.0, 2.0) == P_MIN


def test_aocc_monotone_better_trace_never_scores_lower() -> None:
    rng = np.random.default_rng(0)
    for _ in range(500):
        f_ref = rng.normal()
        worse = f_ref + np.minimum.accumulate(10 ** rng.uniform(-10, 3, 30))
        better = f_ref + (worse - f_ref) * rng.uniform(0, 1, 30)
        assert aocc(better, f_ref) >= aocc(worse, f_ref)


def test_aocc_rewards_speed() -> None:
    fast = [1e2] * 2 + [1e-8] * 8
    slow = [1e2] * 8 + [1e-8] * 2
    assert aocc(fast, 0.0) > aocc(slow, 0.0)


def test_aocc_weights_checkpoints_by_the_evaluations_they_cover() -> None:
    # precision 1e2 for evaluations 1-9, then 1e-8 for evaluation 10 only
    assert aocc([1e2, 1e-8], 0.0, [1, 10]) == pytest.approx(0.1)
    pts = checkpoints(5000)
    assert aocc([1e-3] * len(pts), 0.0, pts) == pytest.approx(0.5)
    rng = np.random.default_rng(1)
    for _ in range(200):
        worse = np.minimum.accumulate(10 ** rng.uniform(-10, 3, len(pts)))
        assert aocc(worse * rng.uniform(0, 1, len(pts)), 0.0, pts) >= aocc(worse, 0.0, pts)


def test_aggregate_median_over_seeds_mean_over_instances() -> None:
    out = aggregate([[0.1, 0.2, 0.9], [0.4, 0.4, 0.4]])
    assert out["aocc"] == pytest.approx(0.3)
    assert out["score"] == 300
    assert out["iqr"] == pytest.approx(0.2)


def test_best_so_far_at_matches_brute_force() -> None:
    rng = np.random.default_rng(3)
    values = rng.normal(size=1000)
    pts = checkpoints(1000)
    expected = [float(np.min(values[:p])) for p in pts]
    trace: list[float] = []
    best, done = np.inf, 0
    while done < 1000:
        chunk = values[done : done + int(rng.integers(1, 90))]
        trace += best_so_far_at(chunk, best, done, pts)
        best = min(best, float(np.min(chunk)))
        done += len(chunk)
    assert trace == expected
