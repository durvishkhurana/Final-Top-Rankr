"""Problem instances: a base function plus a seeded shift and rotation.

f_inst(x) = f_base(R (x - x_star) + z_opt)

For functions with a known optimum this puts the optimum at x_star, inside the box.
For the others (z_opt = None) it is a plain shift and rotation of the landscape.
Instance parameters must never leave the worker process.
"""

import zlib
from dataclasses import dataclass
from typing import Any

import numpy as np

from .functions import Array, Problem


@dataclass(frozen=True)
class Instance:
    problem: Problem
    dim: int
    lower: Array
    upper: Array
    x_star: Array
    rotation: Array
    f_opt: float | None  # exact optimum value when the problem's optimum is known
    centre: float = 0.0  # middle of the box: contributed problems keep their coordinates

    def __call__(self, X: Array) -> Array:
        z_opt = self.problem.z_opt if self.problem.z_opt is not None else self.centre
        return self.problem.fn((X - self.x_star) @ self.rotation.T + z_opt)


def make_instance(problem: Problem, dim: int, instance_seed: int) -> Any:
    if dim < 2:
        raise ValueError("dim must be at least 2")
    if problem.factory is not None:
        return problem.factory(problem, dim, instance_seed)
    rng = np.random.default_rng([instance_seed, dim, zlib.crc32(problem.id.encode())])
    if problem.lower is not None and problem.upper is not None:
        # Contributed: shift only. A rotation would move the corners of the box outside
        # the region the smoke test checked.
        centre = (problem.lower + problem.upper) / 2
        x_star = centre + rng.uniform(-1.0, 1.0, dim) * problem.shift_frac * problem.bound
        return Instance(problem, dim, np.full(dim, problem.lower), np.full(dim, problem.upper),
                        x_star, np.eye(dim), None, centre)
    x_star = rng.uniform(-1.0, 1.0, dim) * problem.shift_frac * problem.bound
    Q, R = np.linalg.qr(rng.standard_normal((dim, dim)))
    Q = Q * np.sign(np.diag(R))  # sign fix makes Q uniformly distributed
    f_opt = None
    if problem.z_opt is not None:
        f_opt = float(problem.fn(np.full((1, dim), problem.z_opt))[0])
    bound = np.full(dim, problem.bound)
    return Instance(problem, dim, -bound, bound, x_star, Q, f_opt)
