"""Grading of a handed-in attempt. Multiple choice and numeric answers are graded by
code; reasoning answers by the language model against the instructor's rubric, with
the score itself computed here from the model's level. Every grade is audit-logged."""

import json
import logging
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ai import llm
from ai.features import Grade
from db.models import Answer, Attempt, GradeEvent, IntegrityEvent, Question, Submission

from . import numeric
from .personal import facts

log = logging.getLogger("grading")


async def set_total(session: AsyncSession, attempt: Attempt) -> None:
    scores = await session.scalars(select(Answer.score).where(Answer.attempt_id == attempt.id))
    attempt.total = round(sum(s or 0.0 for s in scores), 2)


def _record(session: AsyncSession, answer: Answer, score: float | None, by: str,
            reason: str) -> None:
    session.add(GradeEvent(answer_id=answer.id, actor_id=None, old_score=answer.score,
                           new_score=score, reason=reason))
    answer.score, answer.graded_by = score, by


async def _grade_reasoning(session: AsyncSession, answer: Answer, q: Question) -> None:
    if not answer.response:
        _record(session, answer, 0.0, "code", "no answer")
        return
    sub = await session.scalar(select(Submission).options(selectinload(Submission.runs))
                               .where(Submission.id == answer.submission_id))
    try:
        grade = await llm.ask(
            session, feature="grading", user_id=None, schema=Grade,
            prompt=llm.render(
                "grade.v1", question=answer.prompt, rubric=q.data["rubric"],
                facts=json.dumps(facts(sub, sub.runs)) if sub else "none",
                answer=answer.response, follow_up=answer.follow_up or "(none)",
                follow_up_answer=answer.follow_up_response or "(none)",
                code=sub.code if sub else "(none)"))
    except (llm.AiDisabled, llm.AiLimit, llm.AiError) as exc:
        answer.rationale = f"Not graded automatically ({type(exc).__name__}); grade by hand."
        return
    answer.rationale, answer.confidence = grade.rationale, grade.confidence
    if grade.contradiction:
        note = grade.contradiction_note.strip() or "the answers do not match the code or runs"
        answer.flags = [*answer.flags, f"possible contradiction: {note}"]
    _record(session, answer, round(grade.level * answer.max_score, 2), "ai",
            "graded by AI against the rubric")


async def grade_attempt(session: AsyncSession, attempt_id: int) -> None:
    attempt = await session.get(Attempt, attempt_id)
    if attempt is None or attempt.status != "submitted":
        return
    rows = await session.execute(select(Answer, Question)
                                 .join(Question, Question.id == Answer.question_id)
                                 .where(Answer.attempt_id == attempt_id))
    for answer, q in rows:
        if answer.graded_by == "instructor":
            continue
        if q.kind == "mcq":
            right = answer.response == str(q.data["correct"])
            _record(session, answer, answer.max_score if right else 0.0, "code",
                    "graded by code")
        elif q.kind == "numeric":
            _, expected = numeric.expected(q.data["generator"], attempt.exam_id,
                                           attempt.user_id, q.id)
            try:
                right = numeric.is_correct(float(answer.response), expected,
                                           q.data.get("rel_tol", 1e-3))
            except ValueError:
                right = False
            _record(session, answer, answer.max_score if right else 0.0, "code",
                    "graded by code")
        else:
            await _grade_reasoning(session, answer, q)
    await set_total(session, attempt)
    attempt.status = "graded"
    await session.commit()


async def purge_events(session: AsyncSession, older_than: datetime) -> int:
    """Deletes integrity signals received before older_than."""
    result = await session.execute(delete(IntegrityEvent).where(
        IntegrityEvent.received_at < older_than))
    await session.commit()
    return int(getattr(result, "rowcount", 0) or 0)
