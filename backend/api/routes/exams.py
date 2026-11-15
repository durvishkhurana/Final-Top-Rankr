"""Course tests: building (instructor), taking (student), grading and review."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ai import llm
from ai.features import Distractors, FollowUp, Phrasings, SimilarityOpinion, Viva
from db.models import (
    Answer,
    Attempt,
    Course,
    Enrollment,
    Exam,
    GradeEvent,
    IntegrityEvent,
    Problem,
    Question,
    Submission,
    User,
)
from exams import numeric, similarity
from exams.grading import set_total
from exams.personal import FACTS, facts
from judge import templates

from ..deps import CurrentUser, Enqueue, Session
from ..schemas import (
    AnswerIn,
    AnswerResult,
    AnswerView,
    AttemptOut,
    AttemptResult,
    EventIn,
    EventOut,
    ExamIn,
    ExamOut,
    ExamPatch,
    FollowUpIn,
    GradeEventOut,
    GradeIn,
    MyAttempt,
    OpinionIn,
    PoolIn,
    QuestionIn,
    QuestionOut,
    SaveOut,
    SimilarPair,
    StartIn,
)
from .ai import guarded
from .courses import teaching

router = APIRouter(tags=["tests"])

POOL_SIZE = 20


# --- helpers --------------------------------------------------------------------------


def _teaches(course: Course, user: User) -> bool:
    return user.role == "admin" or course.instructor_id == user.id


async def _exam(session: AsyncSession, exam_id: int) -> tuple[Exam, Course]:
    exam = await session.get(Exam, exam_id)
    course = await session.get(Course, exam.course_id) if exam else None
    if exam is None or course is None:
        raise HTTPException(404, "Test not found")
    return exam, course


async def _own_exam(session: AsyncSession, exam_id: int, user: User) -> Exam:
    exam, course = await _exam(session, exam_id)
    if not _teaches(course, user):
        raise HTTPException(403, "Only the instructor can do this")
    return exam


async def _out(session: AsyncSession, exam: Exam, course: Course, user: User) -> ExamOut:
    count, total = (await session.execute(
        select(func.count(), func.coalesce(func.sum(Question.points), 0.0))
        .where(Question.exam_id == exam.id))).one()
    mine = await session.scalar(select(Attempt).where(Attempt.exam_id == exam.id,
                                                      Attempt.user_id == user.id))
    return ExamOut(
        id=exam.id, course_id=course.id, course_title=course.title, title=exam.title,
        description=exam.description, starts_at=exam.starts_at, ends_at=exam.ends_at,
        camera_checks=exam.camera_checks, status=exam.status, questions=count,
        max_total=total, teaches=_teaches(course, user),
        attempt=MyAttempt(id=mine.id, status=mine.status,
                          total=mine.total if exam.status == "closed" else None)
        if mine else None)


def _check_question(body: QuestionIn) -> dict[str, Any]:
    d = body.data
    if body.kind == "mcq":
        choices = [str(c).strip() for c in d.get("choices", []) if str(c).strip()]
        correct = d.get("correct")
        if len(choices) < 2 or not isinstance(correct, int) or not 0 <= correct < len(choices):
            raise HTTPException(422, "A multiple-choice question needs at least two choices "
                                     "and the index of the correct one")
        return {"choices": choices, "correct": correct}
    if body.kind == "numeric":
        if d.get("generator") not in numeric.GENERATORS:
            raise HTTPException(422, f"generator must be one of {sorted(numeric.GENERATORS)}")
        return {"generator": d["generator"], "rel_tol": float(d.get("rel_tol", 1e-3))}
    if not str(d.get("rubric", "")).strip():
        raise HTTPException(422, "A reasoning question needs a rubric")
    if numeric.fill(body.prompt, dict.fromkeys(FACTS, "")) is None:
        raise HTTPException(422, f"The question may use only these placeholders: {FACTS}")
    return {"problem_id": str(d.get("problem_id", "")), "dim": int(d.get("dim", 0)),
            "rubric": str(d["rubric"]).strip(), "follow_up": bool(d.get("follow_up", True)),
            "pool": [p for p in d.get("pool", []) if isinstance(p, str)]}


def _valid_pool(pool: list[str]) -> list[str]:
    blank = dict.fromkeys(FACTS, "")
    return [p.strip() for p in pool if p.strip() and numeric.fill(p, blank) is not None]


async def _draft_question(session: AsyncSession, exam_id: int, question_id: int,
                          user: User) -> Question:
    exam = await _own_exam(session, exam_id, user)
    question = await session.get(Question, question_id)
    if question is None or question.exam_id != exam_id:
        raise HTTPException(404, "Question not found")
    if exam.status != "draft":
        raise HTTPException(409, "Questions can only be changed while the test is a draft")
    return question


def _expected(exam_id: int, user_id: int, q: Question) -> tuple[dict[str, Any], float]:
    return numeric.instance(q.data["generator"],
                            numeric.personal_seed(exam_id, user_id, q.id))


# --- instructor: building ---------------------------------------------------------------


@router.get("/tests/question-kit")
async def question_kit(_: CurrentUser) -> dict[str, Any]:
    """What the question editor offers: numeric generators with their default text, and
    the placeholders reasoning questions may use."""
    return {"generators": {k: text for k, (_, text) in numeric.GENERATORS.items()},
            "facts": list(FACTS)}


@router.get("/tests", response_model=list[ExamOut])
async def list_exams(user: CurrentUser, session: Session) -> list[ExamOut]:
    """Tests of the courses the user teaches (all) or is enrolled in (once published)."""
    enrolled = select(Enrollment.course_id).where(Enrollment.user_id == user.id)
    rows = await session.execute(
        select(Exam, Course).join(Course, Course.id == Exam.course_id)
        .where((Course.instructor_id == user.id)
               | (Course.id.in_(enrolled) & (Exam.status != "draft")))
        .order_by(Exam.starts_at.desc()))
    return [await _out(session, e, c, user) for e, c in rows]


@router.post("/tests", response_model=ExamOut, status_code=201)
async def create_exam(body: ExamIn, user: CurrentUser, session: Session) -> ExamOut:
    course = await teaching(session, body.course_id, user)
    if body.ends_at <= body.starts_at:
        raise HTTPException(422, "The test must end after it starts")
    exam = Exam(**body.model_dump(), created_by=user.id)
    exam.title, exam.description = body.title.strip(), body.description.strip()
    session.add(exam)
    await session.commit()
    return await _out(session, exam, course, user)


@router.get("/tests/{exam_id}", response_model=ExamOut)
async def get_exam(exam_id: int, user: CurrentUser, session: Session) -> ExamOut:
    exam, course = await _exam(session, exam_id)
    member = await session.get(Enrollment, (course.id, user.id))
    if not _teaches(course, user) and (member is None or exam.status == "draft"):
        raise HTTPException(404, "Test not found")
    return await _out(session, exam, course, user)


@router.patch("/tests/{exam_id}", response_model=ExamOut)
async def update_exam(exam_id: int, body: ExamPatch, user: CurrentUser, session: Session,
                      enqueue: Enqueue) -> ExamOut:
    exam = await _own_exam(session, exam_id, user)
    changes = body.model_dump(exclude_unset=True, exclude={"status"})
    for key, value in changes.items():
        setattr(exam, key, value)
    if exam.ends_at <= exam.starts_at:
        raise HTTPException(422, "The test must end after it starts")
    to_grade: list[int] = []
    if body.status and body.status != exam.status:
        if body.status == "live":
            await _publish_gate(session, exam)
        if body.status == "closed":
            # attempts still open are handed in as they are
            open_ = await session.scalars(select(Attempt).where(
                Attempt.exam_id == exam.id, Attempt.status == "in_progress"))
            for attempt in open_:
                attempt.status, attempt.submitted_at = "submitted", datetime.now(UTC)
                to_grade.append(attempt.id)
        if body.status == "draft" and await session.scalar(
                select(func.count()).select_from(Attempt).where(Attempt.exam_id == exam.id)):
            raise HTTPException(409, "Students have started this test; it cannot go back "
                                     "to draft")
        exam.status = body.status
    await session.commit()
    for attempt_id in to_grade:
        await enqueue("grade_attempt", attempt_id)
    _, course = await _exam(session, exam.id)
    return await _out(session, exam, course, user)


async def _publish_gate(session: AsyncSession, exam: Exam) -> None:
    questions = list(await session.scalars(select(Question).where(Question.exam_id == exam.id)))
    if not questions:
        raise HTTPException(409, "Add at least one question before publishing")
    for q in questions:
        if q.kind == "reasoning" and not (q.pool_approved and q.data.get("pool")):
            raise HTTPException(409, f"Question {q.position}: approve its pool of "
                                     "phrasings before publishing")


@router.get("/tests/{exam_id}/questions", response_model=list[QuestionOut])
async def questions(exam_id: int, user: CurrentUser, session: Session) -> list[Question]:
    await _own_exam(session, exam_id, user)
    return list(await session.scalars(select(Question).where(Question.exam_id == exam_id)
                                      .order_by(Question.position)))


@router.post("/tests/{exam_id}/questions", response_model=QuestionOut, status_code=201)
async def add_question(exam_id: int, body: QuestionIn, user: CurrentUser,
                       session: Session) -> Question:
    exam = await _own_exam(session, exam_id, user)
    if exam.status != "draft":
        raise HTTPException(409, "Questions can only be changed while the test is a draft")
    data = _check_question(body)
    if body.kind == "reasoning":
        problem = await session.get(Problem, data["problem_id"])
        if problem is None or data["dim"] not in problem.dims:
            raise HTTPException(422, "Choose a problem and dimension the students submitted to")
    position = (await session.scalar(select(func.max(Question.position))
                                     .where(Question.exam_id == exam_id)) or 0) + 1
    question = Question(exam_id=exam_id, position=position, kind=body.kind,
                        prompt=body.prompt.strip(), points=body.points, data=data)
    session.add(question)
    await session.commit()
    return question


@router.put("/tests/{exam_id}/questions/{question_id}", response_model=QuestionOut)
async def edit_question(exam_id: int, question_id: int, body: QuestionIn, user: CurrentUser,
                        session: Session) -> Question:
    """Replaces a draft question. A reasoning question's pool must be approved again."""
    question = await _draft_question(session, exam_id, question_id, user)
    if body.kind != question.kind:
        raise HTTPException(422, "The kind of a question cannot change")
    data = _check_question(body)
    if body.kind == "reasoning":
        problem = await session.get(Problem, data["problem_id"])
        if problem is None or data["dim"] not in problem.dims:
            raise HTTPException(422, "Choose a problem and dimension the students submitted to")
        data["pool"] = question.data.get("pool", [])
        question.pool_approved = False
    question.prompt, question.points, question.data = body.prompt.strip(), body.points, data
    await session.commit()
    return question


