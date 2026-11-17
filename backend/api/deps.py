from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.security import read_token
from db.base import get_session
from db.models import User

Session = Annotated[AsyncSession, Depends(get_session)]


async def optional_user(request: Request, session: Session) -> User | None:
    payload = read_token(request.cookies.get("access_token", ""), "access")
    if payload is None:
        return None
    return await session.get(User, int(payload["sub"]))


async def current_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise HTTPException(401, "Not signed in")
    return user


async def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Admins only")
    return user


async def verified_user(user: Annotated[User, Depends(current_user)]) -> User:
    if get_settings().require_verified_email and not user.email_verified:
        raise HTTPException(403, "Confirm your email address first; the link is in your inbox")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
VerifiedUser = Annotated[User, Depends(verified_user)]
OptionalUser = Annotated[User | None, Depends(optional_user)]
AdminUser = Annotated[User, Depends(admin_user)]

EnqueueFn = Callable[[str, int], Awaitable[None]]


def get_enqueue(request: Request) -> EnqueueFn:
    async def enqueue(job: str, target_id: int) -> None:
        await request.app.state.queue.enqueue_job(job, target_id)

    return enqueue


Enqueue = Annotated[EnqueueFn, Depends(get_enqueue)]
