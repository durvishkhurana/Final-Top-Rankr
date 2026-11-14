"""Stores judge output and keeps scores consistent with the best-known values."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from judge.evaluate import score_runs
from judge.functions import PROBLEMS

from .models import FRef, Run, Submission

RUN_FIELDS = ("instance_seed", "seed", "status", "error", "evals", "f_best", "aocc",
              "precision", "wall_sec", "trace", "log", "points", "solution")


async def load_f_ref(session: AsyncSession, problem_id: str, dim: int) -> dict[int, float]:
    rows = await session.execute(
        select(FRef.instance_seed, FRef.value).where(FRef.problem_id == problem_id,
                                                     FRef.dim == dim))
    return {seed: value for seed, value in rows}


async def ref_lookup(session: AsyncSession, problem_id: str, dim: int
                     ) -> Callable[[int], float | None]:
    """Reference value by instance seed, for turning stored traces into precisions."""
    problem = PROBLEMS[problem_id]
    if problem.z_opt is not None:
        f_opt = float(problem.fn(np.full((1, dim), problem.z_opt))[0])
        return lambda seed: f_opt
    return (await load_f_ref(session, problem_id, dim)).get


async def store_result(session: AsyncSession, sub: Submission, out: dict[str, Any]) -> None:
    """Saves the runs of a judged submission. If any run beat the best-known value
    of its instance, that value is lowered and every submission on the same problem
    and dimension is re-scored from its stored traces."""
    # One writer per (problem, dim) at a time, so concurrent jobs cannot interleave
    # a reference-value update with a re-score.
    await session.execute(select(func.pg_advisory_xact_lock(
        func.hashtext(f"{sub.problem_id}:{sub.dim}"))))
    for r in out["runs"]:  # Postgres text cannot hold NUL bytes
        r["log"], r["error"] = r["log"].replace("\x00", ""), r["error"].replace("\x00", "")
    session.add_all(Run(submission_id=sub.id, **{k: r[k] for k in RUN_FIELDS})
                    for r in out["runs"])
    sub.budget = out["budget"]
    sub.status, sub.finished_at = "done", datetime.now(UTC)
    for key in ("score", "aocc", "iqr", "median_precision"):
        setattr(sub, key, out[key])
    await session.flush()

    improved = False
    if PROBLEMS[sub.problem_id].z_opt is None:
        known = await load_f_ref(session, sub.problem_id, sub.dim)
        for seed in {r["instance_seed"] for r in out["runs"]}:
            best = min((r["f_best"] for r in out["runs"] if r["instance_seed"] == seed
                        and r["status"] == "ok" and r["f_best"] is not None), default=None)
            if best is not None and best < known.get(seed, float("inf")):
                improved = True
                stmt = insert(FRef).values(problem_id=sub.problem_id, dim=sub.dim,
                                           instance_seed=seed, value=best)
                await session.execute(stmt.on_conflict_do_update(
                    index_elements=[FRef.problem_id, FRef.dim, FRef.instance_seed],
                    set_={"value": best}))
    if improved:
        await rescore(session, sub.problem_id, sub.dim)
    await session.commit()


async def rescore(session: AsyncSession, problem_id: str, dim: int) -> None:
    refs = await load_f_ref(session, problem_id, dim)
    subs = await session.scalars(
        select(Submission).options(selectinload(Submission.runs))
        .where(Submission.problem_id == problem_id, Submission.dim == dim,
               Submission.status == "done").execution_options(populate_existing=True))
    for sub in subs.unique():
        runs = [{k: getattr(r, k) for k in RUN_FIELDS} for r in sub.runs]
        if not runs or sub.budget is None or any(r["instance_seed"] not in refs for r in runs):
            continue
        summary = score_runs(runs, refs, sub.budget)
        for row, r in zip(sub.runs, runs, strict=True):
            row.aocc, row.precision = r["aocc"], r["precision"]
        for key, value in summary.items():
            setattr(sub, key, value)


async def judge_refs(session: AsyncSession, problem_id: str, dim: int) -> dict[int, float] | None:
    """f_ref argument for judge(): stored values, or None for known-optimum problems."""
    if PROBLEMS[problem_id].z_opt is not None:
        return None
    return await load_f_ref(session, problem_id, dim)