@router.delete("/tests/{exam_id}/questions/{question_id}", status_code=204)
async def delete_question(exam_id: int, question_id: int, user: CurrentUser,
                          session: Session) -> None:
    question = await _draft_question(session, exam_id, question_id, user)
    await session.delete(question)
    await session.commit()


@router.post("/tests/{exam_id}/questions/{question_id}/distractors",
             response_model=Distractors)
async def distractors(exam_id: int, question_id: int, user: CurrentUser,
                      session: Session) -> Distractors:
    """Suggestions only: the instructor picks, edits and saves the choices."""
    q = await _draft_question(session, exam_id, question_id, user)
    if q.kind != "mcq":
        raise HTTPException(422, "Only multiple-choice questions have distractors")
    choices = q.data["choices"]
    result: Distractors = await guarded(lambda: llm.ask(
        session, feature="distractors", user_id=user.id, schema=Distractors,
        prompt=llm.render("distractors.v1", question=q.prompt,
                          correct=choices[q.data["correct"]], existing=json.dumps(choices),
                          count=3)))
    return result


@router.post("/tests/{exam_id}/questions/{question_id}/pool", response_model=QuestionOut)
async def generate_pool(exam_id: int, question_id: int, user: CurrentUser,
                        session: Session) -> Question:
    """Drafts ~20 phrasings of a reasoning question. They wait for the instructor."""
    q = await _draft_question(session, exam_id, question_id, user)
    if q.kind != "reasoning":
        raise HTTPException(422, "Only reasoning questions have a pool of phrasings")
    result: Phrasings = await guarded(lambda: llm.ask(
        session, feature="phrasings", user_id=user.id, schema=Phrasings,
        prompt=llm.render("phrasings.v1", template=q.prompt, count=POOL_SIZE,
                          placeholders=", ".join(f"{{{name}}}" for name in FACTS))))
    q.data = {**q.data, "pool": _valid_pool(result.phrasings)}
    q.pool_approved = False
    await session.commit()
    return q


