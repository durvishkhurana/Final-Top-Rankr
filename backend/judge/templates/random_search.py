def optimize(f, dim, lower, upper, budget, rng):
    # Sample the whole budget uniformly in the box and evaluate it as one batch.
    # f(X) takes an array of shape (n, dim) and returns n values.
    X = rng.uniform(lower, upper, size=(budget, dim))
    f(X)
