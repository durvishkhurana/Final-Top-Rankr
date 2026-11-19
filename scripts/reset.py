"""Removes seeded demo data: every user flagged is_demo, their submissions, courses,
contests and tests, and the problems they contributed.

    python scripts/reset.py

Real accounts, baselines and reference values are kept.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import delete, select  # noqa: E402

from db.base import sessionmaker  # noqa: E402
from db.models import Contribution, Problem, Submission, User  # noqa: E402


async def main() -> None:
    async with sessionmaker()() as session:
        # problems from demo contributions would be left without their source
        contributed = select(Contribution.problem_id).join(User).where(
            User.is_demo, Contribution.problem_id.is_not(None))
        await session.execute(delete(Submission).where(Submission.problem_id.in_(contributed)))
        await session.execute(delete(Problem).where(Problem.id.in_(contributed)))
        result = await session.execute(delete(User).where(User.is_demo))
        await session.commit()
        print(f"Removed {result.rowcount} demo users and their data.")  # type: ignore[attr-defined]


if __name__ == "__main__":
    asyncio.run(main())
