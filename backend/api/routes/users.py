from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from db.models import Submission, User

from ..deps import CurrentUser, Session
from ..ratings import user_ratings
from ..schemas import DayCount, Me, Profile, ProfileIn, ProfileSubmission

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=Me)
async def update_me(body: ProfileIn, user: CurrentUser, session: Session) -> User:
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(user, key, value.strip())
    await session.commit()
    return user


@router.get("/{user_id}/activity", response_model=list[DayCount])
async def activity(user_id: int, session: Session) -> list[DayCount]:
    """Submissions per UTC day over the last year, for the profile heatmap."""
    day = func.date(Submission.created_at)
    rows = await session.execute(
        select(day, func.count())
        .where(Submission.user_id == user_id,
               Submission.created_at >= datetime.now(UTC) - timedelta(days=371))
        .group_by(day).order_by(day))
    return [DayCount(day=str(d), count=n) for d, n in rows]


@router.get("/{user_id}", response_model=Profile)
async def profile(user_id: int, session: Session) -> Profile:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    rated = next((r for r in await user_ratings(session) if r.user.id == user_id), None)
    total = await session.scalar(
        select(func.count()).select_from(Submission).where(Submission.user_id == user_id))
    recent = await session.scalars(
        select(Submission).where(Submission.user_id == user_id)
        .order_by(Submission.created_at.desc()).limit(20))
    return Profile(
        id=user.id, name=user.name, role=user.role, country=user.country,
        institution=user.institution, bio=user.bio, created_at=user.created_at,
        rating=rated.rating if rated else 0.0, rank=rated.rank if rated else None,
        problems_attempted=rated.problems if rated else 0, submissions=total or 0,
        recent=[ProfileSubmission.model_validate(s) for s in recent.unique()],
    )
