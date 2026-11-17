# Adding a problem

This page covers built-in problems, which are code in the repository. Users can also
propose a function from the web app (`/contribute`), written by hand or drafted by the
AI problem builder; it is smoke-tested in a sandbox and approved by an admin before it
joins the catalogue as `C-NNN`. See [AI_FEATURES.md](AI_FEATURES.md#contributed-problems).

## A hidden function

1. Add a vectorised function to `backend/judge/functions.py`. It receives an array of
   shape `(n, D)` and returns `n` values, and must work for every `D >= 2` it is offered at.
2. Register it in `PROBLEMS` with an id, a name and the half-width of its search box.
   If its optimum location is known in closed form, give it as `z_opt` (the value of
   every coordinate at the optimum); the judge then uses the exact optimum value.
   Otherwise leave `z_opt` unset and run `scripts/compute_f_ref.py --problems <id>` to
   produce best-known values.
3. Add the public entry to `problems/catalogue.json`: name, category, level, tags, a
   one-line summary and a description in plain language. Describe behaviour, not the
   formula.
4. Add tests (see `backend/tests/test_functions.py`) and run `scripts/seed.py`.

Set `dims=(2,)` and `kind="landscape2d"` for a two-variable demo whose landscape may be
shown.

## A real-world pack

Real-world problems live in `backend/judge/realworld.py`. Each is a subclass of
`RealInstance` built by a factory `(problem, dim, seed)` and provides:

- `__call__(X)`: the objective for a batch of random-key vectors in `[0, 1]^dim`;
- `public()`: the instance data that may be shown (JSON);
- `decode(x)`: the human-readable solution for one vector (JSON).

Register the problem with `kind` set to a name the frontend can draw
(`frontend/components/solution-view.tsx`) and add the catalogue entry as above.