@router.post("/tests/{exam_id}/questions/{question_id}/approve-pool",
             response_model=QuestionOut)
async def approve_pool(exam_id: int, question_id: int, body: PoolIn, user: CurrentUser,
                       session: Session) -> Question:
    q = await _draft_question(session, exam_id, question_id, user)
    pool = _valid_pool(body.pool)
    if q.kind != "reasoning" or len(pool) != len(body.pool):
        raise HTTPException(422, f"Each phrasing may use only these placeholders: {FACTS}")
    q.data, q.pool_approved = {**q.data, "pool": pool}, True
    await session.commit()
    return q


# --- student: taking ---------------------------------------------------------------------


async def _reasoning_prompt(session: AsyncSession, exam: Exam, user_id: int, q: Question
                            ) -> tuple[str, int | None, list[str]]:
    """The student's own phrasing, filled with facts from their latest judged
    submission. Without one, the instructor's generic text is used and flagged."""
    sub = await session.scalar(
        select(Submission).options(selectinload(Submission.runs))
        .where(Submission.user_id == user_id, Submission.problem_id == q.data["problem_id"],
               Submission.dim == q.data["dim"], Submission.status == "done")
        .order_by(Submission.created_at.desc()).limit(1))
    pool = q.data["pool"]
    phrasing = pool[numeric.personal_seed(exam.id, user_id, q.id) % len(pool)]
    if sub is None:
        text = numeric.fill(q.prompt, dict.fromkeys(FACTS, "(no judged submission)"))
        return text or q.prompt, None, ["no judged submission on the problem"]
    return numeric.fill(phrasing, facts(sub, sub.runs)) or q.prompt, sub.id, []


