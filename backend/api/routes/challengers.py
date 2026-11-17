"""Evolving AI challengers. Anyone can follow one; only admins start or steer them."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ai.challenger import champion, history, running
from db.models import Challenger, Problem

from ..deps import AdminUser, Enqueue, Session
from ..schemas import ActiveIn, ChallengerDetail, ChallengerIn, ChallengerOut, GenerationOut

router = APIRouter(prefix="/challengers", tags=["challengers"])


async def _out(session: AsyncSession, c: Challenger, detail: bool = False) -> ChallengerDetail:
    gens = await history(session, c)
    best = champion(gens)
    return ChallengerDetail(
        id=c.id, problem_id=c.problem_id, dim=c.dim, active=c.active, generations=len(gens),
        running=running(gens),
        best_score=best.submission.score if best and best.submission else None,
        history=[GenerationOut(
            number=g.number, status=g.status, approach=g.approach, changes=g.changes,
            error=g.error, submission_id=g.submission_id, created_at=g.created_at,
            score=g.submission.score if g.status == "done" and g.submission else None,
            is_champion=g is best) for g in gens] if detail else [])


async def _get(session: AsyncSession, challenger_id: int) -> Challenger:
    challenger = await session.get(Challenger, challenger_id)
    if challenger is None:
        raise HTTPException(404, "Challenger not found")
    return challenger


@router.get("", response_model=list[ChallengerOut])
async def list_challengers(session: Session, problem_id: str | None = None,
                           dim: int | None = None) -> list[ChallengerDetail]:
    query = select(Challenger).order_by(Challenger.problem_id, Challenger.dim)
    if problem_id:
        query = query.where(Challenger.problem_id == problem_id)
    if dim:
        query = query.where(Challenger.dim == dim)
    return [await _out(session, c) for c in await session.scalars(query)]


@router.get("/{challenger_id}", response_model=ChallengerDetail)
async def get_challenger(challenger_id: int, session: Session) -> ChallengerDetail:
    return await _out(session, await _get(session, challenger_id), detail=True)


@router.post("", response_model=ChallengerOut, status_code=201)
async def start(body: ChallengerIn, _: AdminUser, session: Session, enqueue: Enqueue
                ) -> ChallengerDetail:
    """Creates the challenger and queues its first generation."""
    problem = await session.get(Problem, body.problem_id)
    if problem is None or body.dim not in problem.dims:
        raise HTTPException(404, "Problem or dimension not found")
    challenger = Challenger(problem_id=problem.id, dim=body.dim)
    session.add(challenger)
    try:
        await session.commit()
    except IntegrityError:
        raise HTTPException(409, "This problem and dimension already have a challenger") from None
    await enqueue("evolve_challenger", challenger.id)
    return await _out(session, challenger)


@router.patch("/{challenger_id}", response_model=ChallengerOut)
async def set_active(challenger_id: int, body: ActiveIn, _: AdminUser, session: Session
                     ) -> ChallengerDetail:
    """Inactive challengers keep their entry but are skipped by the daily job."""
    challenger = await _get(session, challenger_id)
    challenger.active = body.is_active
    await session.commit()
    return await _out(session, challenger)


@router.post("/{challenger_id}/evolve", response_model=ChallengerOut, status_code=202)
async def evolve_now(challenger_id: int, _: AdminUser, session: Session, enqueue: Enqueue
                     ) -> ChallengerDetail:
    challenger = await _get(session, challenger_id)
    if running(await history(session, challenger)):
        raise HTTPException(409, "A generation is already running")
    await enqueue("evolve_challenger", challenger.id)
    return await _out(session, challenger)
