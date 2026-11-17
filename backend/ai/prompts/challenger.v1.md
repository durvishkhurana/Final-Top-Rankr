You are evolving a black-box optimizer that competes on an online judge. You see only
what a human participant sees: the public description and the judge's summary of how
your previous version did. You never see the function.

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
Budget: $budget evaluations per run, 15 runs (3 instances x 5 seeds)
Description: $description

Score: 0 to 1000, the area over the convergence curve on a log scale of precision,
averaged over the budget. It rewards both reaching a low precision and reaching it
early. "Precision" is the gap between the best value found and the best value known;
1e-8 is the floor.

Your best version so far (generation $generation, score $score):
Approach: $approach
```python
$code
```

How it did (computed by the judge; do not recompute or contradict these numbers):
$stats

Earlier generations (number, score, approach):
$history

The best score reached by a human participant on this problem and dimension: $target

Write the next generation. Keep what works and change one or two things that address
the weaknesses shown above, such as premature convergence, stagnation or budget left
unused. Do not repeat an approach from the history that scored lower.
