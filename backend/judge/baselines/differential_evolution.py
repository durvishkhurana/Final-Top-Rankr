from scipy.optimize import differential_evolution


def optimize(f, dim, lower, upper, budget, rng):
    bounds = list(zip(lower, upper, strict=True))
    # SciPy defaults, except: each generation is evaluated as one batch (vectorized,
    # deferred updating), and tol=0 / no polish so only the budget ends the run.
    # Restarts if the population collapses before the budget is spent.
    while True:
        differential_evolution(lambda X: f(X.T), bounds, maxiter=10**9, tol=0, polish=False,
                               seed=rng, vectorized=True, updating="deferred")
