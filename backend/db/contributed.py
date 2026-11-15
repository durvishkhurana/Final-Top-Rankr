"""Bridges approved contributions (rows) and the judge's problem registry (code)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from judge.functions import PROBLEMS, Array, Problem

from .models import Contribution


def _never(X: Array) -> Array:
    raise RuntimeError("contributed functions are evaluated in the sandbox only")


def register(item: Contribution) -> None:
    """shift_frac 0.2 must match the margin smoke_test probes beyond the box."""
    assert item.problem_id is not None
    PROBLEMS[item.problem_id] = Problem(
        item.problem_id, item.name, _never, bound=(item.upper - item.lower) / 2,
        lower=item.lower, upper=item.upper, dims=tuple(item.dims), shift_frac=0.2,
        source=item.source)


async def load_contributed(session: AsyncSession) -> None:
    """Call before using PROBLEMS for an id that may be a contributed problem."""
    for item in await session.scalars(select(Contribution).where(
            Contribution.status == "approved")):
        if item.problem_id not in PROBLEMS:
            register(item)
