from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter
from sqlalchemy import func, select

from db.models import Problem, Run, Submission, User

from ..deps import Session
from ..ratings import user_ratings
from ..schemas import DayCount, GlobalRow, ProblemCount, Stats

router = APIRouter(tags=["leaderboard"])


@router.get("/leaderboard", response_model=list[GlobalRow])
async def global_leaderboard(session: Session,
                             by: Literal["user", "country", "institution"] = "user"
                             ) -> list[GlobalRow]:
    """by=user ranks people by rating. by=country / by=institution ranks groups by the
    mean rating of their rated members."""
    rated = await user_ratings(session)
    if by == "user":
        return [GlobalRow(rank=r.rank, key=str(r.user.id), name=r.user.name,
                          country=r.user.country, institution=r.user.institution,
                          rating=r.rating, problems=r.problems) for r in rated]
    groups: dict[str, list[float]] = defaultdict(list)
    for r in rated:
        if key := getattr(r.user, by):
            groups[key].append(r.rating)
    ordered = sorted(groups.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))
    return [GlobalRow(rank=i, key=key, name=key, rating=sum(v) / len(v), members=len(v))
            for i, (key, v) in enumerate(ordered, start=1)]


@router.get("/stats", response_model=Stats)
async def stats(session: Session) -> Stats:
    async def count(model: Any, *where: Any) -> int:
        return await session.scalar(select(func.count()).select_from(model).where(*where)) or 0

    day = func.date(Submission.created_at)
    since = datetime.now(UTC) - timedelta(days=30)
    per_day = await session.execute(
        select(day, func.count()).where(Submission.created_at >= since)
        .group_by(day).order_by(day))
    per_problem = await session.execute(
        select(Problem.id, Problem.name, func.count(Submission.id))
        .join(Submission, Submission.problem_id == Problem.id, isouter=True)
        .where(Problem.is_active).group_by(Problem.id).order_by(Problem.id))
    by_status = await session.execute(
        select(Submission.status, func.count()).group_by(Submission.status))
    return Stats(
        users=await count(User, User.is_bot.is_(False)),
        problems=await count(Problem, Problem.is_active),
        submissions=await count(Submission),
        runs=await count(Run),
        evaluations=await session.scalar(select(func.coalesce(func.sum(Run.evals), 0))) or 0,
        per_day=[DayCount(day=str(d), count=n) for d, n in per_day],
        per_problem=[ProblemCount(problem_id=i, name=name, count=n) for i, name, n in per_problem],
        by_status={status: n for status, n in by_status},
    )