@router.post("/tests/{exam_id}/attempt", response_model=AttemptOut)
async def start(exam_id: int, body: StartIn, user: CurrentUser, session: Session
                ) -> AttemptOut:
    exam, course = await _exam(session, exam_id)
    if await session.get(Enrollment, (course.id, user.id)) is None:
        raise HTTPException(403, "Join the course to take this test")
    attempt = await session.scalar(select(Attempt).where(Attempt.exam_id == exam_id,
                                                         Attempt.user_id == user.id))
    if attempt is None:
        now = datetime.now(UTC)
        if exam.status != "live" or not exam.starts_at <= now <= exam.ends_at:
            raise HTTPException(409, "This test is not open")
        if not body.consent:
            raise HTTPException(422, "Read and accept the consent notice to start")
        attempt = Attempt(exam_id=exam_id, user_id=user.id,
                          camera_consent=exam.camera_checks and body.camera_consent)
        session.add(attempt)
        await session.flush()
        for q in await session.scalars(select(Question).where(Question.exam_id == exam_id)
                                       .order_by(Question.position)):
            prompt, sub_id = q.prompt, None
            flags: list[str] = []
            if q.kind == "numeric":
                params, _ = _expected(exam_id, user.id, q)
                prompt = numeric.fill(q.prompt, params) or q.prompt
            elif q.kind == "reasoning":
                prompt, sub_id, flags = await _reasoning_prompt(session, exam, user.id, q)
            session.add(Answer(attempt_id=attempt.id, question_id=q.id, prompt=prompt,
                               submission_id=sub_id, max_score=q.points, flags=flags))
        await session.commit()
    return await _attempt_out(session, attempt, user)


