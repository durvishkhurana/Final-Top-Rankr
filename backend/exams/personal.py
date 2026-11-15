"""Facts about a student's own judged submission, used to personalise reasoning
questions. All values are computed by the judge and are relative (precision, share of
budget); nothing about the hidden instance is included."""

from ai.features import run_stats
from db.models import Run, Submission

FACTS = ("budget", "evaluations_used", "last_improvement_evals", "final_precision",
         "best_precision", "failed_runs", "runs", "score")


def facts(sub: Submission, runs: list[Run]) -> dict[str, str]:
    assert sub.budget is not None
    st = run_stats(sub, runs)

    def evals(value: float | None) -> str:
        return f"{round(value):,}" if value is not None else "unknown"

    def prec(value: float | None) -> str:
        return f"{value:.1e}" if value is not None else "not reached"

    frac = st["median_fraction_of_budget_at_last_improvement"]
    return {
        "budget": f"{sub.budget:,}",
        "evaluations_used": evals(st["median_evaluations_used"]),
        "last_improvement_evals": evals(frac * sub.budget if frac is not None else None),
        "final_precision": prec(st["median_final_precision"]),
        "best_precision": prec(st["best_final_precision"]),
        "failed_runs": str(st["failed_runs"]),
        "runs": str(st["runs"]),
        "score": f"{sub.score:.0f}" if sub.score is not None else "none",
    }
