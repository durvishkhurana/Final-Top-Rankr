"""CMA-ES (Hansen's standard formulation) with restarts that double the population."""

import numpy as np


def optimize(f, dim, lower, upper, budget, rng):
    lam = 4 + int(3 * np.log(dim))
    while True:  # the budget running out ends the run
        _descend(f, dim, lower, upper - lower, rng, lam)
        lam *= 2


def _descend(f, n, lower, span, rng, lam):
    # Works in the unit box; points are clipped to it before evaluation.
    mu = lam // 2
    w = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
    w /= w.sum()
    mueff = 1 / np.sum(w**2)
    cc = (4 + mueff / n) / (n + 4 + 2 * mueff / n)
    cs = (mueff + 2) / (n + mueff + 5)
    c1 = 2 / ((n + 1.3) ** 2 + mueff)
    cmu = min(1 - c1, 2 * (mueff - 2 + 1 / mueff) / ((n + 2) ** 2 + mueff))
    damps = 1 + 2 * max(0, np.sqrt((mueff - 1) / (n + 1)) - 1) + cs
    chi_n = np.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n**2))

    mean, sigma = rng.uniform(0, 1, n), 0.3
    pc, ps = np.zeros(n), np.zeros(n)
    B, D, C = np.eye(n), np.ones(n), np.eye(n)
    history = []
    patience = 10 + int(30 * n / lam)

    for gen in range(1, 10**9):
        u = np.clip(mean + sigma * (rng.standard_normal((lam, n)) * D) @ B.T, 0, 1)
        fit = np.atleast_1d(f(lower + u * span))
        order = np.argsort(fit)
        y = (u[order[:mu]] - mean) / sigma
        yw = w @ y
        mean = mean + sigma * yw

        ps = (1 - cs) * ps + np.sqrt(cs * (2 - cs) * mueff) * (B @ ((B.T @ yw) / D))
        hsig = np.linalg.norm(ps) / np.sqrt(1 - (1 - cs) ** (2 * gen)) / chi_n < 1.4 + 2 / (n + 1)
        pc = (1 - cc) * pc + hsig * np.sqrt(cc * (2 - cc) * mueff) * yw
        C = ((1 - c1 - cmu) * C
             + c1 * (np.outer(pc, pc) + (1 - hsig) * cc * (2 - cc) * C)
             + cmu * (y.T * w) @ y)
        sigma *= np.exp((cs / damps) * (np.linalg.norm(ps) / chi_n - 1))

        C = np.triu(C) + np.triu(C, 1).T
        eigvals, B = np.linalg.eigh(C)
        D = np.sqrt(np.maximum(eigvals, 1e-20))

        history.append(fit[order[0]])
        stalled = len(history) > patience and np.ptp(history[-patience:]) < 1e-12
        if stalled or sigma * D.max() < 1e-12 or D.max() > 1e7 * D.min() or sigma > 1e3:
            return
