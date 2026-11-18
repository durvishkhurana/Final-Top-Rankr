from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ai import llm
from ai.challenger import baseline_prompt
from ai.features import BaselineCode
from db.models import Problem, Submission, User
from db.seed import bot_user
from judge import baselines

from ..deps import AdminUser, Enqueue, Session
from ..schemas import ActiveIn, BaselinesIn, ProblemOut, RoleIn, SubmissionOut
from ..schemas import AdminUser as AdminUserOut
from .ai import guarded
from .submissions import _out

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users", response_model=list[AdminUserOut])
async def list_users(_: AdminUser, session: Session) -> list[User]:
    return list(await session.scalars(select(User).order_by(User.id).limit(500)))


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def set_role(user_id: int, body: RoleIn, admin: AdminUser, session: Session) -> User:
    user = await session.get(User, user_id)
    if user is None or user.is_bot:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "You cannot change your own role")
    user.role = body.role
    await session.commit()
    return user


@router.get("/problems", response_model=list[ProblemOut])
async def all_problems(_: AdminUser, session: Session) -> list[Problem]:
    return list(await session.scalars(select(Problem).order_by(Problem.id)))


@router.patch("/problems/{problem_id}", response_model=ProblemOut)
async def set_active(problem_id: str, body: ActiveIn, _: AdminUser, session: Session) -> Problem:
    problem = await session.get(Problem, problem_id)
    if problem is None:
        raise HTTPException(404, "Problem not found")
    problem.is_active = body.is_active
    await session.commit()
    return problem


@router.get("/submissions", response_model=list[SubmissionOut])
async def recent_submissions(_: AdminUser, session: Session) -> list[SubmissionOut]:
    subs = await session.scalars(select(Submission).order_by(Submission.id.desc()).limit(100))
    return [_out(s) for s in subs.unique()]


@router.post("/problems/{problem_id}/baselines", response_model=list[SubmissionOut],
             status_code=201)
async def run_baselines(problem_id: str, body: BaselinesIn, _: AdminUser, session: Session,
                        enqueue: Enqueue) -> list[SubmissionOut]:
    """Queues the three baselines on a problem and dimension as labelled bot entries."""
    problem = await session.get(Problem, problem_id)
    if problem is None or body.dim not in problem.dims:
        raise HTTPException(404, "Problem or dimension not found")
    subs = []
    for key in baselines.NAMES:
        bot = await bot_user(session, key)
        subs.append(Submission(user_id=bot.id, problem_id=problem_id, dim=body.dim,
                               code=baselines.source(key)))
    session.add_all(subs)
    await session.commit()
    for sub in subs:
        await session.refresh(sub)
        await enqueue("judge_submission", sub.id)
    return [_out(s) for s in subs]


@router.post("/problems/{problem_id}/ai-baseline", response_model=SubmissionOut,
             status_code=201)
async def ai_baseline(problem_id: str, body: BaselinesIn, admin: AdminUser, session: Session,
                      enqueue: Enqueue) -> SubmissionOut:
    """Asks the language model for an optimizer from the public description only, and
    queues it as a labelled bot entry. The code runs in the sandbox like any other."""
    problem = await session.get(Problem, problem_id)
    if problem is None or body.dim not in problem.dims:
        raise HTTPException(404, "Problem or dimension not found")
    answer: BaselineCode = await guarded(lambda: llm.ask(
        session, feature="ai_baseline", user_id=admin.id, schema=BaselineCode,
        prompt=baseline_prompt(problem, body.dim)))
    bot = await bot_user(session, "ai")
    sub = Submission(user_id=bot.id, problem_id=problem_id, dim=body.dim, code=answer.code)
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    await enqueue("judge_submission", sub.id)
    return _out(sub)
