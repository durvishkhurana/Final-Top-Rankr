"""Queue worker: judges queued submissions. Start with `arq worker.main.WorkerSettings`.

The worker needs the `docker` CLI and access to the Docker daemon to start sandbox
containers.
"""

import asyncio
import hmac
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import distinct_on

from ai.challenger import evolve
from core.config import get_settings
from db.base import sessionmaker
from db.contributed import load_contributed
from db.models import (
    AuthEvent,
    Challenger,
    Contest,
    Contribution,
    FinalResult,
    RefreshToken,
    Submission,
)
from db.results import judge_refs, store_result
from exams.grading import grade_attempt as grade
from exams.grading import purge_events
from judge.contributed import smoke_test
from judge.evaluate import judge, score_runs
from judge.functions import PROBLEMS
from judge.instance import make_instance
from judge.runner import Limits

log = logging.getLogger("worker")

PLATFORM_ERROR = ("The judge could not run this submission because of a platform error. "
                  "It does not count against your code; please submit again.")


async def judge_submission(ctx: dict[str, Any], submission_id: int) -> None:
    async with sessionmaker()() as session:
        sub = await session.get(Submission, submission_id)
        if sub is None or sub.status != "queued":
            return
        sub.status = "running"
        await session.commit()
        try:
            await load_contributed(session)
            f_ref = await judge_refs(session, sub.problem_id, sub.dim)
            out = await asyncio.to_thread(
                judge, sub.code, PROBLEMS[sub.problem_id], sub.dim, f_ref=f_ref,
                limits=Limits.from_env(), sandbox=ctx.get("sandbox", True))
            await store_result(session, sub, out)
        except Exception:
            log.exception("judging submission %s failed", submission_id)
            await session.rollback()
            sub.status, sub.error = "failed", PLATFORM_ERROR
            await session.commit()


def heldout_seeds(contest_id: int, n: int = 3) -> list[int]:
    """Instance seeds used only for a contest's final ranking. They are derived from a
    server secret and are never stored with the contest or sent to a client."""
    s = get_settings()
    key = (s.heldout_secret or s.jwt_secret).encode()
    return [10**6 + int.from_bytes(hmac.digest(key, f"{contest_id}:{k}".encode(), "sha256")[:6])
            for k in range(n)]


async def finalise_contest(ctx: dict[str, Any], contest_id: int) -> None:
    """Re-runs every participant's best public submission per task on held-out
    instances. All entries of a task are scored against the same reference values:
    the exact optimum, or the best value any of them reached."""
    seeds = heldout_seeds(contest_id)
    async with sessionmaker()() as session:
        contest = await session.get(Contest, contest_id)
        if contest is None or contest.status != "finalising":
            return
        try:
            await load_contributed(session)
            await session.execute(delete(FinalResult).where(FinalResult.contest_id == contest_id))
            for task in contest.tasks:
                problem, dim = PROBLEMS[task["problem_id"]], task["dim"]
                best = await session.scalars(
                    select(Submission)
                    .where(Submission.contest_id == contest_id, Submission.status == "done",
                           Submission.problem_id == problem.id, Submission.dim == dim)
                    .ext(distinct_on(Submission.user_id))
                    .order_by(Submission.user_id, Submission.score.desc(), Submission.created_at))
                entries = []
                for sub in best.unique():
                    out = await asyncio.to_thread(
                        judge, sub.code, problem, dim, instance_seeds=seeds,
                        limits=Limits.from_env(), sandbox=ctx.get("sandbox", True))
                    entries.append((sub, out))
                refs = {}
                for seed in seeds:
                    f_opt = make_instance(problem, dim, seed).f_opt
                    values = [r["f_best"] for _, out in entries for r in out["runs"]
                              if r["instance_seed"] == seed and r["f_best"] is not None]
                    refs[seed] = f_opt if f_opt is not None else min(values, default=0.0)
                for sub, out in entries:
                    summary = score_runs(out["runs"], refs, out["budget"])
                    session.add(FinalResult(
                        contest_id=contest_id, user_id=sub.user_id, problem_id=problem.id,
                        dim=dim, submission_id=sub.id, score=summary["score"],
                        aocc=summary["aocc"], iqr=summary["iqr"],
                        median_precision=summary["median_precision"],
                        runs=[{"instance": seeds.index(r["instance_seed"]), "seed": r["seed"],
                               "status": r["status"], "aocc": r["aocc"],
                               "precision": r["precision"]} for r in out["runs"]]))
            contest.status = "final"
            await session.commit()
        except Exception:
            log.exception("finalising contest %s failed", contest_id)
            await session.rollback()
            contest.status = "open"  # the organiser can try again
            await session.commit()


async def smoke_contribution(ctx: dict[str, Any], contribution_id: int) -> None:
    """Runs the contributed function in a sandbox before an admin sees it."""
    async with sessionmaker()() as session:
        item = await session.get(Contribution, contribution_id)
        if item is None or item.status != "testing":
            return
        try:
            item.smoke = await asyncio.to_thread(
                smoke_test, item.source, item.lower, item.upper, item.dims,
                Limits.from_env(), ctx.get("sandbox", True))
        except Exception:
            log.exception("smoke test of contribution %s failed", contribution_id)
            item.smoke = {"ok": False, "checks": [
                {"name": "the smoke test could run", "ok": False, "detail": "platform error"}]}
        item.status = "pending" if item.smoke["ok"] else "failed"
        await session.commit()


async def grade_attempt(ctx: dict[str, Any], attempt_id: int) -> None:
    async with sessionmaker()() as session:
        await grade(session, attempt_id)


async def evolve_challenger(ctx: dict[str, Any], challenger_id: int) -> None:
    """Writes one generation of a challenger and judges it here, before returning."""
    async with sessionmaker()() as session:
        gen = await evolve(session, challenger_id,
                           lambda submission_id: judge_submission(ctx, submission_id))
    if gen is not None:
        log.info("challenger %s generation %s: %s", challenger_id, gen.number, gen.status)


async def evolve_challengers(ctx: dict[str, Any]) -> None:
    """Daily: one generation of every active challenger, within the AI daily limits."""
    async with sessionmaker()() as session:
        ids = list(await session.scalars(select(Challenger.id).where(Challenger.active)))
    for challenger_id in ids:
        await evolve_challenger(ctx, challenger_id)


async def purge_old_rows(ctx: dict[str, Any]) -> None:
    """Daily: integrity signals past their retention, expired sign-in sessions, and
    account events older than any rate-limit window."""
    days = get_settings().integrity_log_retention_days
    now = datetime.now(UTC)
    async with sessionmaker()() as session:
        n = await purge_events(session, now - timedelta(days=days))
        await session.execute(delete(RefreshToken).where(RefreshToken.expires_at < now))
        await session.execute(delete(AuthEvent).where(AuthEvent.at < now - timedelta(days=1)))
        await session.commit()
    log.info("deleted %d integrity events older than %d days", n, days)


class WorkerSettings:
    functions = [judge_submission, finalise_contest, smoke_contribution, grade_attempt,
                 evolve_challenger]
    cron_jobs = [cron(purge_old_rows, hour={3}, minute={0}),
                 cron(evolve_challengers, hour={4}, minute={0})]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 2  # each job already runs 4 sandbox containers in parallel
    job_timeout = 3600
    max_tries = 1
