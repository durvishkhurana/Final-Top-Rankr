def optimize(f, dim, lower, upper, budget, rng):
    f(rng.uniform(lower, upper, size=(budget, dim)))
