from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

ROLES = ("student", "instructor", "admin")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="student")
    country: Mapped[str] = mapped_column(String(80), default="")
    institution: Mapped[str] = mapped_column(String(150), default="")
    bio: Mapped[str] = mapped_column(String(500), default="")
    is_bot: Mapped[bool] = mapped_column(default=False)  # baseline entries
    is_demo: Mapped[bool] = mapped_column(default=False)  # seeded demo data, wiped by reset
    email_verified: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthEvent(Base):
    """Rate-limited account events (failed sign-in, emails sent), keyed by email."""

    __tablename__ = "auth_events"
    __table_args__ = (Index("ix_auth_events_lookup", "kind", "email", "at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # login_failed | verify_sent | reset_sent
    email: Mapped[str] = mapped_column(String(320))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Problem(Base):
    """Public catalogue entry. The function itself lives in judge.functions only."""

    __tablename__ = "problems"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))
    level: Mapped[str] = mapped_column(String(20))
    tags: Mapped[list[str]] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    dims: Mapped[list[int]] = mapped_column(JSON)
    bound: Mapped[float]
    kind: Mapped[str] = mapped_column(String(20), default="function", server_default="function")
    is_active: Mapped[bool] = mapped_column(default=True)
    # Search box of contributed problems; None: the box is [-bound, bound]
    lower: Mapped[float | None]
    upper: Mapped[float | None]


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        Index("ix_submissions_board", "problem_id", "dim", "status"),
        Index("ix_submissions_user", "user_id", "problem_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"))
    dim: Mapped[int]
    contest_id: Mapped[int | None] = mapped_column(ForeignKey("contests.id"), index=True)
    code: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|done|failed
    error: Mapped[str] = mapped_column(Text, default="")
    budget: Mapped[int | None]
    score: Mapped[float | None]
    aocc: Mapped[float | None]
    iqr: Mapped[float | None]
    median_precision: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")
    runs: Mapped[list["Run"]] = relationship(back_populates="submission",
                                             cascade="all, delete-orphan",
                                             order_by="Run.instance_seed, Run.seed")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"),
                                               index=True)
    instance_seed: Mapped[int]
    seed: Mapped[int]
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str] = mapped_column(Text, default="")
    evals: Mapped[int]
    f_best: Mapped[float | None]  # None when nothing was evaluated
    aocc: Mapped[float]
    precision: Mapped[float | None]
    wall_sec: Mapped[float]
    trace: Mapped[list[Any]] = mapped_column(JSON)  # best-so-far at scoring.checkpoints(budget)
    log: Mapped[str] = mapped_column(Text, default="")
    points: Mapped[list[Any] | None] = mapped_column(JSON)  # 2D demo problems only
    solution: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # decoded, real-world only

    submission: Mapped[Submission] = relationship(back_populates="runs")


class FRef(Base):
    """Best-known value per (problem, dim, instance) for problems without a known optimum."""

    __tablename__ = "f_refs"

    problem_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    dim: Mapped[int] = mapped_column(primary_key=True)
    instance_seed: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[float]


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    invite_code: Mapped[str] = mapped_column(String(20), unique=True)
    instructor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())


class Enrollment(Base):
    __tablename__ = "enrollments"

    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"),
                                           primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         primary_key=True)


class Contest(Base):
    __tablename__ = "contests"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    invite_code: Mapped[str | None] = mapped_column(String(20))  # None: open to everyone
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    tasks: Mapped[list[dict[str, Any]]] = mapped_column(JSON)  # [{problem_id, dim}]
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|finalising|final
    # AI coach in this contest: off | concept | specific
    hint_level: Mapped[str] = mapped_column(String(20), default="specific",
                                            server_default="specific")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())


class ContestEntry(Base):
    __tablename__ = "contest_entries"

    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id", ondelete="CASCADE"),
                                            primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         primary_key=True)


