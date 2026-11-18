from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import get_settings
from db.models import Contest, Problem, Submission
from db.results import precision_trace, ref_lookup
from judge.scoring import checkpoints

from ..deps import CurrentUser, Enqueue, OptionalUser, Session, VerifiedUser
from ..export import Format, table
from ..schemas import RunDetail, SubmissionDetail, SubmissionOut, SubmitIn
from .contests import is_participant, phase
from .problems import quota_for

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _out(sub: Submission) -> SubmissionOut:
    return SubmissionOut.model_validate({**sub.__dict__, "user_name": sub.user.name})


@router.post("", response_model=SubmissionOut, status_code=201)
async def submit(body: SubmitIn, user: VerifiedUser, session: Session, enqueue: Enqueue
                 ) -> SubmissionOut:
    problem = await session.get(Problem, body.problem_id)
    if problem is None or not problem.is_active:
        raise HTTPException(404, "Problem not found")
    if body.dim not in problem.dims:
        raise HTTPException(422, f"Dimension must be one of {problem.dims}")
    if len(body.code.encode()) > get_settings().max_code_bytes:
        raise HTTPException(413, "The submission is too large")
    quota = await quota_for(session, user.id, problem.id)
    if quota.remaining_today <= 0:
        raise HTTPException(429, "Daily submission limit reached for this problem")
    if quota.wait_sec > 0:
        raise HTTPException(429, f"Wait {quota.wait_sec}s before submitting to this problem again",
                            headers={"Retry-After": str(quota.wait_sec)})

    if body.contest_id is not None:
        contest = await session.get(Contest, body.contest_id)
        if contest is None or not await is_participant(session, body.contest_id, user.id):
            raise HTTPException(403, "Join the contest before submitting to it")
        if phase(contest) != "running":
            raise HTTPException(409, "This contest is not accepting submissions")
        if {"problem_id": problem.id, "dim": body.dim} not in contest.tasks:
            raise HTTPException(422, "This problem and dimension are not part of the contest")

    sub = Submission(user_id=user.id, problem_id=problem.id, dim=body.dim, code=body.code,
                     contest_id=body.contest_id)
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    await enqueue("judge_submission", sub.id)
    return _out(sub)


@router.get("", response_model=list[SubmissionOut])
async def my_submissions(user: CurrentUser, session: Session, problem_id: str | None = None
                         ) -> list[SubmissionOut]:
    query = select(Submission).where(Submission.user_id == user.id)
    if problem_id:
        query = query.where(Submission.problem_id == problem_id)
    subs = await session.scalars(query.order_by(Submission.created_at.desc()).limit(100))
    return [_out(s) for s in subs.unique()]


async def with_runs(session: AsyncSession, submission_id: int) -> Submission:
    sub = await session.scalar(select(Submission).options(selectinload(Submission.runs))
                               .where(Submission.id == submission_id))
    if sub is None:
        raise HTTPException(404, "Submission not found")
    return sub


RUN_COLUMNS = ["instance_seed", "seed", "status", "evals", "aocc", "precision", "wall_sec"]


def run_rows(sub: Submission, ref: Callable[[int], float | None]
             ) -> tuple[list[str], list[dict[str, Any]]]:
    """One flat row per run, with the precision at every checkpoint (public data only)."""
    points = checkpoints(sub.budget) if sub.budget else []
    trace_columns = [f"precision_at_{c}" for c in points]
    rows = [{**{c: getattr(r, c) for c in RUN_COLUMNS},
             **dict(zip(trace_columns, precision_trace(r, ref(r.instance_seed)), strict=True))}
            for r in sub.runs]
    return RUN_COLUMNS + trace_columns, rows


@router.get("/{submission_id}/export")
async def export_runs(submission_id: int, session: Session, format: Format = "csv"
                      ) -> Response:
    """Every run of a submission with its convergence, for analysis elsewhere."""
    sub = await with_runs(session, submission_id)
    columns, rows = run_rows(sub, await ref_lookup(session, sub.problem_id, sub.dim))
    return table(columns, rows, f"submission-{sub.id}-runs", format)


@router.get("/{submission_id}", response_model=SubmissionDetail)
async def get_submission(submission_id: int, viewer: OptionalUser, session: Session
                         ) -> SubmissionDetail:
    """Scores and convergence are public. Code and logs are shown only to the author
    and to admins."""
    sub = await with_runs(session, submission_id)
    private = viewer is not None and (viewer.id == sub.user_id or viewer.role == "admin")
    ref = await ref_lookup(session, sub.problem_id, sub.dim)
    runs = [RunDetail.model_validate(
        {**r.__dict__, "precision_trace": precision_trace(r, ref(r.instance_seed)),
         "log": r.log if private else "", "error": r.error if private else ""})
        for r in sub.runs]
    return SubmissionDetail.model_validate(
        {**_out(sub).model_dump(), "code": sub.code if private else "",
         "error": sub.error if private else "",
         "checkpoints": checkpoints(sub.budget) if sub.budget else [], "runs": runs})
