"""Real-world problem packs. Each uses a random-key encoding: the optimizer searches
the unit box [0, 1]^D with any continuous method and a decoder turns the vector into a
timetable, a set of stops or a set of routes.

Unlike the hidden functions, the instance data (courses, demand points, customers) is
part of the problem statement and is public. There is no shift or rotation; the
instance seed generates the data.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np

from .functions import PROBLEMS, Array, Problem

MAP = 10.0  # maps are MAP x MAP


def _dist(a: Array, b: Array) -> Array:
    return np.sqrt(np.sum((a - b) ** 2, axis=-1))


def _clustered(rng: np.random.Generator, n: int, clusters: int) -> Array:
    centres = rng.uniform(1.5, MAP - 1.5, (clusters, 2))
    points = centres[rng.integers(clusters, size=n)] + rng.normal(0, 0.9, (n, 2))
    return np.clip(points, 0, MAP)


@dataclass(frozen=True)
class RealInstance:
    """Same interface as judge.instance.Instance, plus public data and a decoder."""

    problem: Problem
    dim: int
    lower: Array
    upper: Array
    f_opt = None  # unknown; best-known values come from reference runs

    def __call__(self, X: Array) -> Array:
        raise NotImplementedError

    def public(self) -> dict[str, Any]:
        raise NotImplementedError

    def decode(self, x: Array) -> dict[str, Any]:
        raise NotImplementedError


# --- Exam timetabling --------------------------------------------------------------------


@dataclass(frozen=True)
class Timetable(RealInstance):
    """One key per course picks its slot. Rooms are filled largest course first.
    Objective: students with a clash plus students without a seat, per 100 enrolments."""

    sizes: Array = None  # type: ignore[assignment]
    conflicts: Array = None  # type: ignore[assignment]  # students shared by each course pair
    capacities: Array = None  # type: ignore[assignment]  # sorted, largest room first
    n_slots: int = 0

    def _slots(self, X: Array) -> Array:
        return np.minimum((X * self.n_slots).astype(int), self.n_slots - 1)

    def _parts(self, X: Array) -> tuple[Array, Array]:
        onehot = np.eye(self.n_slots)[self._slots(X)]  # (n, courses, slots)
        clashes = 0.5 * np.einsum("nis,ij,njs->n", onehot, self.conflicts, onehot)
        # per slot: course sizes in descending order against rooms in descending order
        by_slot = np.sort(onehot * self.sizes[None, :, None], axis=1)[:, ::-1, :]
        rooms = np.zeros(self.dim)
        rooms[: len(self.capacities)] = self.capacities[: self.dim]
        unseated = np.sum(np.maximum(by_slot - rooms[None, :, None], 0), axis=(1, 2))
        return clashes, unseated

    def __call__(self, X: Array) -> Array:
        clashes, unseated = self._parts(X)
        return 100.0 * (clashes + unseated) / self.sizes.sum()

    def public(self) -> dict[str, Any]:
        return {"courses": [{"name": f"C{i + 1}", "students": int(s)}
                            for i, s in enumerate(self.sizes)],
                "rooms": [int(c) for c in self.capacities], "slots": self.n_slots,
                "clash_pairs": int(np.count_nonzero(np.triu(self.conflicts, 1)))}

    def decode(self, x: Array) -> dict[str, Any]:
        slots = self._slots(x[None, :])[0]
        clashes, unseated = self._parts(x[None, :])
        grid = []
        for s in range(self.n_slots):
            courses = sorted(np.flatnonzero(slots == s), key=lambda c: -self.sizes[c])
            grid.append([{"course": f"C{c + 1}", "students": int(self.sizes[c]),
                          "room": k + 1 if k < len(self.capacities) else None,
                          "capacity": int(self.capacities[k]) if k < len(self.capacities) else 0}
                         for k, c in enumerate(courses)])
        return {"slots": grid, "clashing_students": float(clashes[0]),
                "unseated_students": float(unseated[0])}


def timetable(problem: Problem, dim: int, seed: int) -> Timetable:
    rng = np.random.default_rng([seed, dim, 101])
    n_students = 12 * dim
    # each student takes 3 or 4 courses; popular courses are picked more often
    weight = rng.dirichlet(np.full(dim, 2.0))
    takes = np.zeros((n_students, dim))
    for row in takes:
        row[rng.choice(dim, size=rng.integers(3, 5), replace=False, p=weight)] = 1
    conflicts = takes.T @ takes
    np.fill_diagonal(conflicts, 0)
    sizes = takes.sum(axis=0)
    n_slots = max(4, dim // 3)
    n_rooms = int(np.ceil(dim / n_slots)) + 1
    capacities = np.sort(rng.integers(int(np.mean(sizes)), int(np.max(sizes)) + 5, n_rooms))[::-1]
    return Timetable(problem, dim, np.zeros(dim), np.ones(dim), sizes, conflicts,
                     capacities.astype(float), n_slots)


# --- Facility / bus-stop location --------------------------------------------------------


@dataclass(frozen=True)
class Facility(RealInstance):
    """Two keys per stop give its position. Objective: mean walking distance from a
    demand point to its nearest stop, weighted by demand."""

    demand: Array = None  # type: ignore[assignment]
    weights: Array = None  # type: ignore[assignment]

    def _stops(self, X: Array) -> Array:
        return X.reshape(len(X), -1, 2) * MAP

    def __call__(self, X: Array) -> Array:
        d = _dist(self.demand[None, :, None, :], self._stops(X)[:, None, :, :])
        return d.min(axis=2) @ self.weights / self.weights.sum()

    def public(self) -> dict[str, Any]:
        return {"size": MAP, "stops": self.dim // 2,
                "demand": [{"x": float(p[0]), "y": float(p[1]), "people": int(w)}
                           for p, w in zip(self.demand, self.weights, strict=True)]}

    def decode(self, x: Array) -> dict[str, Any]:
        stops = self._stops(x[None, :])[0]
        nearest = _dist(self.demand[:, None, :], stops[None, :, :]).argmin(axis=1)
        return {"stops": [{"x": float(s[0]), "y": float(s[1]),
                           "people": int(self.weights[nearest == k].sum())}
                          for k, s in enumerate(stops)],
                "assigned": [int(k) for k in nearest],
                "mean_distance": float(self(x[None, :])[0])}


def facility(problem: Problem, dim: int, seed: int) -> Facility:
    rng = np.random.default_rng([seed, dim, 202])
    demand = _clustered(rng, 60, clusters=dim // 2 + 2)
    return Facility(problem, dim, np.zeros(dim), np.ones(dim), demand,
                    rng.integers(5, 60, len(demand)).astype(float))


# --- Delivery routing --------------------------------------------------------------------


@dataclass(frozen=True)
class Routing(RealInstance):
    """One key per customer; sorting the keys gives the visiting order. A vehicle
    returns to the depot when the next customer would exceed its capacity.
    Objective: total distance driven."""

    customers: Array = None  # type: ignore[assignment]
    demands: Array = None  # type: ignore[assignment]
    depot: Array = None  # type: ignore[assignment]
    capacity: float = 0.0

    def __call__(self, X: Array) -> Array:
        order = np.argsort(X, axis=1)
        n = len(X)
        pos = np.tile(self.depot, (n, 1))
        load, total = np.zeros(n), np.zeros(n)
        for j in range(self.dim):  # vectorised over the batch, one stop at a time
            c = order[:, j]
            here, need = self.customers[c], self.demands[c]
            full = load + need > self.capacity
            total += np.where(full, _dist(pos, self.depot) + _dist(self.depot, here),
                              _dist(pos, here))
            load = np.where(full, need, load + need)
            pos = here
        return total + _dist(pos, self.depot)

    def public(self) -> dict[str, Any]:
        return {"size": MAP, "capacity": self.capacity,
                "depot": {"x": float(self.depot[0]), "y": float(self.depot[1])},
                "customers": [{"x": float(p[0]), "y": float(p[1]), "demand": int(d)}
                              for p, d in zip(self.customers, self.demands, strict=True)]}

    def decode(self, x: Array) -> dict[str, Any]:
        routes: list[list[int]] = [[]]
        load = 0.0
        for c in np.argsort(x):
            if load + self.demands[c] > self.capacity:
                routes.append([])
                load = 0.0
            routes[-1].append(int(c))
            load += self.demands[c]
        return {"routes": [{"customers": r, "load": float(self.demands[r].sum())}
                           for r in routes],
                "total_distance": float(self(x[None, :])[0])}


def _zero(X: Array) -> Array:  # real-world problems have no base function
    return np.zeros(len(X))


PROBLEMS.update({
    "RW-001": Problem("RW-001", "Exam timetabling", _zero, 1.0, dims=(10, 20, 30),
                      kind="timetable", factory=timetable),
    "RW-002": Problem("RW-002", "Bus-stop location", _zero, 1.0, dims=(6, 10, 20),
                      kind="facility", factory=facility),
})


def routing(problem: Problem, dim: int, seed: int) -> Routing:
    rng = np.random.default_rng([seed, dim, 303])
    demands = rng.integers(1, 10, dim).astype(float)
    return Routing(problem, dim, np.zeros(dim), np.ones(dim), _clustered(rng, dim, 4), demands,
                   np.array([MAP / 2, MAP / 2]), capacity=float(np.ceil(demands.sum() / 4) + 4))


PROBLEMS["RW-003"] = Problem("RW-003", "Delivery routing", _zero, 1.0, dims=(10, 20, 30),
                             kind="routing", factory=routing)
