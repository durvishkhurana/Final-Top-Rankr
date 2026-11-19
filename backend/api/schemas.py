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


class EmailIn(BaseModel):
    email: EmailStr


class TokenIn(BaseModel):
    token: str = Field(max_length=1000)


class ResetIn(TokenIn):
    password: str = Field(min_length=8, max_length=200)


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
    email_verified: bool


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
    hint_level: Literal["off", "concept", "specific"] = "specific"


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
    hint_level: str
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


# --- AI features and contributions ------------------------------------------------------


class AiStatus(BaseModel):
    enabled: bool
    remaining_today: int


class NoteOut(Model):
    kind: str
    content: dict[str, Any]
    created_at: datetime


class ContributionIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=5000)
    source: str = Field(min_length=1, max_length=50_000)
    lower: float
    upper: float
    dims: list[int] = Field(min_length=1, max_length=3)
    level: Literal["Easy", "Medium", "Hard"] = "Medium"
    tags: list[str] = Field(default_factory=list, max_length=4)


class BuildIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    image_base64: str = Field(default="", max_length=3_000_000)
    image_mime: str = "image/png"


class ContributionOut(Model):
    id: int
    user_id: int
    name: str
    summary: str
    description: str
    source: str
    lower: float
    upper: float
    dims: list[int]
    level: str
    tags: list[str]
    ai_built: bool
    status: str
    smoke: dict[str, Any] | None
    problem_id: str | None
    created_at: datetime


# --- course tests -------------------------------------------------------------------------


class ExamIn(BaseModel):
    course_id: int
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=5000)
    starts_at: datetime
    ends_at: datetime
    camera_checks: bool = True


class ExamPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    camera_checks: bool | None = None
    status: Literal["draft", "live", "closed"] | None = None


class MyAttempt(BaseModel):
    id: int
    status: str
    total: float | None


class ExamOut(BaseModel):
    id: int
    course_id: int
    course_title: str
    title: str
    description: str
    starts_at: datetime
    ends_at: datetime
    camera_checks: bool
    status: str
    questions: int
    max_total: float
    teaches: bool
    attempt: MyAttempt | None


class QuestionIn(BaseModel):
    kind: Literal["mcq", "numeric", "reasoning"]
    prompt: str = Field(min_length=1, max_length=4000)
    points: float = Field(default=1.0, gt=0, le=100)
    data: dict[str, Any] = Field(default_factory=dict)


class QuestionOut(Model):
    """Instructor view, including correct answers."""
    id: int
    position: int
    kind: str
    prompt: str
    points: float
    data: dict[str, Any]
    pool_approved: bool


class PoolIn(BaseModel):
    pool: list[str] = Field(min_length=1, max_length=30)


class StartIn(BaseModel):
    consent: bool
    camera_consent: bool = False


class AnswerView(BaseModel):
    """Student view: never includes a correct answer or a grade before the test closes."""
    id: int
    question_id: int
    kind: str
    prompt: str
    choices: list[str] | None
    max_score: float
    response: str
    follow_up: str
    follow_up_response: str
    score: float | None
    rationale: str


class AttemptOut(BaseModel):
    id: int
    exam: ExamOut
    status: str
    camera_consent: bool
    total: float | None
    answers: list[AnswerView]


class AnswerIn(BaseModel):
    response: str = Field(max_length=5000)
    time_ms: int = Field(default=0, ge=0, le=86_400_000)
    paste_chars: int = Field(default=0, ge=0, le=1_000_000)


class FollowUpIn(BaseModel):
    response: str = Field(max_length=5000)


class SaveOut(BaseModel):
    follow_up: str


INTEGRITY_KINDS = Literal["tab_hidden", "window_blur", "fullscreen_exit", "copy", "paste",
                          "no_face", "multiple_faces", "head_turned", "camera_unavailable"]


class EventIn(BaseModel):
    kind: INTEGRITY_KINDS
    at: datetime
    duration_ms: int = Field(default=0, ge=0, le=86_400_000)
    detail: str = Field(default="", max_length=200)


class GradeIn(BaseModel):
    score: float = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)


class GradeEventOut(Model):
    actor: str
    old_score: float | None
    new_score: float | None
    reason: str
    created_at: datetime


class AnswerResult(BaseModel):
    id: int
    question_id: int
    kind: str
    prompt: str
    response: str
    follow_up: str
    follow_up_response: str
    correct: str | None  # mcq / numeric: computed by code
    score: float | None
    max_score: float
    rationale: str
    confidence: float | None
    graded_by: str
    flags: list[str]
    time_ms: int
    paste_chars: int
    submission_id: int | None
    history: list[GradeEventOut]


class EventOut(Model):
    kind: str
    at: datetime
    duration_ms: int
    detail: str


class AttemptResult(BaseModel):
    id: int
    user_id: int
    name: str
    status: str
    camera_consent: bool
    total: float | None
    started_at: datetime
    submitted_at: datetime | None
    viva: list[str] | None
    answers: list[AnswerResult]
    events: list[EventOut]


class SimilarPair(BaseModel):
    a: int
    b: int
    a_name: str
    b_name: str
    token: float
    structure: float
    similarity: float


class OpinionIn(BaseModel):
    a: int
    b: int


# --- research ---------------------------------------------------------------------------


class ComparedEntry(BaseModel):
    submission_id: int
    label: str
    is_baseline: bool
    score: float
    runs: int
    mean: float  # of per-run AOCC
    median: float
    ci_low: float  # 95% bootstrap interval of the mean
    ci_high: float
    mean_rank: float | None = None  # over the shared (instance, seed) runs; 1 is best
    ecdf: list[float]  # fraction of (run, target) pairs reached, per checkpoint


class PairTest(BaseModel):
    a: int
    b: int
    p: float  # Mann-Whitney U, two-sided
    p_holm: float
    a12: float  # probability that a run of a beats a run of b
    significant: bool
    better: int | None


class Comparison(BaseModel):
    problem_id: str
    dim: int
    targets: list[float]
    checkpoints: list[int]
    entries: list[ComparedEntry]
    pairs: list[PairTest]
    blocks: int
    friedman_p: float | None
    alpha: float


class WriteUpOut(BaseModel):
    text: str


# --- AI challenger ----------------------------------------------------------------------


class ChallengerIn(BaseModel):
    problem_id: str
    dim: int


class GenerationOut(BaseModel):
    number: int
    status: str  # running | done | failed
    approach: str
    changes: str
    error: str
    submission_id: int | None
    score: float | None
    is_champion: bool
    parent: int | None  # number of the generation it was written from
    created_at: datetime


class ChallengerOut(BaseModel):
    id: int
    problem_id: str
    dim: int
    active: bool
    generations: int
    running: bool
    best_score: float | None


class ChallengerDetail(ChallengerOut):
    history: list[GenerationOut]