async def _attempt_out(session: AsyncSession, attempt: Attempt, user: User) -> AttemptOut:
    exam, course = await _exam(session, attempt.exam_id)
    graded = exam.status == "closed" and attempt.status == "graded"
    rows = await session.execute(
        select(Answer, Question).join(Question, Question.id == Answer.question_id)
        .where(Answer.attempt_id == attempt.id).order_by(Question.position))
    answers = [AnswerView(
        id=a.id, question_id=q.id, kind=q.kind, prompt=a.prompt,
        choices=q.data["choices"] if q.kind == "mcq" else None, max_score=a.max_score,
        response=a.response, follow_up=a.follow_up, follow_up_response=a.follow_up_response,
        score=a.score if graded else None, rationale=a.rationale if graded else "")
        for a, q in rows]
    return AttemptOut(id=attempt.id, exam=await _out(session, exam, course, user),
                      status=attempt.status, camera_consent=attempt.camera_consent,
                      total=attempt.total if graded else None, answers=answers)


async def _my_attempt(session: AsyncSession, attempt_id: int, user: User,
                      writable: bool = False) -> Attempt:
    attempt = await session.get(Attempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(404, "Attempt not found")
    if writable:
        exam, _ = await _exam(session, attempt.exam_id)
        if attempt.status != "in_progress" or exam.status != "live":
            raise HTTPException(409, "This attempt has been handed in")
        if datetime.now(UTC) > exam.ends_at:
            raise HTTPException(409, "The test has ended")
    return attempt


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
async def get_attempt(attempt_id: int, user: CurrentUser, session: Session) -> AttemptOut:
    return await _attempt_out(session, await _my_attempt(session, attempt_id, user), user)


async def _my_answer(session: AsyncSession, answer_id: int, user: User
                     ) -> tuple[Answer, Question, Attempt]:
    answer = await session.get(Answer, answer_id)
    if answer is None:
        raise HTTPException(404, "Answer not found")
    attempt = await _my_attempt(session, answer.attempt_id, user, writable=True)
    question = await session.get(Question, answer.question_id)
    assert question is not None
    return answer, question, attempt


@router.put("/answers/{answer_id}", response_model=SaveOut)
async def save_answer(answer_id: int, body: AnswerIn, user: CurrentUser, session: Session
                      ) -> SaveOut:
    """Saves a response. The first non-empty answer to a reasoning question with a
    follow-up gets one generated follow-up question."""
    answer, q, _ = await _my_answer(session, answer_id, user)
    answer.response = body.response.strip()
    answer.time_ms += body.time_ms
    answer.paste_chars += body.paste_chars
    if (q.kind == "reasoning" and q.data.get("follow_up") and answer.response
            and not answer.follow_up):
        sub = await session.scalar(select(Submission).options(selectinload(Submission.runs))
                                   .where(Submission.id == answer.submission_id))
        try:
            # not counted against the student's own AI quota
            result = await llm.ask(
                session, feature="follow_up", user_id=None, schema=FollowUp,
                prompt=llm.render("follow_up.v1", question=answer.prompt,
                                  answer=answer.response,
                                  facts=json.dumps(facts(sub, sub.runs)) if sub else "none",
                                  code=sub.code if sub else "(none)"))
            answer.follow_up = result.question
        except (llm.AiDisabled, llm.AiLimit, llm.AiError):
            pass  # the test goes on without a follow-up
    await session.commit()
    return SaveOut(follow_up=answer.follow_up)


@router.put("/answers/{answer_id}/follow-up", status_code=204)
async def save_follow_up(answer_id: int, body: FollowUpIn, user: CurrentUser,
                         session: Session) -> None:
    answer, _, _ = await _my_answer(session, answer_id, user)
    if not answer.follow_up:
        raise HTTPException(409, "This answer has no follow-up question")
    answer.follow_up_response = body.response.strip()
    await session.commit()


@router.post("/attempts/{attempt_id}/events", status_code=204)
async def record_events(attempt_id: int, body: list[EventIn], user: CurrentUser,
                        session: Session) -> None:
    """Browser signals (an event log only; no images or video)."""
    if len(body) > 200:
        raise HTTPException(422, "Send at most 200 events at a time")
    attempt = await _my_attempt(session, attempt_id, user)
    if attempt.status != "in_progress":
        return
    session.add_all(IntegrityEvent(attempt_id=attempt_id, **e.model_dump()) for e in body)
    await session.commit()


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptOut)
async def submit(attempt_id: int, user: CurrentUser, session: Session, enqueue: Enqueue
                 ) -> AttemptOut:
    attempt = await _my_attempt(session, attempt_id, user, writable=True)
    attempt.status, attempt.submitted_at = "submitted", datetime.now(UTC)
    await session.commit()
    await enqueue("grade_attempt", attempt.id)
    return await _attempt_out(session, attempt, user)


