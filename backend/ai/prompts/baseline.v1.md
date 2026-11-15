Write a black-box optimizer for the problem described below. You see only what a human
participant sees: the public description. You do not see the function.

Contract. Return Python source that defines:

    def optimize(f, dim, lower, upper, budget, rng) -> None

- `f(X)` minimises; X is one point of shape (dim,) or a batch of shape (n, dim), and it
  returns one value or n values. Every point counts against `budget`; when the budget
  is used up `f` raises an exception that ends the run, so do not catch broad exceptions
  around calls to `f`.
- `lower` and `upper` are NumPy arrays of shape (dim,). `rng` is a seeded
  numpy.random.Generator; use it for all randomness.
- Only the Python standard library, NumPy and SciPy are available.
- Evaluate in batches (a whole population per call) wherever the algorithm allows.
- The return value is ignored; the platform records every evaluated point itself.

Problem: $name
Dimension: $dim
Search box: $lower to $upper in every variable
Budget: $budget evaluations
Description: $description

Choose an approach that suits the description and use the whole budget.
