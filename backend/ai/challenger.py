"""The evolving AI challenger: an optimizer written by a language model that improves
itself one generation at a time on one problem and dimension.

Each generation starts from the best generation so far (the champion). The model gets
what a participant would have: the public description, the champion's code, and the
judge's summary statistics of its runs (relative precisions only, as for the coach),
plus the history of earlier attempts and the best human score. Its new code is judged
in the sandbox like any submission. A worse generation is kept in the history but does
not replace the champion.
"""

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Challenger, Generation, Problem, Run, Submission, User
from db.seed import bot_user
from judge.scoring import default_budget

from . import llm
from .features import ChallengerCode, run_stats

HISTORY = 10  # earlier generations shown to the model
STALE = timedelta(hours=2)  # a generation still running after this is considered dead


def baseline_prompt(problem: Problem, dim: int) -> str:
    """The first version: written from the public description alone."""
    return llm.render("baseline.v1", **_problem_vars(problem, dim))


def _problem_vars(problem: Problem, dim: int) -> dict[str, object]:
    lower = problem.lower if problem.lower is not None else -problem.bound
    upper = problem.upper if problem.upper is not None else problem.bound
    return {"name": problem.name, "dim": dim, "lower": lower, "upper": upper,
            "budget": default_budget(dim), "description": problem.description}


def running(generations: list[Generation]) -> bool:
    return any(g.status == "running" and datetime.now(UTC) - g.created_at < STALE
               for g in generations)


def champion(generations: list[Generation]) -> Generation | None:
    judged = [g for g in generations if g.status == "done" and g.submission is not None
              and g.submission.score is not None]
    return max(judged, key=lambda g: (g.submission.score, -g.number),  # type: ignore[union-attr]
               default=None)


def _line(g: Generation) -> str:
    score = g.submission.score if g.status == "done" and g.submission else None
    return f"{g.number}: {'failed' if score is None else f'{score:.0f}'} - {g.approach or g.error}"


async def histories(session: AsyncSession, challenger_ids: list[int]
                    ) -> dict[int, list[Generation]]:
    """Every generation of each challenger, oldest first, in one query."""
    out: dict[int, list[Generation]] = {i: [] for i in challenger_ids}
    for g in (await session.scalars(
            select(Generation).where(Generation.challenger_id.in_(challenger_ids))
            .order_by(Generation.number))).unique():
        out[g.challenger_id].append(g)
    return out


async def _next_prompt(session: AsyncSession, challenger: Challenger, problem: Problem,
                       gens: list[Generation], best: Generation | None) -> str:
    if best is None or best.submission is None:
        return baseline_prompt(problem, challenger.dim)
    sub = best.submission
    runs = list(await session.scalars(select(Run).where(Run.submission_id == sub.id)))
    target = await session.scalar(
        select(func.max(Submission.score)).join(User, User.id == Submission.user_id)
        .where(Submission.problem_id == problem.id, Submission.dim == challenger.dim,
               Submission.status == "done", User.is_bot.is_(False)))
    return llm.render(
        "challenger.v1", **_problem_vars(problem, challenger.dim), generation=best.number,
        score=sub.score, approach=best.approach, code=sub.code,
        stats=json.dumps(run_stats(sub, runs), indent=1),
        history="\n".join(_line(g) for g in gens[-HISTORY:]),
        target="none yet" if target is None else target)


async def evolve(session: AsyncSession, challenger_id: int,
                 judge: Callable[[int], Awaitable[None]]) -> Generation | None:
    """Writes, judges and records one generation. None if the challenger is gone or a
    generation of it is already running. judge(submission_id) judges in place."""
    challenger = await session.get(Challenger, challenger_id)
    if challenger is None or not (problem := await session.get(Problem, challenger.problem_id)):
        return None
    gens = (await histories(session, [challenger.id]))[challenger.id]
    if running(gens):
        return None
    best = champion(gens)
    gen = Generation(challenger_id=challenger.id, number=len(gens) + 1,
                     parent_id=best.id if best else None)
    session.add(gen)
    try:
        await session.commit()
    except IntegrityError:  # another job took this number first
        await session.rollback()
        return None

    bot = await bot_user(session, "challenger")
    try:
        answer = await llm.ask(session, feature="challenger", user_id=bot.id,
                               schema=ChallengerCode,
                               prompt=await _next_prompt(session, challenger, problem, gens, best))
    except (llm.AiDisabled, llm.AiLimit, llm.AiError) as exc:
        gen.status, gen.error = "failed", str(exc) or "AI features are disabled"
        await session.commit()
        return gen
    sub = Submission(user_id=bot.id, problem_id=problem.id, dim=challenger.dim,
                     code=answer.code)
    session.add(sub)
    await session.flush()
    gen.submission_id, gen.approach, gen.changes = sub.id, answer.approach, answer.changes
    await session.commit()

    await judge(sub.id)
    await session.refresh(sub)
    gen.status = "done" if sub.status == "done" else "failed"
    gen.error = sub.error
    await session.commit()
    return gen