# --- instructor: review -------------------------------------------------------------------


@router.get("/tests/{exam_id}/results", response_model=list[AttemptResult])
async def results(exam_id: int, user: CurrentUser, session: Session) -> list[AttemptResult]:
    await _own_exam(session, exam_id, user)
    out = []
    questions = {q.id: q for q in await session.scalars(
        select(Question).where(Question.exam_id == exam_id))}
    for attempt in await session.scalars(select(Attempt).where(Attempt.exam_id == exam_id)
                                         .order_by(Attempt.id)):
        answers = []
        for a in await session.scalars(select(Answer).where(Answer.attempt_id == attempt.id)):
            q = questions[a.question_id]
            correct = None
            if q.kind == "mcq":
                correct = q.data["choices"][q.data["correct"]]
            elif q.kind == "numeric":
                correct = f"{_expected(exam_id, attempt.user_id, q)[1]:.6g}"
            history = await session.execute(
                select(GradeEvent, User.name).outerjoin(User, User.id == GradeEvent.actor_id)
                .where(GradeEvent.answer_id == a.id).order_by(GradeEvent.id))
            answers.append(AnswerResult(
                id=a.id, question_id=q.id, kind=q.kind, prompt=a.prompt, response=a.response,
                follow_up=a.follow_up, follow_up_response=a.follow_up_response,
                correct=correct, score=a.score, max_score=a.max_score, rationale=a.rationale,
                confidence=a.confidence, graded_by=a.graded_by, flags=a.flags,
                time_ms=a.time_ms, paste_chars=a.paste_chars, submission_id=a.submission_id,
                history=[GradeEventOut(actor=name or "automatic", old_score=e.old_score,
                                       new_score=e.new_score, reason=e.reason,
                                       created_at=e.created_at)
                         for e, name in history]))
        answers.sort(key=lambda r: questions[r.question_id].position)
        events = await session.scalars(select(IntegrityEvent).where(
            IntegrityEvent.attempt_id == attempt.id).order_by(IntegrityEvent.at))
        out.append(AttemptResult(
            id=attempt.id, user_id=attempt.user_id, name=attempt.user.name,
            status=attempt.status, camera_consent=attempt.camera_consent, total=attempt.total,
            started_at=attempt.started_at, submitted_at=attempt.submitted_at, viva=attempt.viva,
            answers=answers, events=[EventOut.model_validate(e) for e in events]))
    return out


async def _instructor_answer(session: AsyncSession, answer_id: int, user: User
                             ) -> tuple[Answer, Attempt]:
    answer = await session.get(Answer, answer_id)
    attempt = await session.get(Attempt, answer.attempt_id) if answer else None
    if answer is None or attempt is None:
        raise HTTPException(404, "Answer not found")
    await _own_exam(session, attempt.exam_id, user)
    return answer, attempt


@router.post("/answers/{answer_id}/grade", response_model=AnswerResult)
async def override(answer_id: int, body: GradeIn, user: CurrentUser, session: Session
                   ) -> AnswerResult:
    """Any grade can be changed by the instructor; every change is logged."""
    answer, attempt = await _instructor_answer(session, answer_id, user)
    if body.score > answer.max_score:
        raise HTTPException(422, f"The most this answer can get is {answer.max_score}")
    session.add(GradeEvent(answer_id=answer.id, actor_id=user.id, old_score=answer.score,
                           new_score=body.score, reason=body.reason.strip()))
    answer.score, answer.graded_by = body.score, "instructor"
    await set_total(session, attempt)
    await session.commit()
    rows = [r for r in await results(attempt.exam_id, user, session) if r.id == attempt.id]
    return next(a for a in rows[0].answers if a.id == answer.id)


