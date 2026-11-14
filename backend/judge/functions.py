"""Built-in base fitness functions, vectorised: X of shape (n, D) -> values of shape (n,).

Base functions are never exposed to submissions; they are evaluated in the worker
after an instance transformation (see instance.py).
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

import numpy as np
import numpy.typing as npt

Array = npt.NDArray[np.float64]
Fn = Callable[[Array], Array]


def _exp(v: Array) -> Array:
    return np.exp(np.clip(v, -700.0, 700.0))


def _next(X: Array) -> Array:
    """x[(i + 1) % D] for every i."""
    return np.roll(X, -1, axis=1)


# --- TR-001 .. TR-010: the original TopRanker functions ---------------------------------


def tr001(X: Array) -> Array:
    """Cascading Tide: circular sine coupling."""
    target = 1.0 / np.arange(1, X.shape[1] + 1)
    return np.sum((X - target) ** 2 + 0.3 * np.sin(3 * np.pi * X * _next(X)), axis=1)


def tr002(X: Array) -> Array:
    """Phantom Plateau: sigmoid minus Gaussian."""
    s1 = np.sum(X**2, axis=1)
    s2 = np.sum((X - 2) ** 2, axis=1)
    return 1.0 / (1.0 + _exp(-0.5 * s1)) - _exp(-0.01 * s2)


def tr003(X: Array) -> Array:
    """Spiral Sink: polar ridges on consecutive pairs."""
    a, b = X[:, :-1], X[:, 1:]
    theta = np.arctan2(b, a + 1e-9)
    r = np.sqrt(a**2 + b**2)
    return np.sum(r**2 + 2 * np.sin(3 * theta + r) ** 2 + 0.1 * (a - b) ** 2, axis=1)


def tr004(X: Array) -> Array:
    """Mirage Basin: three false attractors."""
    D = X.shape[1]
    A = np.sum(X**2, axis=1)
    B = np.sum(np.cos(2 * np.pi * X / 3), axis=1)
    C = np.sum(np.sin(np.pi * X) * _next(X), axis=1)
    return A / D - 1.5 * _exp(-0.1 * A) + 0.8 * B + 0.4 * np.abs(C)


def tr005(X: Array) -> Array:
    """Recursive Ripple: four-scale fractal surface."""
    total = 0.05 * np.sum(X**2, axis=1)
    for k in range(1, 5):
        total += np.sum(np.cos(2**k * np.pi * X + k), axis=1) / 2**k
    return total


def tr006(X: Array) -> Array:
    """Tidal Lock: constrained, optimum on the constraint boundary."""
    D = X.shape[1]
    obj = np.sum((X - 3) ** 2, axis=1) + np.sum(np.sin(X * _next(X)), axis=1)
    g1 = np.maximum(0.0, np.sum(X**2, axis=1) - D * 4)
    g2 = np.sum(np.maximum(0.0, np.abs(X[:, :-1] - X[:, 1:]) - 1.5), axis=1)
    return obj + 1e5 * g1**2 + 1e5 * g2**2


@cache
def _tr007_rotation(D: int) -> Array:
    Q, _ = np.linalg.qr(np.random.default_rng(42).standard_normal((D, D)))
    return Q


def tr007(X: Array) -> Array:
    """Vortex Core: ill-conditioned rotated ellipsoid with a sinusoidal overlay."""
    Y = X @ _tr007_rotation(X.shape[1]).T
    ell = Y[:, 0] ** 2 + 1e5 * np.sum(Y[:, 1:] ** 2, axis=1)
    return ell + np.sum(0.5 * np.sin(4 * np.pi * Y) * Y**2, axis=1)


def tr008(X: Array) -> Array:
    """Hollow Crown: hyper-ring optimum with a symmetry breaker."""
    root = np.sqrt(X.shape[1])
    r = np.sqrt(np.sum(X**2, axis=1))
    smooth = 0.1 * np.sum((X[:, :-1] - X[:, 1:]) ** 2, axis=1)
    return (r - root) ** 4 + smooth + 0.01 * (X[:, 0] - root / 2) ** 2


def tr009(X: Array) -> Array:
    """Phase Shift Labyrinth: frequency and phase scale with D."""
    D = X.shape[1]
    i = np.arange(1, D + 1)
    phi, omega = 2 * np.pi * i / D, 1.0 + i / D
    total = np.sum(X**2 * (1 + 0.5 * np.sin(omega * X + phi)), axis=1)
    return total + 0.3 * np.mean(X, axis=1) ** 2


def tr010(X: Array) -> Array:
    """Abyss Gate: deceptive function."""
    S = np.mean(X, axis=1)
    Q = np.sum((X - S[:, None]) ** 2, axis=1)
    T = np.sum(np.sin(X**2 - _next(X)), axis=1)
    U = np.abs(X @ ((-1.0) ** np.arange(X.shape[1])))
    return -_exp(-0.5 * Q) * np.cos(2 * np.pi * S) + 0.5 * T + 0.1 * U


# --- Standard comparison set (optimum value 0 at z = z_opt) -----------------------------


def sphere(Z: Array) -> Array:
    return np.sum(Z**2, axis=1)


def ellipsoid(Z: Array) -> Array:
    D = Z.shape[1]
    return np.sum(10.0 ** (6 * np.arange(D) / max(D - 1, 1)) * Z**2, axis=1)


def rosenbrock(Z: Array) -> Array:
    a, b = Z[:, :-1], Z[:, 1:]
    return np.sum(100 * (b - a**2) ** 2 + (1 - a) ** 2, axis=1)


def rastrigin(Z: Array) -> Array:
    return np.sum(Z**2 - 10 * np.cos(2 * np.pi * Z) + 10, axis=1)


def ackley(Z: Array) -> Array:
    a = -20 * np.exp(-0.2 * np.sqrt(np.mean(Z**2, axis=1)))
    b = -np.exp(np.mean(np.cos(2 * np.pi * Z), axis=1))
    # abs() removes the ~1e-16 negative rounding residue at the optimum
    return np.abs(a + b + 20 + np.e)


def griewank(Z: Array) -> Array:
    i = np.sqrt(np.arange(1, Z.shape[1] + 1))
    return np.sum(Z**2, axis=1) / 4000 - np.prod(np.cos(Z / i), axis=1) + 1


SCHWEFEL_OPT = 420.968746227503


def schwefel(Z: Array) -> Array:
    # The plain formula is only valid on [-500, 500]; outside, evaluate the clipped
    # point and add a quadratic penalty so the optimum stays where it is.
    Zc = np.clip(Z, -500.0, 500.0)
    base = 418.982887272433799 * Z.shape[1] - np.sum(Zc * np.sin(np.sqrt(np.abs(Zc))), axis=1)
    return np.abs(base) + 0.01 * np.sum((Z - Zc) ** 2, axis=1)


def lunacek(Z: Array) -> Array:
    """Lunacek bi-Rastrigin: two funnels, the better one at z = 2.5."""
    D = Z.shape[1]
    mu0, d = 2.5, 1.0
    s = 1 - 1 / (2 * np.sqrt(D + 20) - 8.2)
    mu1 = -np.sqrt((mu0**2 - d) / s)
    funnels = np.minimum(
        np.sum((Z - mu0) ** 2, axis=1), d * D + s * np.sum((Z - mu1) ** 2, axis=1)
    )
    return funnels + 10 * (D - np.sum(np.cos(2 * np.pi * (Z - mu0)), axis=1))


@dataclass(frozen=True)
class Problem:
    id: str
    name: str
    fn: Fn
    bound: float  # search box is [-bound, bound]^D
    # Optimum location in the base function's own coordinates, when it is known
    # (then the optimum value is fn(z_opt)). None: f_ref comes from reference runs.
    z_opt: float | None = None
    # Instance optimum/shift is drawn within this fraction of the box half-width.
    shift_frac: float = 0.4


_TR = [
    ("TR-001", "Cascading Tide", tr001, 5.0),
    ("TR-002", "Phantom Plateau", tr002, 10.0),
    ("TR-003", "Spiral Sink", tr003, 6.0),
    ("TR-004", "Mirage Basin", tr004, 8.0),
    ("TR-005", "Recursive Ripple", tr005, 4.0),
    ("TR-006", "Tidal Lock", tr006, 7.0),
    ("TR-007", "Vortex Core", tr007, 5.0),
    ("TR-008", "Hollow Crown", tr008, 8.0),
    ("TR-009", "Phase Shift Labyrinth", tr009, 10.0),
    ("TR-010", "Abyss Gate", tr010, float(np.pi)),
]

_STD = [
    ("STD-001", "Sphere", sphere, 5.0, 0.0),
    ("STD-002", "Ellipsoid", ellipsoid, 5.0, 0.0),
    ("STD-003", "Rosenbrock", rosenbrock, 5.0, 1.0),
    ("STD-004", "Rastrigin", rastrigin, 5.0, 0.0),
    ("STD-005", "Ackley", ackley, 32.768, 0.0),
    ("STD-006", "Griewank", griewank, 600.0, 0.0),
    ("STD-007", "Schwefel", schwefel, 500.0, SCHWEFEL_OPT),
    ("STD-008", "Lunacek bi-Rastrigin", lunacek, 5.0, 2.5),
]

PROBLEMS: dict[str, Problem] = {
    **{pid: Problem(pid, name, fn, b, shift_frac=0.1) for pid, name, fn, b in _TR},
    **{pid: Problem(pid, name, fn, b, z_opt=z) for pid, name, fn, b, z in _STD},
}
