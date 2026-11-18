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


async def user_ratings(session: AsyncSession, user_id: int | None = None) -> list[Rated]:
    """All non-bot users with at least one scored submission, best first; or only the
    given user, still ranked against everyone.

    shortcut: computed on every request, fine for a classroom-sized user base;
    cache or materialise once leaderboards get slow.
    """
    best = (select(Submission.user_id, Submission.problem_id,
                   func.max(Submission.score).label("best"))
            .where(Submission.status == "done")
            .group_by(Submission.user_id, Submission.problem_id).subquery())
    rating = func.sum(best.c.best)
    ranked = (select(best.c.user_id, rating.label("rating"), func.count().label("problems"),
                     func.row_number().over(order_by=(rating.desc(), best.c.user_id))
                     .label("rank"))
              .join(User, User.id == best.c.user_id).where(User.is_bot.is_(False))
              .group_by(best.c.user_id).subquery())
    query = (select(User, ranked.c.rating, ranked.c.problems, ranked.c.rank)
             .join(ranked, ranked.c.user_id == User.id).order_by(ranked.c.rank))
    if user_id is not None:
        query = query.where(User.id == user_id)
    return [Rated(user, float(total), int(n), int(rank))
            for user, total, n, rank in await session.execute(query)]
