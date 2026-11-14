from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
    is_active: Mapped[bool] = mapped_column(default=True)


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

    submission: Mapped[Submission] = relationship(back_populates="runs")


class FRef(Base):
    """Best-known value per (problem, dim, instance) for problems without a known optimum."""

    __tablename__ = "f_refs"

    problem_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    dim: Mapped[int] = mapped_column(primary_key=True)
    instance_seed: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[float]
