# The judge

How a submission is run and scored. Everything on this page is implemented in
`backend/judge/` and `sandbox/`.

## Submission contract

A submission is one Python file that defines:

```python
def optimize(f, dim, lower, upper, budget, rng) -> None:
    ...
```

| Argument | Meaning |
|---|---|
| `f(X)` | The hidden objective, to be minimised. `X` is one point of shape `(dim,)` (returns a float) or a batch of shape `(n, dim)` (returns an array of `n` values). |
| `dim` | Number of variables. |
| `lower`, `upper` | Arrays of shape `(dim,)`: the search box. |
| `budget` | Total number of points `f` will evaluate. |
| `rng` | A seeded `numpy.random.Generator`. Using it for all randomness makes a run reproducible. |

Rules:

- Every point counts against the budget, in a batch or alone. When the budget is used
  up `f` raises `BudgetExhausted` and the run ends normally. A batch larger than the
  remaining budget is evaluated up to the budget and then raises. The name
  `BudgetExhausted` is available in the submission's namespace.
- Points outside the box are moved to the nearest point inside it before evaluation.
- A non-finite objective value is returned as `inf` and never counts as a best value.
- The return value of `optimize` is ignored. The score comes only from the points the
  platform evaluated.
- Available packages: the Python standard library, NumPy and SciPy.
- Evaluate in batches where the algorithm allows it (a whole population per call).
  Each call to `f` is a round trip to the judge; see Throughput below.

Minimal example (random search):

```python
def optimize(f, dim, lower, upper, budget, rng):
    f(rng.uniform(lower, upper, size=(budget, dim)))
```

## Where the function lives

The objective and the instance parameters exist only in the judge process. The
submission runs in a separate, locked-down container (see `SECURITY.md`) and its `f`
is a proxy: it sends points to the judge and receives values back over the container's
original stdin/stdout pipes. Inside the container the submission's own stdout and
stderr are redirected to a captured log (truncated to 64 kB) before its code is
loaded, so printing cannot corrupt the protocol. The judge counts evaluations and
records the trace itself.

## Problems and instances

| Set | Problems |
|---|---|
| TR-001 to TR-010 | Cascading Tide, Phantom Plateau, Spiral Sink, Mirage Basin, Recursive Ripple, Tidal Lock, Vortex Core, Hollow Crown, Phase Shift Labyrinth, Abyss Gate |
| STD-001 to STD-008 | Sphere, Ellipsoid, Rosenbrock, Rastrigin, Ackley, Griewank, Schwefel, Lunacek bi-Rastrigin |

| D2-001 to D2-004 | Two-variable demos (Rastrigin, Rosenbrock, Ackley, Lunacek), dimension 2 only. Their landscape is public and a thinned sample of up to 600 evaluated points per run is kept for the replay. |
| RW-001 to RW-003 | Real-world packs: exam timetabling, bus-stop location, delivery routing. See below. |

A submission is never run on a base function directly. Each instance is generated from
an instance seed (together with the problem and the dimension):

```
f_inst(x) = f_base(R (x - x*) + z_opt)
```

- `R` is a random rotation: the Q factor of a seeded Gaussian matrix, sign-corrected.
- `x*` is a random point inside the box, at most 40% of the half-width from the centre
  (10% for TR problems).
- `z_opt` is the base function's own optimum location for the standard set, so the
  instance optimum is exactly `x*`, inside the box. For TR problems, whose optima are
  not known in closed form, `z_opt = 0` and the transformation is a plain shift and
  rotation of the landscape.

Schwefel's formula is only valid on `[-500, 500]`; outside that range the clipped
point is evaluated and a quadratic penalty is added. Variable scaling is not applied.

## Real-world packs

The three packs use a random-key encoding: the search box is `[0, 1]^dim` and a decoder
turns the vector into a solution, so any continuous optimizer can be used unchanged.
There is no shift or rotation; the instance seed generates the data, and the data of
the public instances is shown on the problem page.

