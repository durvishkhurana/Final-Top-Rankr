"""Global rating: the sum, over problems, of a user's best score on that problem."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Submission, User


@dataclass
class Rated:
    user: User
    rating: float
    problems: int
    rank: int


async def user_ratings(session: AsyncSession) -> list[Rated]:
    """All non-bot users with at least one scored submission, best first.

    shortcut: computed on every request, fine for a classroom-sized user base;
    cache or materialise once leaderboards get slow.
    """
    best = (select(Submission.user_id, Submission.problem_id,
                   func.max(Submission.score).label("best"))
            .where(Submission.status == "done")
            .group_by(Submission.user_id, Submission.problem_id).subquery())
    rating = func.sum(best.c.best)
    rows = await session.execute(
        select(User, rating, func.count())
        .join(best, best.c.user_id == User.id)
        .where(User.is_bot.is_(False))
        .group_by(User.id).order_by(rating.desc(), User.id))
    return [Rated(user, float(total), int(n), rank)
            for rank, (user, total, n) in enumerate(rows, start=1)]
