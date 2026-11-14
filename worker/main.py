"""Queue worker: judges queued submissions. Start with `arq worker.main.WorkerSettings`.

The worker needs the `docker` CLI and access to the Docker daemon to start sandbox
containers.
"""

import asyncio
import logging
from typing import Any

from arq.connections import RedisSettings

from core.config import get_settings
from db.base import sessionmaker
from db.models import Submission
from db.results import judge_refs, store_result
from judge.evaluate import judge
from judge.functions import PROBLEMS
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


class WorkerSettings:
    functions = [judge_submission]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 2  # each job already runs 4 sandbox containers in parallel
    job_timeout = 3600
    max_tries = 1
