import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Contest,
    ContestEntry,
    Course,
    Enrollment,
    FinalResult,
    Problem,
    Submission,
    User,
)

from ..deps import CurrentUser, Enqueue, OptionalUser, Session
from ..schemas import ContestBoardRow, ContestIn, ContestOut, JoinIn

router = APIRouter(prefix="/contests", tags=["contests"])


def new_code() -> str:
    return secrets.token_urlsafe(6)


def phase(contest: Contest) -> str:
    """upcoming | running | ended | finalising | final"""
    if contest.status != "open":
        return contest.status
    now = datetime.now(UTC)
    if now < contest.starts_at:
        return "upcoming"
    return "running" if now < contest.ends_at else "ended"


def can_manage(contest: Contest, user: User | None) -> bool:
    return user is not None and (user.role == "admin" or user.id == contest.created_by)


async def is_participant(session: AsyncSession, contest_id: int, user_id: int) -> bool:
    return await session.get(ContestEntry, (contest_id, user_id)) is not None


async def _out(session: AsyncSession, contest: Contest, user: User | None) -> ContestOut:
    count = await session.scalar(select(func.count()).select_from(ContestEntry)
                                 .where(ContestEntry.contest_id == contest.id)) or 0
    manage = can_manage(contest, user)
    return ContestOut(
        id=contest.id, title=contest.title, description=contest.description,
        tasks=contest.tasks, starts_at=contest.starts_at, ends_at=contest.ends_at,
        phase=phase(contest), invite_only=contest.invite_code is not None,
        course_id=contest.course_id, participants=count, can_manage=manage,
        joined=user is not None and await is_participant(session, contest.id, user.id),
        invite_code=contest.invite_code if manage else None)


async def _get(session: AsyncSession, contest_id: int) -> Contest:
    contest = await session.get(Contest, contest_id)
    if contest is None:
        raise HTTPException(404, "Contest not found")
    return contest


@router.post("", response_model=ContestOut, status_code=201)
async def create(body: ContestIn, user: CurrentUser, session: Session) -> ContestOut:
    if user.role not in ("instructor", "admin"):
        raise HTTPException(403, "Only instructors and admins can create contests")
    if body.ends_at <= body.starts_at:
        raise HTTPException(422, "The contest must end after it starts")
    for task in body.tasks:
        problem = await session.get(Problem, task.problem_id)
        if problem is None or not problem.is_active or task.dim not in problem.dims:
            raise HTTPException(422, f"Unknown problem or dimension: {task.problem_id} "
                                     f"at {task.dim}")
    if body.course_id is not None:
        course = await session.get(Course, body.course_id)
        if course is None or (course.instructor_id != user.id and user.role != "admin"):
            raise HTTPException(403, "You do not teach this course")
    contest = Contest(
        title=body.title.strip(), description=body.description.strip(),
        tasks=[t.model_dump() for t in body.tasks], starts_at=body.starts_at,
        ends_at=body.ends_at, created_by=user.id, course_id=body.course_id,
        invite_code=new_code() if body.invite_only else None)
    session.add(contest)
    await session.commit()
    return await _out(session, contest, user)


@router.get("", response_model=list[ContestOut])
async def list_contests(user: OptionalUser, session: Session) -> list[ContestOut]:
    """Contests anyone may see, plus the course contests of the viewer's courses."""
    mine = (select(Enrollment.course_id).where(Enrollment.user_id == (user.id if user else 0))
            .union(select(Course.id).where(Course.instructor_id == (user.id if user else 0))))
    contests = await session.scalars(
        select(Contest).where(Contest.course_id.is_(None) | Contest.course_id.in_(mine))
        .order_by(Contest.starts_at.desc()))
    return [await _out(session, c, user) for c in contests]


@router.get("/{contest_id}", response_model=ContestOut)
async def get(contest_id: int, user: OptionalUser, session: Session) -> ContestOut:
    return await _out(session, await _get(session, contest_id), user)


@router.post("/{contest_id}/join", response_model=ContestOut)
async def join(contest_id: int, body: JoinIn, user: CurrentUser, session: Session) -> ContestOut:
    contest = await _get(session, contest_id)
    if phase(contest) in ("finalising", "final", "ended"):
        raise HTTPException(409, "This contest is closed")
    if contest.course_id is not None:
        if await session.get(Enrollment, (contest.course_id, user.id)) is None:
            raise HTTPException(403, "Join the course first")
    elif contest.invite_code is not None and not secrets.compare_digest(
            body.code.strip(), contest.invite_code):
        raise HTTPException(403, "Wrong invite code")
    await session.execute(insert(ContestEntry).values(contest_id=contest.id, user_id=user.id)
                          .on_conflict_do_nothing())
    await session.commit()
    return await _out(session, contest, user)


@router.get("/{contest_id}/leaderboard", response_model=list[ContestBoardRow])
async def leaderboard(contest_id: int, session: Session) -> list[ContestBoardRow]:
    """While a contest runs: each participant's best public score per task. Once it is
    final: the scores of those submissions re-run on held-out instances."""
    contest = await _get(session, contest_id)
    final = contest.status == "final"
    scores: dict[int, dict[str, float]] = {}
    if final:
        rows = await session.execute(
            select(FinalResult.user_id, FinalResult.problem_id, FinalResult.dim,
                   FinalResult.score).where(FinalResult.contest_id == contest.id))
    else:
        rows = await session.execute(
            select(Submission.user_id, Submission.problem_id, Submission.dim,
                   func.max(Submission.score))
            .where(Submission.contest_id == contest.id, Submission.status == "done")
            .group_by(Submission.user_id, Submission.problem_id, Submission.dim))
    for user_id, problem_id, dim, score in rows:
        scores.setdefault(user_id, {})[f"{problem_id}@{dim}"] = score or 0.0

    users = {u.id: u for u in await session.scalars(
        select(User).where(User.id.in_(scores)))} if scores else {}
    ordered = sorted(scores.items(), key=lambda kv: -sum(kv[1].values()))
    return [ContestBoardRow(rank=i, user_id=uid, name=users[uid].name,
                            is_baseline=users[uid].is_bot, total=sum(per.values()),
                            scores=per, final=final)
            for i, (uid, per) in enumerate(ordered, start=1)]


@router.post("/{contest_id}/finalise", response_model=ContestOut)
async def finalise(contest_id: int, user: CurrentUser, session: Session, enqueue: Enqueue
                   ) -> ContestOut:
    """Closes the contest and re-runs every participant's best submission per task on
    held-out instances. Those scores become the final ranking."""
    contest = await _get(session, contest_id)
    if not can_manage(contest, user):
        raise HTTPException(403, "Only the organiser can finalise a contest")
    if contest.status != "open":
        raise HTTPException(409, "This contest is already being finalised or is final")
    contest.status = "finalising"
    contest.ends_at = min(contest.ends_at, datetime.now(UTC))
    await session.commit()
    await enqueue("finalise_contest", contest.id)
    return await _out(session, contest, user)