class FinalResult(Base):
    """Score of a participant's best contest submission re-run on held-out instances."""

    __tablename__ = "final_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id", ondelete="CASCADE"),
                                            index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    problem_id: Mapped[str] = mapped_column(String(20))
    dim: Mapped[int]
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"))
    score: Mapped[float]
    aocc: Mapped[float]
    iqr: Mapped[float]
    median_precision: Mapped[float | None]
    # per run: {instance (0-based index, not the seed), seed, status, aocc, precision}
    runs: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class LlmCall(Base):
    """Every request to a language model, including answers served from the cache."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    feature: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"),
                                                index=True)
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    ok: Mapped[bool]
    cached: Mapped[bool]
    response: Mapped[str] = mapped_column(Text, default="")
    tokens_in: Mapped[int] = mapped_column(default=0)
    tokens_out: Mapped[int] = mapped_column(default=0)
    latency_ms: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(), index=True)


class AiNote(Base):
    """An AI answer about a submission (analysis or coach), generated once."""

    __tablename__ = "ai_notes"
    __table_args__ = (UniqueConstraint("submission_id", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())


class Challenger(Base):
    """An AI-written optimizer on one problem and dimension that improves itself one
    generation at a time. Its best generation is its leaderboard entry."""

    __tablename__ = "challengers"
    __table_args__ = (UniqueConstraint("problem_id", "dim"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    dim: Mapped[int]
    active: Mapped[bool] = mapped_column(default=True)  # evolved by the daily job
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())


class Generation(Base):
    """One attempt of a challenger: running -> done | failed."""

    __tablename__ = "challenger_generations"
    __table_args__ = (UniqueConstraint("challenger_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    challenger_id: Mapped[int] = mapped_column(ForeignKey("challengers.id", ondelete="CASCADE"),
                                               index=True)
    number: Mapped[int]
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("challenger_generations.id", ondelete="SET NULL"))
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="running")
    approach: Mapped[str] = mapped_column(Text, default="")
    changes: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())

    submission: Mapped[Submission | None] = relationship(lazy="joined")


class Contribution(Base):
    """A proposed fitness function: testing -> pending | failed -> approved | rejected."""

    __tablename__ = "contributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    lower: Mapped[float]
    upper: Mapped[float]
    dims: Mapped[list[int]] = mapped_column(JSON)
    level: Mapped[str] = mapped_column(String(20))
    tags: Mapped[list[str]] = mapped_column(JSON)
    ai_built: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20), default="testing")
    smoke: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    problem_id: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())


class Exam(Base):
    """A course test ("test" in the interface). draft -> live -> closed."""

    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"),
                                           index=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    camera_checks: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())


class Question(Base):
    """kind mcq: data {choices, correct}; numeric: {generator}; reasoning: {problem_id,
    dim, rubric, pool, follow_up}. The prompt of numeric and reasoning questions has
    {placeholders} filled per student."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    position: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))
    prompt: Mapped[str] = mapped_column(Text)
    points: Mapped[float] = mapped_column(default=1.0)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    pool_approved: Mapped[bool] = mapped_column(default=False)


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("exam_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    camera_consent: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # |submitted|graded
    total: Mapped[float | None]
    viva: Mapped[list[str] | None] = mapped_column(JSON)  # instructor only
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"),
                                            index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    prompt: Mapped[str] = mapped_column(Text)  # as shown to this student
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"))  # reasoning: the run asked about
    response: Mapped[str] = mapped_column(Text, default="")
    follow_up: Mapped[str] = mapped_column(Text, default="")
    follow_up_response: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float | None]
    max_score: Mapped[float]
    rationale: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float | None]
    graded_by: Mapped[str] = mapped_column(String(20), default="")  # code | ai | instructor
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    time_ms: Mapped[int] = mapped_column(default=0)
    paste_chars: Mapped[int] = mapped_column(default=0)


class GradeEvent(Base):
    """Audit log: every grade an answer has had, and who gave it."""

    __tablename__ = "grade_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"),
                                           index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    old_score: Mapped[float | None]
    new_score: Mapped[float | None]
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())


class IntegrityEvent(Base):
    """One browser-side signal during a test. Deleted after the retention period."""

    __tablename__ = "integrity_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"),
                                            index=True)
    kind: Mapped[str] = mapped_column(String(30))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # browser clock
    duration_ms: Mapped[int] = mapped_column(default=0)
    detail: Mapped[str] = mapped_column(String(200), default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now(), index=True)
