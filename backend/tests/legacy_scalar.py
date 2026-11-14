"""Original scalar TR-001..TR-010 implementations, kept only to check the vectorised ports."""
# ruff: noqa
# mypy: ignore-errors
import math

import numpy as np

def _safe_exp(v):
    """Clamp argument to avoid overflow."""
    return math.exp(max(-700, min(700, v)))

def evaluate_TR001(x, D):
    """Cascading Tide — circular sine coupling."""
    total = 0.0
    for i in range(D):
        xi   = x[i]
        xi1  = x[(i + 1) % D]
        target = 1.0 / (i + 1)
        total += (xi - target) ** 2 + 0.3 * math.sin(3 * math.pi * xi * xi1)
    return total

def evaluate_TR002(x, D):
    """Phantom Plateau — sigmoid minus Gaussian."""
    s1 = sum(xi ** 2 for xi in x)
    s2 = sum((xi - 2) ** 2 for xi in x)
    sigmoid = 1.0 / (1.0 + _safe_exp(-0.5 * s1))
    return sigmoid - _safe_exp(-0.01 * s2)

def evaluate_TR003(x, D):
    """Spiral Sink — polar ridges on consecutive pairs."""
    total = 0.0
    for i in range(D - 1):
        xi  = x[i]
        xi1 = x[i + 1]
        theta = math.atan2(xi1, xi + 1e-9)
        r     = math.sqrt(xi ** 2 + xi1 ** 2)
        total += r ** 2 + 2 * math.sin(3 * theta + r) ** 2 + 0.1 * (xi - xi1) ** 2
    return total

def evaluate_TR004(x, D):
    """Mirage Basin — three false attractors."""
    A = sum(xi ** 2 for xi in x)
    B = sum(math.cos(2 * math.pi * xi / 3) for xi in x)
    C = sum(math.sin(math.pi * x[i]) * x[(i + 1) % D] for i in range(D))
    return A / D - 1.5 * _safe_exp(-0.1 * A) + 0.8 * B + 0.4 * abs(C)

def evaluate_TR005(x, D):
    """Recursive Ripple — four-scale fractal surface."""
    total = 0.05 * sum(xi ** 2 for xi in x)
    for k in range(1, 5):
        scale = 1.0 / (2 ** k)
        total += scale * sum(math.cos(2 ** k * math.pi * xi + k) for xi in x)
    return total

def evaluate_TR006(x, D):
    """Tidal Lock — constrained, optimum on constraint boundary."""
    obj = (sum((xi - 3) ** 2 for xi in x)
           + sum(math.sin(x[i] * x[(i + 1) % D]) for i in range(D)))
    g1_viol = max(0.0, sum(xi ** 2 for xi in x) - D * 4)
    g2_viol = sum(max(0.0, abs(x[i] - x[i + 1]) - 1.5) for i in range(D - 1))
    penalty = 1e5 * g1_viol ** 2 + 1e5 * g2_viol ** 2
    return obj + penalty

def evaluate_TR007(x, D):
    """Vortex Core — ill-conditioned rotated ellipsoid + sinusoidal overlay."""
    R = _get_rotation_matrix(D)
    y = R @ np.array(x, dtype=float)
    ell = float(y[0] ** 2 + 1e5 * sum(float(yi) ** 2 for yi in y[1:]))
    sin_overlay = float(
        sum(0.5 * math.sin(4 * math.pi * float(yi)) * float(yi) ** 2 for yi in y)
    )
    return ell + sin_overlay

# Cache rotation matrices per dimension so TR-007 produces consistent results
# across calls and we don't pay the QR cost on every evaluation.
_rotation_cache: dict = {}

def _get_rotation_matrix(D: int):
    """Return (and cache) the deterministic D×D rotation matrix for TR-007."""
    if D not in _rotation_cache:
        rng = np.random.default_rng(42)
        A = rng.standard_normal((D, D))
        R, _ = np.linalg.qr(A)
        _rotation_cache[D] = R
    return _rotation_cache[D]

def evaluate_TR008(x, D):
    """Hollow Crown — hyper-ring optimum with symmetry breaker."""
    R_target = math.sqrt(D)
    r = math.sqrt(sum(xi ** 2 for xi in x))
    ring_term = (r - R_target) ** 4
    smooth    = 0.1 * sum((x[i] - x[i + 1]) ** 2 for i in range(D - 1))
    sym_break = 0.01 * (x[0] - math.sqrt(D) / 2) ** 2
    return ring_term + smooth + sym_break

def evaluate_TR009(x, D):
    """Phase Shift Labyrinth — frequency and phase scale with D."""
    total = 0.0
    for i in range(D):
        phi_i   = 2 * math.pi * (i + 1) / D
        omega_i = 1.0 + (i + 1) / D
        total  += x[i] ** 2 * (1 + 0.5 * math.sin(omega_i * x[i] + phi_i))
    mean_term = (sum(x) / D) ** 2
    return total + 0.3 * mean_term

def evaluate_TR010(x, D):
    """Abyss Gate — fully deceptive adversarial function."""
    S = sum(x) / D
    Q = sum((xi - S) ** 2 for xi in x)
    T = sum(math.sin(x[i] ** 2 - x[(i + 1) % D]) for i in range(D))
    U = abs(sum((-1) ** i * x[i] for i in range(D)))
    return -_safe_exp(-0.5 * Q) * math.cos(2 * math.pi * S) + 0.5 * T + 0.1 * U
