from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth / users -----------------------------------------------------------------------


class SignupIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)
    country: str = Field(default="", max_length=80)
    institution: str = Field(default="", max_length=150)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    country: str | None = Field(default=None, max_length=80)
    institution: str | None = Field(default=None, max_length=150)
    bio: str | None = Field(default=None, max_length=500)


class Me(Model):
    id: int
    email: str
    name: str
    role: str
    country: str
    institution: str
    bio: str


class ProfileSubmission(Model):
    id: int
    problem_id: str
    dim: int
    status: str
    score: float | None
    created_at: datetime


class Profile(Model):
    id: int
    name: str
    role: str
    country: str
    institution: str
    bio: str
    created_at: datetime
    rating: float
    rank: int | None
    problems_attempted: int
    submissions: int
    recent: list[ProfileSubmission]


# --- problems ---------------------------------------------------------------------------


class ProblemOut(Model):
    id: str
    name: str
    category: str
    level: str
    tags: list[str]
    summary: str
    dims: list[int]
    bound: float
    kind: str
    is_active: bool
    submissions: int = 0


class ProblemDetail(ProblemOut):
    description: str


class Quota(BaseModel):
    daily_cap: int
    used_today: int
    remaining_today: int
    cooldown_sec: int
    wait_sec: int  # 0 when a submission is allowed now


class BoardRow(BaseModel):
    rank: int
    user_id: int
    name: str
    country: str
    institution: str
    is_baseline: bool
    submission_id: int
    score: float
    median_precision: float | None
    iqr: float | None
    submitted_at: datetime


class Curve(BaseModel):
    label: str
    is_baseline: bool
    submission_id: int
    median: list[float | None]  # median precision across runs at each checkpoint


class Curves(BaseModel):
    checkpoints: list[int]
    curves: list[Curve]


class ProblemView(BaseModel):
    """What may be shown of a public instance: the landscape of a 2D demo problem, or
    the data of a real-world problem. Hidden-function problems have no view."""

    kind: str
    lower: list[float]
    upper: list[float]
    grid: list[list[float]] | None = None  # precision on an n x n grid, row = y
    data: dict[str, Any] | None = None


class DayCount(BaseModel):
    day: str
    count: int


class Template(BaseModel):
    key: str
    name: str
    code: str


# --- submissions ------------------------------------------------------------------------


class SubmitIn(BaseModel):
    problem_id: str
    dim: int
    contest_id: int | None = None
    code: str = Field(min_length=1)


class RunOut(Model):
    instance_seed: int
    seed: int
    status: str
    error: str
    evals: int
    aocc: float
    precision: float | None
    wall_sec: float


class RunDetail(RunOut):
    # Precision at each checkpoint (best-so-far minus the reference value, floored at
    # 1e-8). Raw objective values are not exposed.
    precision_trace: list[float | None]
    log: str
    points: list[list[float]] | None  # evaluated points, 2D demo problems only
    solution: dict[str, Any] | None  # decoded best solution, real-world problems only


class SubmissionOut(Model):
    id: int
    user_id: int
    user_name: str
    problem_id: str
    dim: int
    contest_id: int | None
    status: str
    error: str
    budget: int | None
    score: float | None
    aocc: float | None
    iqr: float | None
    median_precision: float | None
    created_at: datetime
    finished_at: datetime | None


class SubmissionDetail(SubmissionOut):
    code: str
    checkpoints: list[int]
    runs: list[RunDetail]


# --- leaderboard / stats / admin --------------------------------------------------------


class GlobalRow(BaseModel):
    rank: int
    key: str  # user id, country or institution
    name: str
    country: str = ""
    institution: str = ""
    rating: float
    problems: int = 0
    members: int = 1


class ProblemCount(BaseModel):
    problem_id: str
    name: str
    count: int


class Stats(BaseModel):
    users: int
    problems: int
    submissions: int
    runs: int
    evaluations: int
    per_day: list[DayCount]
    per_problem: list[ProblemCount]
    by_status: dict[str, int]


class AdminUser(Model):
    id: int
    email: str
    name: str
    role: str
    is_bot: bool
    is_demo: bool
    created_at: datetime


class RoleIn(BaseModel):
    role: Literal["student", "instructor", "admin"]


class ActiveIn(BaseModel):
    is_active: bool


class BaselinesIn(BaseModel):
    dim: int


# --- contests and courses ---------------------------------------------------------------


class Task(BaseModel):
    problem_id: str
    dim: int


class ContestIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=5000)
    tasks: list[Task] = Field(min_length=1, max_length=20)
    starts_at: datetime
    ends_at: datetime
    invite_only: bool = False
    course_id: int | None = None


class ContestOut(BaseModel):
    id: int
    title: str
    description: str
    tasks: list[Task]
    starts_at: datetime
    ends_at: datetime
    phase: str  # upcoming | running | ended | finalising | final
    invite_only: bool
    course_id: int | None
    participants: int
    joined: bool
    can_manage: bool
    invite_code: str | None  # organiser only


class JoinIn(BaseModel):
    code: str = Field(default="", max_length=40)


class ContestBoardRow(BaseModel):
    rank: int
    user_id: int
    name: str
    is_baseline: bool
    total: float
    scores: dict[str, float]  # "problem@dim" -> score
    final: bool  # True: scores are from held-out instances


class CourseIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=5000)


class CourseOut(BaseModel):
    id: int
    title: str
    description: str
    instructor: str
    students: int
    teaches: bool
    invite_code: str | None  # instructor only


class DashboardStudent(BaseModel):
    user_id: int
    name: str
    email: str
    scores: dict[str, float | None]  # column key -> best public score
    submissions: int
    last_active: datetime | None


class Dashboard(BaseModel):
    course: CourseOut
    columns: list[dict[str, Any]]  # {key, contest, contest_id, problem_id, dim}
    students: list[DashboardStudent]
