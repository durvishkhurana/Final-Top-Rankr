from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from db.models import Problem, Submission
from judge import templates

from ..deps import CurrentUser, Session
from ..schemas import BoardRow, ProblemDetail, ProblemOut, Quota, Template

router = APIRouter(tags=["problems"])


async def quota_for(session: AsyncSession, user_id: int, problem_id: str) -> Quota:
    s = get_settings()
    now = datetime.now(UTC)
    mine = (Submission.user_id == user_id) & (Submission.problem_id == problem_id)
    used = await session.scalar(
        select(func.count()).select_from(Submission)
        .where(mine, Submission.created_at >= now.replace(hour=0, minute=0, second=0,
                                                          microsecond=0))) or 0
    last = await session.scalar(select(func.max(Submission.created_at)).where(mine))
    wait = max(0, s.submit_cooldown_sec - int((now - last).total_seconds())) if last else 0
    return Quota(daily_cap=s.submit_daily_cap, used_today=used,
                 remaining_today=max(0, s.submit_daily_cap - used),
                 cooldown_sec=s.submit_cooldown_sec, wait_sec=wait)


@router.get("/problems", response_model=list[ProblemOut])
async def list_problems(session: Session) -> list[ProblemOut]:
    counts = dict((await session.execute(
        select(Submission.problem_id, func.count()).group_by(Submission.problem_id))).all())
    problems = await session.scalars(
        select(Problem).where(Problem.is_active).order_by(Problem.category.desc(), Problem.id))
    out = []
    for p in problems:
        item = ProblemOut.model_validate(p)
        item.submissions = counts.get(p.id, 0)
        out.append(item)
    return out


async def _problem(session: AsyncSession, problem_id: str) -> Problem:
    problem = await session.get(Problem, problem_id)
    if problem is None or not problem.is_active:
        raise HTTPException(404, "Problem not found")
    return problem


@router.get("/problems/{problem_id}", response_model=ProblemDetail)
async def get_problem(problem_id: str, session: Session) -> Problem:
    return await _problem(session, problem_id)


@router.get("/problems/{problem_id}/quota", response_model=Quota)
async def get_quota(problem_id: str, user: CurrentUser, session: Session) -> Quota:
    return await quota_for(session, user.id, problem_id)


@router.get("/problems/{problem_id}/leaderboard", response_model=list[BoardRow])
async def leaderboard(problem_id: str, dim: int, session: Session) -> list[BoardRow]:
    """Each user's best submission on this problem and dimension. Baselines are included
    and flagged."""
    await _problem(session, problem_id)
    best = await session.scalars(
        select(Submission)
        .where(Submission.problem_id == problem_id, Submission.dim == dim,
               Submission.status == "done")
        .ext(distinct_on(Submission.user_id))
        .order_by(Submission.user_id, Submission.score.desc(), Submission.created_at))
    ranked = sorted(best.unique(), key=lambda s: (-(s.score or 0), s.created_at))
    return [
        BoardRow(rank=i, user_id=s.user_id, name=s.user.name, country=s.user.country,
                 institution=s.user.institution, is_baseline=s.user.is_bot, submission_id=s.id,
                 score=s.score or 0, median_precision=s.median_precision, iqr=s.iqr,
                 submitted_at=s.created_at)
        for i, s in enumerate(ranked, start=1)
    ]


@router.get("/templates", response_model=list[Template])
async def list_templates() -> list[Template]:
    return [Template(key=key, name=name, code=templates.source(key))
            for key, name in templates.TEMPLATES.items()]
