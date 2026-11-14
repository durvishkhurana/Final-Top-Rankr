from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from core.config import get_settings
from core.security import hash_password, make_token, read_token, verify_password
from db.models import RefreshToken, User

from ..deps import CurrentUser, Session
from ..schemas import LoginIn, Me, SignupIn

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_PATH = "/api/auth"


async def _start_session(response: Response, session: Session, user: User) -> None:
    s = get_settings()
    access, _, _ = make_token(user.id, "access", timedelta(minutes=s.jwt_access_ttl_min))
    refresh, jti, expires = make_token(user.id, "refresh", timedelta(days=s.jwt_refresh_ttl_days))
    session.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires))
    await session.commit()
    common = {"httponly": True, "secure": s.secure_cookies, "samesite": "lax"}
    response.set_cookie("access_token", access, max_age=s.jwt_access_ttl_min * 60, path="/",
                        **common)  # type: ignore[arg-type]
    response.set_cookie("refresh_token", refresh, max_age=s.jwt_refresh_ttl_days * 86400,
                        path=REFRESH_PATH, **common)  # type: ignore[arg-type]


def _clear(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path=REFRESH_PATH)


@router.post("/signup", response_model=Me, status_code=201)
async def signup(body: SignupIn, response: Response, session: Session) -> User:
    user = User(email=body.email.lower(), name=body.name.strip(),
                password_hash=hash_password(body.password),
                country=body.country.strip(), institution=body.institution.strip())
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(409, "An account with this email already exists") from None
    await _start_session(response, session, user)
    return user


@router.post("/login", response_model=Me)
async def login(body: LoginIn, response: Response, session: Session) -> User:
    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or user.is_bot or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    await _start_session(response, session, user)
    return user


@router.post("/refresh", response_model=Me)
async def refresh(request: Request, response: Response, session: Session) -> User:
    payload = read_token(request.cookies.get("refresh_token", ""), "refresh")
    if payload is None:
        raise HTTPException(401, "Session expired")
    # A refresh token works once: deleting its row is the check and the rotation.
    used = await session.execute(delete(RefreshToken).where(RefreshToken.jti == payload["jti"]))
    user = await session.get(User, int(payload["sub"]))
    if used.rowcount != 1 or user is None:  # type: ignore[attr-defined]
        raise HTTPException(401, "Session expired")
    await _start_session(response, session, user)
    return user


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, session: Session) -> None:
    payload = read_token(request.cookies.get("refresh_token", ""), "refresh")
    if payload:
        await session.execute(delete(RefreshToken).where(RefreshToken.jti == payload["jti"]))
        await session.commit()
    _clear(response)


@router.get("/me", response_model=Me)
async def me(user: CurrentUser) -> User:
    return user
