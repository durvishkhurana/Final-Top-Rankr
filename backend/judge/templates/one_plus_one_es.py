import numpy as np


def optimize(f, dim, lower, upper, budget, rng):
    # (1+1)-ES with the one-fifth success rule: keep one point, try one mutated
    # copy per step, widen the step after a success and narrow it after a failure.
    x = rng.uniform(lower, upper)
    fx = f(x)
    sigma = 0.3 * (upper - lower)

    for _ in range(budget - 1):
        y = np.clip(x + sigma * rng.standard_normal(dim), lower, upper)
        fy = f(y)
        if fy <= fx:
            x, fx = y, fy
            sigma *= 1.5
        else:
            sigma *= 1.5 ** -0.25
