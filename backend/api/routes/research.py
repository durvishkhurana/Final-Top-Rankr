"""Statistical comparison of judged submissions on one problem and dimension."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Submission
from db.results import precision_trace, ref_lookup
from judge.scoring import checkpoints
from research import stats

from ..deps import Session
from ..export import Format, table
from ..schemas import ComparedEntry, Comparison, PairTest
from .submissions import run_rows

router = APIRouter(prefix="/research", tags=["research"])

Ids = Annotated[list[int], Query(min_length=2, max_length=8)]


async def _load(session: AsyncSession, problem_id: str, dim: int, ids: list[int]
                ) -> list[Submission]:
    subs = list((await session.scalars(
        select(Submission).options(selectinload(Submission.runs))
        .where(Submission.id.in_(ids), Submission.problem_id == problem_id,
               Submission.dim == dim, Submission.status == "done"))).unique())
    if len(subs) != len(set(ids)):
        raise HTTPException(422, "Every submission must be judged and on this problem and "
                                 "dimension")
    return sorted(subs, key=lambda s: ids.index(s.id))


@router.get("/compare", response_model=Comparison)
async def compare(problem_id: str, dim: int, ids: Ids, session: Session) -> Comparison:
    subs = await _load(session, problem_id, dim, ids)
    ref = await ref_lookup(session, problem_id, dim)
    result = stats.compare({s.id: {(r.instance_seed, r.seed): r.aocc for r in s.runs}
                            for s in subs})
    entries = [ComparedEntry(
        submission_id=s.id, label=s.user.name, is_baseline=s.user.is_bot, score=s.score or 0,
        **result["summary"][s.id],
        ecdf=stats.ecdf([precision_trace(r, ref(r.instance_seed)) for r in s.runs]))
        for s in subs]
    return Comparison(problem_id=problem_id, dim=dim, targets=stats.TARGETS,
                      checkpoints=checkpoints(subs[0].budget or 0), entries=entries,
                      pairs=[PairTest(**p) for p in result["pairs"]], blocks=result["blocks"],
                      friedman_p=result["friedman_p"], alpha=result["alpha"])


@router.get("/runs")
async def export_runs(problem_id: str, dim: int, ids: Ids, session: Session,
                      format: Format = "csv") -> Response:
    """All runs of the compared submissions in one long table, one row per run."""
    subs = await _load(session, problem_id, dim, ids)
    ref = await ref_lookup(session, problem_id, dim)
    columns: list[str] = []
    rows = []
    for s in subs:
        columns, runs = run_rows(s, ref)
        rows += [{"submission_id": s.id, "name": s.user.name, "is_baseline": s.user.is_bot,
                  **r} for r in runs]
    return table(["submission_id", "name", "is_baseline", *columns], rows,
                 f"{problem_id}-d{dim}-runs", format)
