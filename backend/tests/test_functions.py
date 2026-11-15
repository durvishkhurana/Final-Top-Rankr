import numpy as np
import pytest

from judge.functions import PROBLEMS
from judge.instance import make_instance

from . import legacy_scalar

FUNCTION_IDS = [p for p, v in PROBLEMS.items() if v.factory is None]
TR_IDS = [p for p in PROBLEMS if p.startswith("TR-")]
STD_IDS = [p for p in PROBLEMS if p.startswith("STD-")]


@pytest.mark.parametrize("pid", TR_IDS)
@pytest.mark.parametrize("dim", [2, 5, 20, 50])
def test_vectorised_matches_original_scalar(pid: str, dim: int) -> None:
    problem = PROBLEMS[pid]
    X = np.random.default_rng(dim).uniform(-problem.bound, problem.bound, (40, dim))
    old = getattr(legacy_scalar, "evaluate_" + pid.replace("-", ""))
    expected = [old(list(x), dim) for x in X]
    np.testing.assert_allclose(problem.fn(X), expected, rtol=1e-9, atol=1e-9)


@pytest.mark.parametrize("pid", FUNCTION_IDS)
def test_batch_shape_and_single_point_agree(pid: str) -> None:
    problem = PROBLEMS[pid]
    X = np.random.default_rng(0).uniform(-problem.bound, problem.bound, (7, 10))
    values = problem.fn(X)
    assert values.shape == (7,)
    assert np.all(np.isfinite(values))
    np.testing.assert_allclose(problem.fn(X[3:4])[0], values[3])


@pytest.mark.parametrize("pid", STD_IDS)
@pytest.mark.parametrize("dim", [2, 5, 20])
def test_standard_optimum_is_zero_and_minimal(pid: str, dim: int) -> None:
    problem = PROBLEMS[pid]
    assert problem.z_opt is not None
    at_opt = problem.fn(np.full((1, dim), problem.z_opt))[0]
    assert 0 <= at_opt < 1e-8
    X = np.random.default_rng(1).uniform(-problem.bound, problem.bound, (2000, dim))
    assert np.all(problem.fn(X) >= at_opt)


@pytest.mark.parametrize("pid", FUNCTION_IDS)
def test_instance_is_seeded_and_in_bounds(pid: str) -> None:
    problem = PROBLEMS[pid]
    a, b, c = (make_instance(problem, 10, s) for s in (1, 1, 2))
    np.testing.assert_array_equal(a.x_star, b.x_star)
    np.testing.assert_array_equal(a.rotation, b.rotation)
    assert not np.allclose(a.x_star, c.x_star)
    np.testing.assert_allclose(a.rotation @ a.rotation.T, np.eye(10), atol=1e-12)
    margin = 0.5 * problem.bound
    assert np.all(a.x_star > a.lower + margin) and np.all(a.x_star < a.upper - margin)


@pytest.mark.parametrize("pid", STD_IDS)
def test_instance_optimum_sits_at_x_star(pid: str) -> None:
    inst = make_instance(PROBLEMS[pid], 10, 7)
    assert inst.f_opt is not None
    assert inst(inst.x_star[None, :])[0] == pytest.approx(inst.f_opt, abs=1e-8)
    X = np.random.default_rng(2).uniform(inst.lower, inst.upper, (2000, 10))
    assert np.all(inst(X) >= inst.f_opt)


def test_instances_differ_across_dims_and_problems() -> None:
    a = make_instance(PROBLEMS["STD-001"], 5, 1)
    b = make_instance(PROBLEMS["STD-004"], 5, 1)
    assert not np.allclose(a.x_star / a.problem.bound, b.x_star / b.problem.bound)
    with pytest.raises(ValueError):
        make_instance(PROBLEMS["STD-001"], 1, 1)
