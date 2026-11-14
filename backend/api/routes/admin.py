from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from db.models import Problem, Submission, User
from judge import baselines

from ..deps import AdminUser, Enqueue, Session
from ..schemas import ActiveIn, BaselinesIn, ProblemOut, RoleIn, SubmissionOut
from ..schemas import AdminUser as AdminUserOut
from .submissions import _out

router = APIRouter(prefix="/admin", tags=["admin"])

BASELINE_NAMES = {
    "random_search": "Random search",
    "differential_evolution": "Differential evolution (SciPy)",
    "cmaes": "CMA-ES",
}


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


async def baseline_user(session: Session, key: str) -> User:
    email = f"{key}@baseline.invalid"
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=f"{BASELINE_NAMES[key]} (baseline)", password_hash="!",
                    is_bot=True)
        session.add(user)
        await session.flush()
    return user


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
        bot = await baseline_user(session, key)
        subs.append(Submission(user_id=bot.id, problem_id=problem_id, dim=body.dim,
                               code=baselines.source(key)))
    session.add_all(subs)
    await session.commit()
    for sub in subs:
        await session.refresh(sub)
        await enqueue(sub.id)
    return [_out(s) for s in subs]
