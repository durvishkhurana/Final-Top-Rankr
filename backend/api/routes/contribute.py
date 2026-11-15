import base64
import binascii

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ai import llm
from ai.features import BuiltProblem
from db.contributed import register
from db.models import Contribution, Problem

from ..deps import AdminUser, CurrentUser, Enqueue, Session
from ..schemas import BuildIn, ContributionIn, ContributionOut
from .ai import guarded

router = APIRouter(tags=["contribute"])

MAX_IMAGE_BYTES = 2_000_000


def _check(lower: float, upper: float, dims: list[int]) -> None:
    if not lower < upper:
        raise HTTPException(422, "The lower bound must be below the upper bound")
    if any(d < 2 or d > 100 for d in dims) or len(set(dims)) != len(dims):
        raise HTTPException(422, "Dimensions must be distinct and between 2 and 100")


@router.post("/contributions", response_model=ContributionOut, status_code=201)
async def contribute(body: ContributionIn, user: CurrentUser, session: Session,
                     enqueue: Enqueue) -> Contribution:
    """Proposes a fitness function. It is smoke-tested in a sandbox container and then
    waits for an admin to approve it."""
    _check(body.lower, body.upper, body.dims)
    item = Contribution(user_id=user.id, **body.model_dump())
    session.add(item)
    await session.commit()
    await enqueue("smoke_contribution", item.id)
    return item


@router.post("/contributions/build", response_model=ContributionOut, status_code=201)
async def build(body: BuildIn, user: CurrentUser, session: Session, enqueue: Enqueue
                ) -> Contribution:
    """Drafts a problem from a description in words, optionally with an image of the
    formula. The draft goes through the same smoke test and admin approval."""
    image = None
    if body.image_base64:
        try:
            image = base64.b64decode(body.image_base64, validate=True)
        except binascii.Error:
            raise HTTPException(422, "The image is not valid base64") from None
        if len(image) > MAX_IMAGE_BYTES or body.image_mime not in ("image/png", "image/jpeg"):
            raise HTTPException(422, "The image must be a PNG or JPEG of at most 2 MB")
    built: BuiltProblem = await guarded(lambda: llm.ask(
        session, feature="problem_builder", user_id=user.id, schema=BuiltProblem,
        prefer="gemini", image=image, image_mime=body.image_mime,
        prompt=llm.render("problem_builder.v1", text=body.text)))
    _check(built.lower, built.upper, built.dims)
    item = Contribution(user_id=user.id, ai_built=True, **built.model_dump())
    session.add(item)
    await session.commit()
    await enqueue("smoke_contribution", item.id)
    return item


@router.get("/contributions", response_model=list[ContributionOut])
async def mine(user: CurrentUser, session: Session) -> list[Contribution]:
    return list(await session.scalars(select(Contribution).where(
        Contribution.user_id == user.id).order_by(Contribution.id.desc())))


@router.get("/admin/contributions", response_model=list[ContributionOut])
async def all_contributions(_: AdminUser, session: Session) -> list[Contribution]:
    return list(await session.scalars(select(Contribution).order_by(Contribution.id.desc())))


@router.post("/admin/contributions/{item_id}/{decision}", response_model=ContributionOut)
async def decide(item_id: int, decision: str, _: AdminUser, session: Session) -> Contribution:
    item = await session.get(Contribution, item_id)
    if item is None or decision not in ("approve", "reject"):
        raise HTTPException(404, "Contribution not found")
    if item.status != "pending":
        raise HTTPException(409, "Only a contribution that passed its smoke test and is "
                                 "waiting for review can be decided")
    if decision == "reject":
        item.status = "rejected"
    else:
        item.status, item.problem_id = "approved", f"C-{item.id:03d}"
        session.add(Problem(
            id=item.problem_id, name=item.name, category="Contributed", level=item.level,
            tags=item.tags, summary=item.summary, description=item.description,
            dims=item.dims, bound=(item.upper - item.lower) / 2, lower=item.lower,
            upper=item.upper, kind="function"))
        register(item)
    await session.commit()
    return item