async def _student_code(session: AsyncSession, attempt: Attempt) -> Submission | None:
    """The code a viva is about: the run a reasoning question asked about, else the
    student's latest judged submission."""
    sub_id = await session.scalar(select(Answer.submission_id).where(
        Answer.attempt_id == attempt.id, Answer.submission_id.is_not(None)).limit(1))
    if sub_id is not None:
        return await session.get(Submission, sub_id)
    sub: Submission | None = await session.scalar(
        select(Submission).where(Submission.user_id == attempt.user_id,
                                 Submission.status == "done")
        .order_by(Submission.created_at.desc()).limit(1))
    return sub


@router.post("/attempts/{attempt_id}/viva", response_model=list[str])
async def viva(attempt_id: int, user: CurrentUser, session: Session) -> list[str]:
    """Three questions to ask the student in person. Shown to the instructor only."""
    attempt = await session.get(Attempt, attempt_id)
    if attempt is None:
        raise HTTPException(404, "Attempt not found")
    await _own_exam(session, attempt.exam_id, user)
    if attempt.viva:
        return attempt.viva
    sub = await _student_code(session, attempt)
    if sub is None:
        raise HTTPException(409, "This student has no judged submission to ask about")
    result: Viva = await guarded(lambda: llm.ask(
        session, feature="viva", user_id=user.id, schema=Viva,
        prompt=llm.render("viva.v1", code=sub.code)))
    attempt.viva = result.questions
    await session.commit()
    return result.questions


# --- instructor: code similarity ---------------------------------------------------------


async def _course_submissions(session: AsyncSession, course_id: int, problem_id: str,
                              dim: int) -> dict[int, Submission]:
    """Latest judged submission of each enrolled student on the problem."""
    students = select(Enrollment.user_id).where(Enrollment.course_id == course_id)
    latest: dict[int, Submission] = {}
    for sub in await session.scalars(
            select(Submission).where(Submission.user_id.in_(students),
                                     Submission.problem_id == problem_id, Submission.dim == dim,
                                     Submission.status == "done")
            .order_by(Submission.created_at)):
        latest[sub.user_id] = sub
    return {s.id: s for s in latest.values()}


@router.get("/courses/{course_id}/similarity", response_model=list[SimilarPair])
async def similar(course_id: int, problem_id: str, dim: int, user: CurrentUser,
                  session: Session) -> list[SimilarPair]:
    """Pairs of students' code worth a look. Not a verdict, and not AI detection."""
    await teaching(session, course_id, user)
    subs = await _course_submissions(session, course_id, problem_id, dim)
    starters = {name: templates.source(name) for name in templates.TEMPLATES}
    pairs = await asyncio.to_thread(similarity.similar_pairs,
                                    [(i, s.code) for i, s in subs.items()], starters)
    return [SimilarPair(**p, a_name=subs[p["a"]].user.name, b_name=subs[p["b"]].user.name)
            for p in pairs]


@router.post("/courses/{course_id}/similarity/opinion", response_model=SimilarityOpinion)
async def opinion(course_id: int, body: OpinionIn, user: CurrentUser, session: Session
                  ) -> SimilarityOpinion:
    """Optional second opinion from the language model on one pair."""
    await teaching(session, course_id, user)
    students = set(await session.scalars(select(Enrollment.user_id).where(
        Enrollment.course_id == course_id)))
    a, b = await session.get(Submission, body.a), await session.get(Submission, body.b)
    if a is None or b is None or not {a.user_id, b.user_id} <= students:
        raise HTTPException(404, "Submission not found in this course")
    scores = await asyncio.to_thread(similarity.compare, a.code, b.code)
    result: SimilarityOpinion = await guarded(lambda: llm.ask(
        session, feature="similarity", user_id=user.id, schema=SimilarityOpinion,
        prompt=llm.render("similarity.v1", scores=json.dumps(scores), a=a.code, b=b.code)))
    return result
