"""Answer schemas of the AI features and the code-computed facts they are given."""

from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field

from db.models import Run, Submission
from judge.scoring import P_MIN, checkpoints


class Analysis(BaseModel):
    family: str = Field(description="Closest well-known algorithm family, e.g. "
                                    "'differential evolution', 'random search', 'CMA-ES'")
    population_based: bool
    mutation: str = Field(description="How new points are perturbed, or 'none'")
    crossover: str = Field(description="How information from points is combined, or 'none'")
    selection: str = Field(description="How points are kept or discarded, or 'none'")
    restarts: str = Field(description="Restart or diversity mechanism, or 'none'")
    local_search: str = Field(description="Local refinement step, or 'none'")
    summary: str = Field(description="Two or three sentences on what the code really does")


class Coach(BaseModel):
    diagnosis: str = Field(description="What happened in the runs and why, in plain language")
    suggestion: str = Field(description="Exactly one suggested change, in words")


class BaselineCode(BaseModel):
    approach: str = Field(description="One sentence naming the approach")
    code: str = Field(description="Complete Python source defining optimize(...)")


class ChallengerCode(BaseModel):
    approach: str = Field(description="One sentence naming the approach")
    changes: str = Field(description="What changed from the previous version and why, "
                                     "in one to three sentences")
    code: str = Field(description="Complete Python source defining optimize(...)")


class BuiltProblem(BaseModel):
    name: str = Field(max_length=100)
    summary: str = Field(max_length=300)
    description: str
    source: str
    lower: float
    upper: float
    dims: list[int] = Field(min_length=1, max_length=3)
    level: Literal["Easy", "Medium", "Hard"]
    tags: list[str] = Field(max_length=4)


class Distractors(BaseModel):
    distractors: list[str] = Field(min_length=1, max_length=6)


class Phrasings(BaseModel):
    phrasings: list[str] = Field(min_length=1, max_length=30)


class FollowUp(BaseModel):
    question: str = Field(max_length=500)


class Grade(BaseModel):
    level: float = Field(ge=0, le=1, description="Fraction of full marks, 0 to 1")
    rationale: str = Field(description="One or two sentences, referring to the rubric")
    confidence: float = Field(ge=0, le=1)
    contradiction: bool = Field(description="True if the answers contradict the code or "
                                            "the run facts, or each other")
    contradiction_note: str = Field(default="", description="What contradicts what")


class Viva(BaseModel):
    questions: list[str] = Field(min_length=3, max_length=3)


class SimilarityOpinion(BaseModel):
    verdict: Literal["likely shared", "possibly shared", "probably independent"]
    reasons: str


def run_stats(sub: Submission, runs: list[Run]) -> dict[str, Any]:
    """Convergence facts for the coach. Everything is relative precision; no raw
    objective values, instance parameters or reference values are included."""
    assert sub.budget is not None
    budget = sub.budget
    points = np.array(checkpoints(budget))
    ok = [r for r in runs if r.status == "ok" and r.precision is not None]

    def at(fraction: float, r: Run) -> float | None:
        k = int(np.searchsorted(points, fraction * budget, side="right")) - 1
        v, last = r.trace[max(k, 0)], r.trace[-1]
        if v is None or last is None or r.precision is None:
            return None
        # stored traces are raw values; shift them so the final one equals the run's precision
        return float(max(v - last + r.precision, P_MIN))

    def last_improvement(r: Run) -> float:
        trace = np.array([np.inf if v is None else v for v in r.trace])
        changed = np.flatnonzero(np.diff(trace) < 0)
        return float(points[changed[-1] + 1] / budget) if len(changed) else 0.0

    def median(values: list[float | None]) -> float | None:
        kept = [v for v in values if v is not None]
        return float(np.median(kept)) if kept else None

    return {
        "budget_per_run": sub.budget,
        "runs": len(runs),
        "failed_runs": len(runs) - len(ok),
        "first_error": next((r.error.strip().splitlines()[-1] for r in runs if r.error), None),
        "median_evaluations_used": median([float(r.evals) for r in ok]),
        "median_precision_after_10_percent_of_budget": median([at(0.1, r) for r in ok]),
        "median_precision_after_50_percent_of_budget": median([at(0.5, r) for r in ok]),
        "median_final_precision": median([r.precision for r in ok]),
        "best_final_precision": min((r.precision for r in ok if r.precision is not None),
                                    default=None),
        "worst_final_precision": max((r.precision for r in ok if r.precision is not None),
                                     default=None),
        "median_fraction_of_budget_at_last_improvement": median(
            [last_improvement(r) for r in ok]),
        "score_out_of_1000": sub.score,
    }
