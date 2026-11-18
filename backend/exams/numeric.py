"""Parameterised numeric questions. Every student gets their own parameters from
seed = hash(test, student, question); the correct answer is computed here, never by
a language model."""

import hashlib
import math
import re
from collections.abc import Callable
from typing import Any

import numpy as np

from judge.functions import Fn, ackley, rastrigin, rosenbrock, sphere


def personal_seed(test_id: int, student_id: int, question_id: int) -> int:
    digest = hashlib.sha256(f"{test_id}:{student_id}:{question_id}".encode()).digest()
    return int.from_bytes(digest[:8], "little")


# the judge's own (vectorised) functions, without shift or rotation
FUNCTIONS: dict[str, Fn] = {
    "sphere": sphere, "rastrigin": rastrigin, "rosenbrock": rosenbrock, "ackley": ackley}


def _evaluate(rng: np.random.Generator) -> tuple[dict[str, Any], float]:
    name = str(rng.choice(sorted(FUNCTIONS)))
    dim = int(rng.integers(2, 5))
    x = rng.integers(-3, 4, dim).astype(float) / 2
    return {"function": name, "dim": dim, "point": x.tolist()}, float(FUNCTIONS[name](x[None])[0])


def _precision(rng: np.random.Generator) -> tuple[dict[str, Any], float]:
    f_ref = round(float(rng.uniform(-50, 50)), 2)
    gap = 10.0 ** float(rng.integers(-6, 3))
    f_best = round(f_ref + gap * float(rng.uniform(1, 9)), 8)
    return {"f_best": f_best, "f_ref": f_ref}, math.log10(f_best - f_ref)


def _improvement(rng: np.random.Generator) -> tuple[dict[str, Any], float]:
    start = round(float(rng.uniform(50, 500)), 1)
    end = round(start * float(rng.uniform(0.05, 0.9)), 1)
    return {"start": start, "end": end}, 100 * (start - end) / start


# kind -> (parameter generator, default question text with {placeholders})
GENERATORS: dict[str, tuple[Callable[[np.random.Generator], tuple[dict[str, Any], float]], str]] = {
    "evaluate": (_evaluate, "Evaluate the {function} function at x = {point} (dimension "
                            "{dim}). Give the value to at least four significant digits."),
    "precision": (_precision, "A run's best value is {f_best} and the reference value is "
                              "{f_ref}. What is log10 of the precision (f_best - f_ref)?"),
    "improvement": (_improvement, "The best value fell from {start} to {end}. By what "
                                  "percentage did it improve?"),
}


def instance(kind: str, seed: int) -> tuple[dict[str, Any], float]:
    """The student's parameters and the correct answer."""
    return GENERATORS[kind][0](np.random.default_rng(seed))


def expected(generator: str, test_id: int, student_id: int, question_id: int
             ) -> tuple[dict[str, Any], float]:
    """One student's parameters and correct answer for a numeric question."""
    return instance(generator, personal_seed(test_id, student_id, question_id))


PLACEHOLDER = re.compile(r"\{(\w+)\}")


def fill(text: str, values: dict[str, Any]) -> str | None:
    """Replaces {name} placeholders; None if the text uses a name that is not given.
    Only plain names are allowed (no attribute or index access as in str.format)."""
    if any(name not in values for name in PLACEHOLDER.findall(text)):
        return None
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), text)


def is_correct(given: float, expected: float, rel_tol: float = 1e-3) -> bool:
    return math.isclose(given, expected, rel_tol=rel_tol, abs_tol=1e-6)