| Problem | Vector | Decoder | Objective (minimised) |
|---|---|---|---|
| RW-001 Exam timetabling | One key per course (dim = courses: 10, 20, 30) | `slot = floor(key x slots)`; within a slot the largest exam gets the largest room | Students with two exams in one slot plus students without a seat, per 100 enrolments |
| RW-002 Bus-stop location | Two keys per stop (dim = 2 x stops: 6, 10, 20) | Keys are the stop's map coordinates | Demand-weighted mean distance from a demand point to its nearest stop |
| RW-003 Delivery routing | One key per customer (dim = customers: 10, 20, 30) | Sorting the keys gives the visiting order; a vehicle returns to the depot when the next delivery would exceed its capacity | Total distance driven |

Their optima are not known, so `f_ref` is the best value found so far, as for the TR
problems. The decoded best solution of every run is stored and drawn on the submission
page (timetable grid, map with stops, map with routes).

## Budget, runs and trace

- Default budget: `2000 x dim` evaluations. Default dimensions: 5, 10, 20.
- One run = one submission on one instance with one seed. By default a submission is
  run with 5 seeds on each of 3 instances (15 runs).
- For every run the judge stores the best value found so far at up to 64 checkpoints,
  log-spaced in evaluation count from 1 to the budget. A run that stops early keeps
  its last best value for the remaining checkpoints.

## Scoring

Each (problem, instance, dimension) has a reference value `f_ref`: the exact optimum
for the standard set, and the best value known so far for TR problems (initialised by
`scripts/compute_f_ref.py` from CMA-ES with restarts and differential evolution at ten
times the default budget).

For a run with best-so-far values `b_k` at checkpoints `c_k`:

```
p_k   = clip(b_k - f_ref, 1e-8, 1e2)                 precision
v_k   = (2 - log10(p_k)) / 10                         in [0, 1]
AOCC  = sum_k v_k * (c_{k+1} - c_k) / budget          (c_{K+1} = budget + 1)
```

AOCC is the area over the convergence curve on a log precision scale, averaged over
the evaluation axis. It rewards both the final quality and how early it was reached.
A trace that is nowhere worse never scores lower, and a value below `f_ref` scores the
maximum.

Aggregation for a submission on a problem and dimension:

```
per instance : median of AOCC over seeds
aggregate    : mean over instances
score        = round(1000 * aggregate)
```

Also reported: the median final precision `max(f_best - f_ref, 1e-8)` over successful
runs, and the interquartile range of AOCC across seeds (averaged over instances) as a
robustness measure.

A run that fails (exception, timeout, crash, memory limit) scores 0.

When a run finds a value below the stored `f_ref` of its instance, `f_ref` is lowered to
that value and every submission on the same problem and dimension is re-scored from its
stored traces.

## Rate limits

Per user and problem: a cooldown between submissions (default 30 s) and a daily cap
(default 20, counted per UTC day). Both are configurable. The submission page shows
the remaining quota.

## Baselines

Three baselines are ordinary submissions in `backend/judge/baselines/` and are judged
exactly like user code:

| Baseline | Notes |
|---|---|
| Random search | Uniform samples in the box. |
| Differential evolution | SciPy `differential_evolution` with default parameters, evaluated one generation per call. |
| CMA-ES | Pure NumPy implementation with restarts that double the population. |

## Throughput

Measured on the development machine (Windows 11, Docker Desktop on WSL2), 20
dimensions, 40,000 evaluations:

| Pattern | Evaluations per second |
|---|---|
| Batches of 50 points | about 25,600 |
| One point per call | about 1,000 |

Container start and stop adds about 0.6 s per run. The CMA-ES and differential
evolution baselines finish a 40,000-evaluation run in 2 to 4 s. One-point-per-call code
takes about 40 s for the same run, so batching matters.

## Running it locally

```bash
sh scripts/build_sandbox.sh
python scripts/run_local.py my_optimizer.py --problem STD-004 --dim 10
python scripts/run_local.py --baseline cmaes --problem TR-003
```
