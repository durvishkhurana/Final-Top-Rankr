"""Statistical comparison of judged submissions on one problem and dimension."""

import json
import re
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ai import llm
from ai.features import WriteUp
from db.models import Submission
from db.results import precision_trace, ref_lookup
from judge.scoring import checkpoints
from research import export, stats

from ..deps import CurrentUser, Session
from ..export import Format, table
from ..schemas import ComparedEntry, Comparison, PairTest, WriteUpOut
from .ai import guarded
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
    return await _compare(session, problem_id, dim, ids)


async def _compare(session: AsyncSession, problem_id: str, dim: int, ids: list[int]
                   ) -> Comparison:
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


@router.get("/latex")
async def export_latex(problem_id: str, dim: int, ids: Ids, session: Session) -> Response:
    """The summary table as a LaTeX (booktabs) table."""
    data = await _compare(session, problem_id, dim, ids)
    return Response(export.to_latex(problem_id, dim, [e.model_dump() for e in data.entries]),
                    media_type="application/x-tex", headers={
                        "Content-Disposition": f'attachment; filename="{problem_id}-d{dim}.tex"'})


@router.get("/ioh")
async def export_ioh(problem_id: str, dim: int, ids: Ids, session: Session) -> Response:
    """Every run in the IOHprofiler format, as a zip IOHanalyzer can load."""
    subs = await _load(session, problem_id, dim, ids)
    ref = await ref_lookup(session, problem_id, dim)
    data = export.to_ioh(problem_id, dim, subs[0].budget or 0, [
        (s.user.name, [(r.instance_seed, r.evals, precision_trace(r, ref(r.instance_seed)))
                       for r in s.runs]) for s in subs])
    return Response(data, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{problem_id}-d{dim}-ioh.zip"'})


def _effect(a12: float) -> str:
    size = abs(a12 - 0.5)
    return ("large" if size >= 0.21 else "medium" if size >= 0.14
            else "small" if size >= 0.06 else "negligible")


def writeup_facts(data: Comparison) -> dict[str, object]:
    """Verdicts only, entries by letter: the model gets no numbers to repeat or alter."""
    letter = {e.submission_id: chr(65 + i) for i, e in enumerate(data.entries)}
    order = sorted(data.entries, key=lambda e: -e.mean)
    return {
        "entries": {letter[e.submission_id]: "baseline" if e.is_baseline else "participant"
                    for e in data.entries},
        "order_by_mean_aocc_best_first": [letter[e.submission_id] for e in order],
        "all_alike_test": None if data.friedman_p is None else
        ("at least one entry differs" if data.friedman_p < data.alpha
         else "no significant difference among the entries"),
        "pairs": [{"pair": f"{letter[p.a]} vs {letter[p.b]}",
                   "verdict": f"{letter[p.better]} is significantly better" if p.better
                   else "no significant difference",
                   "effect_size": _effect(p.a12)} for p in data.pairs],
    }


@router.post("/writeup", response_model=WriteUpOut)
async def writeup(problem_id: str, dim: int, ids: Ids, user: CurrentUser, session: Session
                  ) -> WriteUpOut:
    """A results paragraph written by the model from the verdicts. Numbers stay in the
    tables: sentences holding a digit are dropped, and letters are replaced by names here."""
    data = await _compare(session, problem_id, dim, ids)
    answer: WriteUp = await guarded(lambda: llm.ask(
        session, feature="writeup", user_id=user.id, schema=WriteUp, prefer="gemini",
        prompt=llm.render("writeup.v1", problem=f"{problem_id} in dimension {dim}",
                          facts=json.dumps(writeup_facts(data), indent=1))))
    # cached answers repeat, so a sentence with a number is dropped rather than retried
    text = " ".join(s for s in re.split(r"(?<=[.!?])[ 	]+", answer.text)
                    if not any(c.isdigit() for c in s)).strip()
    if not text:
        raise HTTPException(502, "The write-up contained numbers only and was discarded")
    for i, e in enumerate(data.entries):
        text = text.replace(f"[{chr(65 + i)}]", e.label)
    return WriteUpOut(text=text)
