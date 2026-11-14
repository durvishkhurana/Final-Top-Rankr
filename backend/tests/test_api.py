from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from worker.main import judge_submission

from api.main import app
from core.config import get_settings
from db.models import FRef, Submission, User
from judge import baselines, templates
from judge.scoring import checkpoints

pytestmark = pytest.mark.anyio

RANDOM = templates.source("random_search")
PASSWORD = "correct horse battery"


async def signup(client: AsyncClient, name: str, **extra: str) -> dict[str, Any]:
    r = await client.post("/api/auth/signup", json={
        "email": f"{name}@example.com", "name": name.title(), "password": PASSWORD, **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def judge_all(queued: list[int]) -> None:
    while queued:
        await judge_submission({"sandbox": False}, queued.pop(0))


async def submit(client: AsyncClient, queued: list[int], problem: str, code: str, dim: int = 5
                 ) -> dict[str, Any]:
    r = await client.post("/api/submissions", json={"problem_id": problem, "dim": dim,
                                                    "code": code})
    assert r.status_code == 201, r.text
    await judge_all(queued)
    return (await client.get(f"/api/submissions/{r.json()['id']}")).json()


async def other_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_signup_login_logout(client: AsyncClient) -> None:
    me = await signup(client, "ada", country="India", institution="IIT")
    assert me["role"] == "student" and "password" not in str(me)
    assert (await client.get("/api/auth/me")).json()["email"] == "ada@example.com"
    cookie = client.cookies.jar.__iter__().__next__()
    assert cookie.has_nonstandard_attr("HttpOnly")

    dup = await client.post("/api/auth/signup", json={
        "email": "ADA@example.com", "name": "x", "password": PASSWORD})
    assert dup.status_code == 409
    weak = await client.post("/api/auth/signup", json={
        "email": "b@example.com", "name": "x", "password": "short"})
    assert weak.status_code == 422

    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401
    for email, password in (("ada@example.com", "wrong-password"), ("no@example.com", PASSWORD)):
        r = await client.post("/api/auth/login", json={"email": email, "password": password})
        assert (r.status_code, r.json()["detail"]) == (401, "Wrong email or password")
    r = await client.post("/api/auth/login", json={"email": "ada@example.com",
                                                   "password": PASSWORD})
    assert r.status_code == 200


async def test_refresh_token_rotates_and_cannot_be_replayed(client: AsyncClient) -> None:
    await signup(client, "ada")
    old = client.cookies.get("refresh_token", path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 200
    assert client.cookies.get("refresh_token", path="/api/auth") != old
    async with await other_client() as thief:
        thief.cookies.set("refresh_token", old or "", path="/api/auth")
        assert (await thief.post("/api/auth/refresh")).status_code == 401
        thief.cookies.set("access_token", "not-a-token")
        assert (await thief.get("/api/auth/me")).status_code == 401


async def test_cross_site_writes_are_refused(client: AsyncClient) -> None:
    r = await client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = await client.post("/api/auth/logout", headers={"Origin": get_settings().frontend_url})
    assert r.status_code == 204


async def test_problem_catalogue_hides_the_functions(client: AsyncClient) -> None:
    problems = (await client.get("/api/problems")).json()
    assert len(problems) == 18 and problems[0]["dims"] == [5, 10, 20]
    detail = (await client.get("/api/problems/TR-008")).json()
    assert detail["name"] == "Hollow Crown" and len(detail["description"]) > 100
    assert not any(word in detail["description"] for word in ("sqrt", "sin(", "**", "x_1"))
    assert (await client.get("/api/problems/NOPE")).status_code == 404
    names = [t["name"] for t in (await client.get("/api/templates")).json()]
    assert len(names) == 3 and all("def optimize" in t["code"]
                                   for t in (await client.get("/api/templates")).json())


async def test_submit_validation_and_rate_limits(client: AsyncClient, queued: list[int],
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"problem_id": "STD-001", "dim": 5, "code": RANDOM}
    assert (await client.post("/api/submissions", json=body)).status_code == 401
    await signup(client, "ada")
    assert (await client.post("/api/submissions", json={**body, "dim": 7})).status_code == 422
    assert (await client.post("/api/submissions",
                              json={**body, "problem_id": "NOPE"})).status_code == 404
    assert (await client.post("/api/submissions",
                              json={**body, "code": "x" * 200_000})).status_code == 413

    monkeypatch.setattr(get_settings(), "submit_cooldown_sec", 600)
    monkeypatch.setattr(get_settings(), "submit_daily_cap", 2)
    assert (await client.post("/api/submissions", json=body)).status_code == 201
    blocked = await client.post("/api/submissions", json=body)
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers
    quota = (await client.get("/api/problems/STD-001/quota")).json()
    assert quota["used_today"] == 1 and quota["remaining_today"] == 1 and quota["wait_sec"] > 0
    # the limit is per problem
    assert (await client.post("/api/submissions",
                              json={**body, "problem_id": "STD-002"})).status_code == 201

    monkeypatch.setattr(get_settings(), "submit_cooldown_sec", 0)
    assert (await client.post("/api/submissions", json=body)).status_code == 201
    capped = await client.post("/api/submissions", json=body)
    assert capped.status_code == 429 and "Daily" in capped.json()["detail"]
    assert len(queued) == 3


async def test_full_flow_submission_to_leaderboards(client: AsyncClient, queued: list[int]
                                                    ) -> None:
    ada = await signup(client, "ada", country="India", institution="IIT")
    sub = await submit(client, queued, "STD-001", RANDOM)
    assert sub["status"] == "done" and sub["budget"] == 10000 and 0 < sub["score"] < 1000
    assert len(sub["runs"]) == 15 and all(r["status"] == "ok" for r in sub["runs"])
    assert sub["checkpoints"] == checkpoints(10000)
    trace = sub["runs"][0]["precision_trace"]
    assert len(trace) == len(sub["checkpoints"]) and trace[-1] == sub["runs"][0]["precision"]
    assert sub["code"] == RANDOM

    mine = (await client.get("/api/submissions", params={"problem_id": "STD-001"})).json()
    assert [s["id"] for s in mine] == [sub["id"]]

    async with await other_client() as anon:
        public = (await anon.get(f"/api/submissions/{sub['id']}")).json()
        assert public["score"] == sub["score"] and public["code"] == ""
        assert all(r["log"] == "" for r in public["runs"])
        assert (await anon.get("/api/submissions")).status_code == 401

        board = (await anon.get("/api/problems/STD-001/leaderboard", params={"dim": 5})).json()
        assert [(b["rank"], b["name"], b["score"]) for b in board] == [(1, "Ada", sub["score"])]
        assert (await anon.get("/api/problems/STD-001/leaderboard",
                               params={"dim": 10})).json() == []

        top = (await anon.get("/api/leaderboard")).json()
        assert top[0]["name"] == "Ada" and top[0]["rating"] == sub["score"]
        by_country = (await anon.get("/api/leaderboard", params={"by": "country"})).json()
        assert by_country == [{**by_country[0], "name": "India", "members": 1}]

        profile = (await anon.get(f"/api/users/{ada['id']}")).json()
        assert profile["rank"] == 1 and profile["problems_attempted"] == 1
        assert "email" not in profile and profile["recent"][0]["id"] == sub["id"]

        stats = (await anon.get("/api/stats")).json()
        assert (stats["users"], stats["submissions"], stats["runs"]) == (1, 1, 15)
        assert stats["evaluations"] == 15 * 10000 and stats["by_status"] == {"done": 1}

    r = await client.patch("/api/users/me", json={"bio": "  hello  "})
    assert r.json()["bio"] == "hello"


async def test_broken_submission_scores_zero_with_error_shown_to_author(
    client: AsyncClient, queued: list[int]
) -> None:
    await signup(client, "ada")
    sub = await submit(client, queued, "STD-001",
                       "def optimize(f, dim, lower, upper, budget, rng):\n"
                       "    print('debug\\x00line')\n    raise ValueError('nope')\n")
    assert sub["status"] == "done" and sub["score"] == 0
    assert "ValueError: nope" in sub["runs"][0]["error"] and "debug" in sub["runs"][0]["log"]


async def test_beating_the_reference_value_rescored_everyone(
    client: AsyncClient, queued: list[int], session: AsyncSession
) -> None:
    await signup(client, "ada")
    first = await submit(client, queued, "TR-001", RANDOM)
    ref_before = {r.instance_seed: r.value for r in await session.scalars(select(FRef))}
    assert len(ref_before) == 3 and first["score"] > 0

    async with await other_client() as bob:
        await signup(bob, "bob")
        better = await submit(bob, queued, "TR-001", baselines.source("cmaes"))
    session.expire_all()
    ref_after = {r.instance_seed: r.value for r in await session.scalars(select(FRef))}
    assert all(ref_after[s] < ref_before[s] for s in ref_before)

    rescored = (await client.get(f"/api/submissions/{first['id']}")).json()
    assert rescored["score"] < first["score"] < better["score"]
    board = (await client.get("/api/problems/TR-001/leaderboard", params={"dim": 5})).json()
    assert [b["name"] for b in board] == ["Bob", "Ada"]


async def test_platform_failure_marks_submission_failed(
    client: AsyncClient, queued: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    await signup(client, "ada")

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("docker is down")

    monkeypatch.setattr("worker.main.judge", boom)
    sub = await submit(client, queued, "STD-001", RANDOM)
    assert sub["status"] == "failed" and "platform error" in sub["error"]
    assert "docker" not in sub["error"]


async def test_admin(client: AsyncClient, queued: list[int], session: AsyncSession) -> None:
    ada = await signup(client, "ada")
    assert (await client.get("/api/admin/users")).status_code == 403
    async with await other_client() as anon:
        assert (await anon.get("/api/admin/users")).status_code == 401

    admin = await session.get(User, ada["id"])
    assert admin is not None
    admin.role = "admin"
    await session.commit()
    async with await other_client() as bob:
        bob_me = await signup(bob, "bob")

    assert len((await client.get("/api/admin/users")).json()) == 2
    r = await client.patch(f"/api/admin/users/{bob_me['id']}", json={"role": "instructor"})
    assert r.json()["role"] == "instructor"
    assert (await client.patch(f"/api/admin/users/{ada['id']}",
                               json={"role": "student"})).status_code == 400
    assert (await client.patch(f"/api/admin/users/{bob_me['id']}",
                               json={"role": "root"})).status_code == 422

    r = await client.patch("/api/admin/problems/STD-008", json={"is_active": False})
    assert r.json()["is_active"] is False
    assert len((await client.get("/api/problems")).json()) == 17
    assert (await client.get("/api/problems/STD-008")).status_code == 404
    assert len((await client.get("/api/admin/problems")).json()) == 18

    r = await client.post("/api/admin/problems/STD-001/baselines", json={"dim": 5})
    assert r.status_code == 201 and len(queued) == 3
    await judge_all(queued)
    board = (await client.get("/api/problems/STD-001/leaderboard", params={"dim": 5})).json()
    assert len(board) == 3 and all(b["is_baseline"] for b in board)
    assert board[0]["name"] == "CMA-ES (baseline)"
    assert (await client.get("/api/leaderboard")).json() == []  # bots are not ranked globally
    assert (await client.get("/api/stats")).json()["users"] == 2
    bots = await session.scalars(select(User).where(User.is_bot))
    r = await client.post("/api/auth/login", json={"email": bots.first().email,  # type: ignore[union-attr]
                                                   "password": "!"})
    assert r.status_code in (401, 422)
    assert len((await client.get("/api/admin/submissions")).json()) == 3
    assert await session.scalar(select(Submission.id).limit(1)) is not None
