from datetime import UTC, datetime

import numpy as np
from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from db.models import Problem, Run, Submission
from db.results import ref_lookup
from judge import templates
from judge.evaluate import PUBLIC_INSTANCE_SEEDS
from judge.functions import PROBLEMS
from judge.instance import make_instance
from judge.scoring import checkpoints, precision

from ..deps import CurrentUser, Session
from ..export import Format, table
from ..schemas import (
    BoardRow,
    Curve,
    Curves,
    ProblemDetail,
    ProblemOut,
    ProblemView,
    Quota,
    Template,
)

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


async def best_submissions(session: AsyncSession, problem_id: str, dim: int) -> list[Submission]:
    """Each user's best scored submission, best first."""
    best = await session.scalars(
        select(Submission)
        .where(Submission.problem_id == problem_id, Submission.dim == dim,
               Submission.status == "done")
        .ext(distinct_on(Submission.user_id))
        .order_by(Submission.user_id, Submission.score.desc(), Submission.created_at))
    return sorted(best.unique(), key=lambda s: (-(s.score or 0), s.created_at))


@router.get("/problems/{problem_id}/curves", response_model=Curves)
async def curves(problem_id: str, dim: int, session: Session) -> Curves:
    """Median convergence of the top three entries and of every baseline, for overlays."""
    await _problem(session, problem_id)
    ranked = await best_submissions(session, problem_id, dim)
    chosen = [s for s in ranked if not s.user.is_bot][:3] + [s for s in ranked if s.user.is_bot]
    ref = await ref_lookup(session, problem_id, dim)
    out = []
    for sub in chosen:
        runs = await session.scalars(select(Run).where(Run.submission_id == sub.id,
                                                       Run.status == "ok"))
        traces = [[precision(v, f_ref) for v in r.trace] for r in runs
                  if (f_ref := ref(r.instance_seed)) is not None and None not in r.trace]
        median = [float(m) for m in np.median(traces, axis=0)] if traces else []
        out.append(Curve(label=sub.user.name, is_baseline=sub.user.is_bot,
                         submission_id=sub.id, median=median))
    budget = chosen[0].budget if chosen else None
    return Curves(checkpoints=checkpoints(budget) if budget else [], curves=out)


GRID = 70


@router.get("/problems/{problem_id}/view", response_model=ProblemView)
async def view(problem_id: str, dim: int, session: Session, instance_seed: int = 1
               ) -> ProblemView:
    problem = await _problem(session, problem_id)
    spec = PROBLEMS[problem_id]
    if (spec.kind == "function" or dim not in problem.dims
            or instance_seed not in PUBLIC_INSTANCE_SEEDS):
        raise HTTPException(404, "Nothing to show for this problem")
    inst = make_instance(spec, dim, instance_seed)
    out = ProblemView(kind=spec.kind, lower=inst.lower.tolist(), upper=inst.upper.tolist())
    if spec.kind == "landscape2d":
        xs = np.linspace(inst.lower[0], inst.upper[0], GRID)
        ys = np.linspace(inst.lower[1], inst.upper[1], GRID)
        mesh = np.stack(np.meshgrid(xs, ys), axis=-1).reshape(-1, 2)
        out.grid = (inst(mesh) - inst.f_opt).reshape(GRID, GRID).tolist()
    else:
        out.data = inst.public()
    return out


@router.get("/problems/{problem_id}/leaderboard", response_model=list[BoardRow])
async def leaderboard(problem_id: str, dim: int, session: Session) -> list[BoardRow]:
    """Each user's best submission on this problem and dimension. Baselines are included
    and flagged."""
    await _problem(session, problem_id)
    ranked = await best_submissions(session, problem_id, dim)
    return [
        BoardRow(rank=i, user_id=s.user_id, name=s.user.name, country=s.user.country,
                 institution=s.user.institution, is_baseline=s.user.is_bot, submission_id=s.id,
                 score=s.score or 0, median_precision=s.median_precision, iqr=s.iqr,
                 submitted_at=s.created_at)
        for i, s in enumerate(ranked, start=1)
    ]


@router.get("/problems/{problem_id}/leaderboard/export")
async def export_leaderboard(problem_id: str, dim: int, session: Session,
                             format: Format = "csv") -> Response:
    rows = [r.model_dump(mode="json") for r in await leaderboard(problem_id, dim, session)]
    return table(list(BoardRow.model_fields), rows, f"{problem_id}-d{dim}-leaderboard", format)


@router.get("/templates", response_model=list[Template])
async def list_templates() -> list[Template]:
    return [Template(key=key, name=name, code=templates.source(key))
            for key, name in templates.TEMPLATES.items()]
