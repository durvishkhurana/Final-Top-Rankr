import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from core import mail
from core.config import get_settings
from core.security import hash_password, make_token, read_token, verify_password
from db.models import AuthEvent, RefreshToken, User

from ..deps import CurrentUser, Session
from ..schemas import EmailIn, LoginIn, Me, ResetIn, SignupIn, TokenIn

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_PATH = "/api/auth"
# Emailed links: lifetime, page they open, and how many may be sent per hour
LINKS = {
    "verify": (timedelta(days=2), "verify-email", "Confirm your TopRanker email address",
               "Open this link to confirm your email address:"),
    "reset": (timedelta(hours=1), "reset-password", "Reset your TopRanker password",
              "Open this link within an hour to choose a new password. If you did not ask "
              "for this, ignore this email; your password stays the same."),
}
LINKS_PER_HOUR = 3


async def _recent(session: Session, kind: str, email: str, window: timedelta) -> int:
    since = datetime.now(UTC) - window
    return await session.scalar(select(func.count()).select_from(AuthEvent).where(
        AuthEvent.kind == kind, AuthEvent.email == email, AuthEvent.at >= since)) or 0


def _fingerprint(user: User) -> str:
    """Changes when the email or password changes, which voids every earlier link."""
    return hashlib.sha256(f"{user.email}\0{user.password_hash}".encode()).hexdigest()[:16]


async def _send_link(session: Session, user: User, purpose: str) -> bool:
    """Emails a verify or reset link. False if the hourly limit was reached."""
    kind = f"{purpose}_sent"
    if await _recent(session, kind, user.email, timedelta(hours=1)) >= LINKS_PER_HOUR:
        return False
    ttl, page, subject, text = LINKS[purpose]
    token, _, _ = make_token(user.id, purpose, ttl, fp=_fingerprint(user))
    session.add(AuthEvent(kind=kind, email=user.email))
    await session.commit()
    link = f"{get_settings().frontend_url}/{page}?token={token}"
    await mail.send(user.email, subject, f"Hello {user.name},\n\n{text}\n\n{link}\n")
    return True


async def _link_user(session: Session, token: str, purpose: str) -> User:
    payload = read_token(token, purpose)
    user = await session.get(User, int(payload["sub"])) if payload else None
    if user is None or payload is None or payload.get("fp") != _fingerprint(user):
        raise HTTPException(400, "This link is invalid or has expired")
    return user


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
    await _send_link(session, user, "verify")
    return user


@router.post("/login", response_model=Me)
async def login(body: LoginIn, response: Response, session: Session) -> User:
    """After LOGIN_MAX_FAILURES wrong passwords for one email within LOGIN_WINDOW_MIN
    minutes, sign-in to that account is refused until the window has passed."""
    s = get_settings()
    email = body.email.lower()
    if await _recent(session, "login_failed", email,
                     timedelta(minutes=s.login_window_min)) >= s.login_max_failures:
        raise HTTPException(429, f"Too many failed sign-in attempts. Try again in "
                                 f"{s.login_window_min} minutes or reset your password.",
                            headers={"Retry-After": str(s.login_window_min * 60)})
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or user.is_bot or not verify_password(body.password, user.password_hash):
        session.add(AuthEvent(kind="login_failed", email=email))
        await session.commit()
        raise HTTPException(401, "Wrong email or password")
    await session.execute(delete(AuthEvent).where(AuthEvent.kind == "login_failed",
                                                  AuthEvent.email == email))
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


@router.post("/verify", response_model=Me)
async def verify_email(body: TokenIn, session: Session) -> User:
    user = await _link_user(session, body.token, "verify")
    user.email_verified = True
    await session.commit()
    return user


@router.post("/verify/resend", status_code=204)
async def resend_verification(user: CurrentUser, session: Session) -> None:
    if not user.email_verified and not await _send_link(session, user, "verify"):
        raise HTTPException(429, "Too many emails sent. Try again in an hour.")


@router.post("/password/forgot", status_code=204)
async def forgot_password(body: EmailIn, session: Session) -> None:
    """Always answers 204, so the response does not reveal whether an account exists."""
    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    if user is not None and not user.is_bot:
        await _send_link(session, user, "reset")


@router.post("/password/reset", status_code=204)
async def reset_password(body: ResetIn, response: Response, session: Session) -> None:
    """Sets a new password, signs the account out everywhere and lifts a sign-in lock.
    Opening the emailed link also proves the address, so it counts as verified."""
    user = await _link_user(session, body.token, "reset")
    user.password_hash = hash_password(body.password)
    user.email_verified = True
    await session.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await session.execute(delete(AuthEvent).where(AuthEvent.kind == "login_failed",
                                                  AuthEvent.email == user.email))
    await session.commit()
    _clear(response)
