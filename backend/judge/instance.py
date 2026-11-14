"""Problem instances: a base function plus a seeded shift and rotation.

f_inst(x) = f_base(R (x - x_star) + z_opt)

For functions with a known optimum this puts the optimum at x_star, inside the box.
For the others (z_opt = None) it is a plain shift and rotation of the landscape.
Instance parameters must never leave the worker process.
"""

import zlib
from dataclasses import dataclass

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

    def __call__(self, X: Array) -> Array:
        z_opt = self.problem.z_opt or 0.0
        return self.problem.fn((X - self.x_star) @ self.rotation.T + z_opt)


def make_instance(problem: Problem, dim: int, instance_seed: int) -> Instance:
    if dim < 2:
        raise ValueError("dim must be at least 2")
    rng = np.random.default_rng([instance_seed, dim, zlib.crc32(problem.id.encode())])
    x_star = rng.uniform(-1.0, 1.0, dim) * problem.shift_frac * problem.bound
    Q, R = np.linalg.qr(rng.standard_normal((dim, dim)))
    Q = Q * np.sign(np.diag(R))  # sign fix makes Q uniformly distributed
    f_opt = None
    if problem.z_opt is not None:
        f_opt = float(problem.fn(np.full((1, dim), problem.z_opt))[0])
    bound = np.full(dim, problem.bound)
    return Instance(problem, dim, -bound, bound, x_star, Q, f_opt)
