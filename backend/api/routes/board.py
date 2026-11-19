from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter
from sqlalchemy import func, select

from db.models import Contribution, Problem, Run, Submission, User

from ..deps import Session
from ..ratings import user_ratings
from ..schemas import DayCount, GlobalRow, ProblemCount, SetterRow, Stats

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


@router.get("/leaderboard/setters", response_model=list[SetterRow])
async def setter_leaderboard(session: Session) -> list[SetterRow]:
    """People ranked by their approved problems that are live, then by how many people
    have had a submission judged on them."""
    owned = (await session.execute(
        select(Contribution.user_id, Contribution.problem_id)
        .join(Problem, Problem.id == Contribution.problem_id)
        .where(Contribution.status == "approved", Problem.is_active))).all()
    if not owned:
        return []
    usage = (await session.execute(
        select(Submission.problem_id, Submission.user_id)
        .join(User, User.id == Submission.user_id)
        .where(Submission.problem_id.in_({p for _, p in owned}),
               Submission.status == "done", User.is_bot.is_(False)))).all()
    by_problem: dict[str, list[int]] = defaultdict(list)
    for problem_id, user_id in usage:
        by_problem[problem_id].append(user_id)
    problems: dict[int, set[str]] = defaultdict(set)
    for owner, pid in owned:
        if pid:  # always set once approved; the join already requires it
            problems[owner].add(pid)
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_(problems)))}
    rows = []
    for user_id, ids in problems.items():
        tries = [u for p in ids for u in by_problem[p] if u != user_id]
        rows.append((len(ids), len(set(tries)), len(tries), users[user_id]))
    rows.sort(key=lambda r: (-r[0], -r[1], -r[2], r[3].name))
    return [SetterRow(rank=i, user_id=u.id, name=u.name, country=u.country,
                      institution=u.institution, problems=n, solvers=s, submissions=t)
            for i, (n, s, t, u) in enumerate(rows, start=1)]


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
