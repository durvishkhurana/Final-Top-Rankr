"""Removes seeded demo data: every user flagged is_demo and their submissions.

    python scripts/reset.py

Real accounts, baselines and reference values are kept.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import delete  # noqa: E402

from db.base import sessionmaker  # noqa: E402
from db.models import User  # noqa: E402


async def main() -> None:
    async with sessionmaker()() as session:
        result = await session.execute(delete(User).where(User.is_demo))
        await session.commit()
        print(f"Removed {result.rowcount} demo users and their submissions.")  # type: ignore[attr-defined]


if __name__ == "__main__":
    asyncio.run(main())
