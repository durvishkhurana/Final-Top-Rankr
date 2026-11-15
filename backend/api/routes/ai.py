import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ai import llm
from ai.features import Analysis, Coach, run_stats
from db.models import AiNote, Contest, Submission, User

from ..deps import CurrentUser, Session
from ..schemas import AiStatus, NoteOut

router = APIRouter(tags=["ai"])


async def guarded(call: Callable[[], Awaitable[Any]]) -> Any:
    """Maps the wrapper's failures to clear HTTP errors."""
    try:
        return await call()
    except llm.AiDisabled:
        raise HTTPException(503, "AI features are disabled on this server") from None
    except llm.AiLimit as exc:
        raise HTTPException(429, str(exc)) from None
    except llm.AiError as exc:
        raise HTTPException(502, str(exc)) from None


@router.get("/ai/status", response_model=AiStatus)
async def status(user: CurrentUser, session: Session) -> AiStatus:
    return AiStatus(enabled=llm.enabled(),
                    remaining_today=await llm.remaining_today(session, user.id))


async def _own(session: AsyncSession, submission_id: int, user: User) -> Submission:
    sub = await session.scalar(select(Submission).options(selectinload(Submission.runs))
                               .where(Submission.id == submission_id))
    if sub is None:
        raise HTTPException(404, "Submission not found")
    if sub.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "Only the author can ask for this")
    return sub


@router.get("/submissions/{submission_id}/notes", response_model=list[NoteOut])
async def notes(submission_id: int, user: CurrentUser, session: Session) -> list[AiNote]:
    await _own(session, submission_id, user)
    return list(await session.scalars(select(AiNote).where(
        AiNote.submission_id == submission_id).order_by(AiNote.kind)))


async def _note(session: AsyncSession, sub: Submission, kind: str,
                make: Callable[[], Awaitable[Any]]) -> AiNote:
    """Each note is generated once per submission and then reused."""
    note = await session.scalar(select(AiNote).where(AiNote.submission_id == sub.id,
                                                     AiNote.kind == kind))
    if note is None:
        answer = await guarded(make)
        note = AiNote(submission_id=sub.id, kind=kind, content=answer.model_dump())
        session.add(note)
        await session.commit()
    return note


@router.post("/submissions/{submission_id}/analysis", response_model=NoteOut)
async def analysis(submission_id: int, user: CurrentUser, session: Session) -> AiNote:
    """What is this algorithm really? The model sees the code only."""
    sub = await _own(session, submission_id, user)
    return await _note(session, sub, "analysis", lambda: llm.ask(
        session, feature="analysis", user_id=user.id, schema=Analysis,
        prompt=llm.render("analysis.v1", code=sub.code)))


@router.post("/submissions/{submission_id}/coach", response_model=NoteOut)
async def coach(submission_id: int, user: CurrentUser, session: Session) -> AiNote:
    """Run diagnosis. The model sees the code and summary statistics only."""
    sub = await _own(session, submission_id, user)
    if sub.status != "done":
        raise HTTPException(409, "The submission has not been judged yet")
    level = "specific"
    if sub.contest_id is not None:
        contest = await session.get(Contest, sub.contest_id)
        level = contest.hint_level if contest else level
    if level == "off":
        raise HTTPException(403, "Hints are switched off for this contest")
    stats = json.dumps(run_stats(sub, sub.runs), indent=1)
    return await _note(session, sub, "coach", lambda: llm.ask(
        session, feature="coach", user_id=user.id, schema=Coach,
        prompt=llm.render("coach.v1", code=sub.code, stats=stats, hint_level=level)))
