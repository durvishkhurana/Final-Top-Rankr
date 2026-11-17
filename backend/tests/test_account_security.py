import re
from email.message import EmailMessage

import pytest
from httpx import AsyncClient

from core import mail
from core.config import get_settings

from .test_api import PASSWORD, RANDOM, other_client, signup

pytestmark = pytest.mark.anyio


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    sent: list[EmailMessage] = []
    monkeypatch.setattr(mail, "_deliver", sent.append)
    return sent


def token(message: EmailMessage, page: str) -> str:
    found = re.search(rf"/{page}\?token=(\S+)", message.get_content())
    assert found, message.get_content()
    return found.group(1)


async def login(client: AsyncClient, password: str = PASSWORD) -> int:
    r = await client.post("/api/auth/login", json={"email": "ada@example.com",
                                                   "password": password})
    return r.status_code


async def test_signup_sends_a_link_that_confirms_the_email(
    client: AsyncClient, outbox: list[EmailMessage]
) -> None:
    me = await signup(client, "ada")
    assert not me["email_verified"]
    assert [m["To"] for m in outbox] == ["ada@example.com"]
    link = token(outbox[0], "verify-email")

    assert (await client.post("/api/auth/verify", json={"token": "junk"})).status_code == 400
    # a reset link cannot be used to verify, nor the other way round
    r = await client.post("/api/auth/password/reset", json={"token": link, "password": "x" * 8})
    assert r.status_code == 400
    async with await other_client() as anyone:  # the link works without signing in
        r = await anyone.post("/api/auth/verify", json={"token": link})
    assert r.status_code == 200 and r.json()["email_verified"]
    assert (await client.get("/api/auth/me")).json()["email_verified"]
    # nothing more is sent once the address is confirmed
    assert (await client.post("/api/auth/verify/resend")).status_code == 204
    assert len(outbox) == 1


async def test_resending_is_limited_per_hour(
    client: AsyncClient, outbox: list[EmailMessage]
) -> None:
    await signup(client, "ada")
    assert (await client.post("/api/auth/verify/resend")).status_code == 204
    assert (await client.post("/api/auth/verify/resend")).status_code == 204
    assert (await client.post("/api/auth/verify/resend")).status_code == 429
    assert len(outbox) == 3


async def test_repeated_wrong_passwords_lock_sign_in(client: AsyncClient) -> None:
    await signup(client, "ada")
    await client.post("/api/auth/logout")
    for _ in range(get_settings().login_max_failures):
        assert await login(client, "wrong-password") == 401
    assert await login(client) == 429  # even the right password, until the window passes
    # unknown accounts are limited the same way, so a lock does not reveal an account
    for _ in range(get_settings().login_max_failures):
        r = await client.post("/api/auth/login", json={"email": "no@example.com",
                                                       "password": PASSWORD})
        assert r.status_code == 401
    r = await client.post("/api/auth/login", json={"email": "no@example.com",
                                                   "password": PASSWORD})
    assert r.status_code == 429 and "Retry-After" in r.headers


async def test_a_success_clears_earlier_failures(client: AsyncClient) -> None:
    await signup(client, "ada")
    for _ in range(get_settings().login_max_failures - 1):
        assert await login(client, "wrong-password") == 401
    assert await login(client) == 200
    for _ in range(get_settings().login_max_failures - 1):
        assert await login(client, "wrong-password") == 401
    assert await login(client) == 200


async def test_password_reset(client: AsyncClient, outbox: list[EmailMessage]) -> None:
    await signup(client, "ada")
    outbox.clear()
    async with await other_client() as stranger:
        r = await stranger.post("/api/auth/password/forgot", json={"email": "no@example.com"})
        assert r.status_code == 204 and not outbox  # same answer, nothing sent
        for _ in range(get_settings().login_max_failures):
            await login(stranger, "wrong-password")
        assert await login(stranger) == 429
        r = await stranger.post("/api/auth/password/forgot", json={"email": "ADA@example.com"})
        assert r.status_code == 204
        link = token(outbox[0], "reset-password")

        short = {"token": link, "password": "short"}
        assert (await stranger.post("/api/auth/password/reset", json=short)).status_code == 422
        new = {"token": link, "password": "a brand new password"}
        assert (await stranger.post("/api/auth/password/reset", json=new)).status_code == 204
        # the link works once: the new password changes its fingerprint
        assert (await stranger.post("/api/auth/password/reset", json=new)).status_code == 400
        assert await login(stranger, PASSWORD) == 401  # the lock was lifted
        assert await login(stranger, "a brand new password") == 200
        assert (await stranger.get("/api/auth/me")).json()["email_verified"]

    # the session that was open before the reset is signed out
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_verified_email_can_be_required(
    client: AsyncClient, outbox: list[EmailMessage], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "require_verified_email", True)
    await signup(client, "ada")
    body = {"problem_id": "STD-001", "dim": 5, "code": RANDOM}
    r = await client.post("/api/submissions", json=body)
    assert r.status_code == 403 and "Confirm your email" in r.json()["detail"]
    await client.post("/api/auth/verify", json={"token": token(outbox[0], "verify-email")})
    assert (await client.post("/api/submissions", json=body)).status_code == 201
