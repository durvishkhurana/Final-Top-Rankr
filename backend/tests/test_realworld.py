import numpy as np
import pytest

from judge.functions import PROBLEMS
from judge.instance import make_instance

RW = [(pid, dim) for pid in ("RW-001", "RW-002", "RW-003") for dim in PROBLEMS[pid].dims]


@pytest.mark.parametrize(("pid", "dim"), RW)
def test_batch_matches_single_and_is_seeded(pid: str, dim: int) -> None:
    inst = make_instance(PROBLEMS[pid], dim, 1)
    X = np.random.default_rng(0).uniform(0, 1, (50, dim))
    values = inst(X)
    assert values.shape == (50,) and np.all(np.isfinite(values)) and np.all(values >= 0)
    np.testing.assert_allclose([inst(x[None, :])[0] for x in X], values)
    np.testing.assert_array_equal(make_instance(PROBLEMS[pid], dim, 1)(X), values)
    assert not np.allclose(make_instance(PROBLEMS[pid], dim, 2)(X), values)


def test_timetable_objective_counts_clashes_and_missing_seats() -> None:
    inst = make_instance(PROBLEMS["RW-001"], 10, 1)
    everything_in_one_slot = np.zeros(10)
    d = inst.decode(everything_in_one_slot)
    assert len(d["slots"][0]) == 10 and all(len(s) == 0 for s in d["slots"][1:])
    assert d["clashing_students"] == inst.conflicts.sum() / 2
    seated = np.minimum(np.sort(inst.sizes)[::-1][: len(inst.capacities)], inst.capacities)
    assert d["unseated_students"] == inst.sizes.sum() - seated.sum()
    total = 100 * (d["clashing_students"] + d["unseated_students"]) / inst.sizes.sum()
    assert inst(everything_in_one_slot[None, :])[0] == pytest.approx(total)


def test_facility_objective_is_weighted_mean_distance_to_nearest_stop() -> None:
    inst = make_instance(PROBLEMS["RW-002"], 6, 1)
    d = inst.decode(np.full(6, 0.5))
    assert sum(s["people"] for s in d["stops"]) == inst.weights.sum()
    centre = np.array([5.0, 5.0])
    expected = np.sqrt(((inst.demand - centre) ** 2).sum(axis=1)) @ inst.weights
    assert d["mean_distance"] == pytest.approx(expected / inst.weights.sum())


def test_routing_respects_capacity_and_visits_everyone_once() -> None:
    inst = make_instance(PROBLEMS["RW-003"], 20, 1)
    x = np.random.default_rng(1).uniform(0, 1, 20)
    d = inst.decode(x)
    visited = [c for r in d["routes"] for c in r["customers"]]
    assert sorted(visited) == list(range(20)) and visited == list(np.argsort(x))
    assert all(r["load"] <= inst.capacity for r in d["routes"])
    # distance recomputed from the decoded routes
    total = 0.0
    for r in d["routes"]:
        stops = [inst.depot, *inst.customers[r["customers"]], inst.depot]
        total += sum(float(np.linalg.norm(b - a)) for a, b in zip(stops, stops[1:], strict=False))
    assert d["total_distance"] == pytest.approx(total)
