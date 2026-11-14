"""Idempotent base data: problem catalogue, stored reference values, first admin."""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import ROOT, get_settings
from core.security import hash_password
from judge.functions import PROBLEMS

from .models import FRef, Problem, User

CATALOGUE = ROOT / "problems" / "catalogue.json"


async def sync_catalogue(session: AsyncSession) -> int:
    entries = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    for entry in entries:
        problem = PROBLEMS[entry["id"]]
        values = {**entry, "bound": problem.bound, "dims": list(problem.dims),
                  "kind": problem.kind}
        update = {k: v for k, v in values.items() if k != "id"}
        await session.execute(insert(Problem).values(**values)
                              .on_conflict_do_update(index_elements=[Problem.id], set_=update))
    await session.commit()
    return len(entries)


async def load_f_refs(session: AsyncSession, path: Path) -> int:
    """Merges values from scripts/compute_f_ref.py output; keeps the lower value."""
    if not path.exists():
        return 0
    n = 0
    for problem_id, dims in json.loads(path.read_text()).items():
        for dim, seeds in dims.items():
            for seed, value in seeds.items():
                stmt = insert(FRef).values(problem_id=problem_id, dim=int(dim),
                                           instance_seed=int(seed), value=value)
                await session.execute(stmt.on_conflict_do_update(
                    index_elements=[FRef.problem_id, FRef.dim, FRef.instance_seed],
                    set_={"value": value}, where=FRef.value > value))
                n += 1
    await session.commit()
    return n


async def ensure_admin(session: AsyncSession) -> User | None:
    s = get_settings()
    if not s.admin_email or not s.admin_password:
        return None
    user = await session.scalar(select(User).where(User.email == s.admin_email.lower()))
    if user is None:
        user = User(email=s.admin_email.lower(), name="Admin", role="admin",
                    password_hash=hash_password(s.admin_password))
        session.add(user)
        await session.commit()
    return user
