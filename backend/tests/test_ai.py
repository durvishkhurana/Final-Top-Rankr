import base64
import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from worker.main import smoke_contribution

from ai import llm
from core.config import get_settings
from db.models import LlmCall, Run, User
from judge.functions import PROBLEMS

from .test_api import RANDOM, judge_all, other_client, signup, submit

pytestmark = pytest.mark.anyio

ANALYSIS = {"family": "random search", "population_based": False, "mutation": "none",
            "crossover": "none", "selection": "keeps the best point", "restarts": "none",
            "local_search": "none", "summary": "Samples the box uniformly."}
COACH = {"diagnosis": "Progress stops early.", "suggestion": "Sample around the best point."}
SPHERE = "def f(X):\n    return (X ** 2).sum(axis=1)\n"


class Fake:
    """Stands in for both providers; replies are queued per provider."""

    def __init__(self) -> None:
        self.groq: list[str] = []
        self.gemini: list[str] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        name = "groq" if "groq" in request.url.host else "gemini"
        self.calls.append((name, body))
        queue = self.groq if name == "groq" else self.gemini
        if not queue:
            return httpx.Response(500)
        text = queue.pop(0)
        if name == "groq":
            return httpx.Response(200, json={"choices": [{"message": {"content": text}}],
                                             "usage": {"prompt_tokens": 9, "completion_tokens": 4}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})

    def prompt(self, k: int = -1) -> str:
        name, body = self.calls[k]
        if name == "groq":
            return str(body["messages"][0]["content"])
        return str(body["contents"][0]["parts"][0]["text"])


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Fake:
    f = Fake()
    monkeypatch.setattr(llm, "TRANSPORT", httpx.MockTransport(f))
    return f


@pytest.fixture
def contributed() -> Iterator[None]:
    """Approved contributions register in the process-wide registry; undo that."""
    yield
    for key in [k for k in PROBLEMS if k.startswith("C-")]:
        del PROBLEMS[key]


async def make_admin(session: AsyncSession, user_id: int) -> None:
    user = await session.get(User, user_id)
    assert user is not None
    user.role = "admin"
    await session.commit()


async def test_analysis_is_stored_reused_and_private(
        client: AsyncClient, queued: list[int], session: AsyncSession, fake: Fake) -> None:
    await signup(client, "ada")
    sub = await submit(client, queued, "STD-001", RANDOM)
    fake.groq.append(json.dumps(ANALYSIS))
    r = await client.post(f"/api/submissions/{sub['id']}/analysis")
    assert r.status_code == 200, r.text
    assert r.json()["content"]["family"] == "random search"
    assert RANDOM.strip() in fake.prompt()
    # stored per submission: no second request
    assert (await client.post(f"/api/submissions/{sub['id']}/analysis")).status_code == 200
    assert len(fake.calls) == 1
    assert [n["kind"] for n in (await client.get(f"/api/submissions/{sub['id']}/notes")).json()] \
        == ["analysis"]

    # identical code elsewhere is answered from the call log
    again = await submit(client, queued, "STD-002", RANDOM)
    assert (await client.post(f"/api/submissions/{again['id']}/analysis")).status_code == 200
    assert len(fake.calls) == 1
    cached = await session.scalars(select(LlmCall.cached).order_by(LlmCall.id))
    assert list(cached) == [False, True]

    async with await other_client() as bob:
        await signup(bob, "bob")
        assert (await bob.post(f"/api/submissions/{sub['id']}/analysis")).status_code == 403


async def test_coach_sees_relative_facts_only_and_falls_back(
        client: AsyncClient, queued: list[int], session: AsyncSession, fake: Fake) -> None:
    await signup(client, "ada")
    # no known optimum: raw values differ from the relative precision the coach is given
    sub = await submit(client, queued, "TR-001", RANDOM)
    fake.groq.append("this is not JSON")
    fake.gemini.append(json.dumps(COACH))
    r = await client.post(f"/api/submissions/{sub['id']}/coach")
    assert r.status_code == 200, r.text
    assert r.json()["content"]["suggestion"] == COACH["suggestion"]
    assert [name for name, _ in fake.calls] == ["groq", "gemini"]
    prompt = fake.prompt()
    # raw objective values would reveal the instance; only relative precision is sent
    raw = await session.scalars(select(Run.f_best).where(Run.submission_id == sub["id"]))
    for f_best in raw:
        assert f_best is None or repr(f_best) not in prompt
    assert "instance_seed" not in prompt and "x_star" not in prompt


async def test_disabled_and_daily_limit(client: AsyncClient, queued: list[int], fake: Fake,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    await signup(client, "ada")
    sub = await submit(client, queued, "STD-001", RANDOM)
    s = get_settings()
    monkeypatch.setattr(s, "ai_daily_limit_per_user", 0)
    assert (await client.get("/api/ai/status")).json() == {"enabled": True, "remaining_today": 0}
    assert (await client.post(f"/api/submissions/{sub['id']}/analysis")).status_code == 429
    monkeypatch.setattr(s, "groq_api_key", "")
    monkeypatch.setattr(s, "gemini_api_key", "")
    assert (await client.post(f"/api/submissions/{sub['id']}/analysis")).status_code == 503
    assert fake.calls == []


async def test_contribution_smoke_test_approval_and_judging(
        client: AsyncClient, queued: list[int], jobs: list[tuple[str, int]],
        session: AsyncSession, contributed: None) -> None:
    ada = await signup(client, "ada")
    body = {"name": "Plain bowl", "summary": "A sphere.", "source": SPHERE,
            "lower": -5, "upper": 5, "dims": [5]}
    r = await client.post("/api/contributions", json=body)
    assert r.status_code == 201, r.text
    good = r.json()
    assert good["status"] == "testing"
    bad = (await client.post("/api/contributions", json={
        **body, "name": "Broken", "source": "def f(X):\n    return X[:, 0] * float('nan')\n"})
    ).json()
    assert jobs == [("smoke_contribution", good["id"]), ("smoke_contribution", bad["id"])]
    for _, item_id in jobs:
        await smoke_contribution({"sandbox": False}, item_id)
    mine = {c["id"]: c for c in (await client.get("/api/contributions")).json()}
    assert mine[good["id"]]["status"] == "pending", mine[good["id"]]["smoke"]
    assert mine[bad["id"]]["status"] == "failed"

    assert (await client.post(f"/api/admin/contributions/{good['id']}/approve")).status_code \
        == 403
    await make_admin(session, ada["id"])
    assert (await client.post(f"/api/admin/contributions/{bad['id']}/approve")).status_code \
        == 409
    r = await client.post(f"/api/admin/contributions/{good['id']}/approve")
    assert r.status_code == 200 and r.json()["problem_id"] == "C-001"
    problem = (await client.get("/api/problems/C-001")).json()
    assert problem["category"] == "Contributed" and problem["dims"] == [5]

    sub = await submit(client, queued, "C-001", RANDOM)
    assert sub["status"] == "done", sub["error"]
    assert sub["score"] is not None and all(r["status"] == "ok" for r in sub["runs"])


async def test_problem_builder_uses_gemini_for_images(
        client: AsyncClient, jobs: list[tuple[str, int]], fake: Fake) -> None:
    await signup(client, "ada")
    built = {"name": "Bowl", "summary": "A sphere.", "description": "Sum of squares.",
             "source": SPHERE, "lower": -5, "upper": 5, "dims": [5, 10], "level": "Easy",
             "tags": ["unimodal"]}
    fake.gemini.append(json.dumps(built))
    r = await client.post("/api/contributions/build", json={
        "text": "sum of squares", "image_base64": base64.b64encode(b"\x89PNG fake").decode(),
        "image_mime": "image/png"})
    assert r.status_code == 201, r.text
    assert r.json()["ai_built"] and r.json()["status"] == "testing"
    name, body = fake.calls[0]
    assert name == "gemini" and "inline_data" in body["contents"][0]["parts"][1]
    assert jobs == [("smoke_contribution", r.json()["id"])]
    bad = await client.post("/api/contributions/build", json={
        "text": "x", "image_base64": "not base64!"})
    assert bad.status_code == 422


async def test_ai_baseline_is_judged_as_a_labelled_bot(
        client: AsyncClient, queued: list[int], session: AsyncSession, fake: Fake) -> None:
    ada = await signup(client, "ada")
    await make_admin(session, ada["id"])
    fake.groq.append(json.dumps({"approach": "random search", "code": RANDOM}))
    r = await client.post("/api/admin/problems/STD-001/ai-baseline", json={"dim": 5})
    assert r.status_code == 201, r.text
    assert "Search box: -" in fake.prompt()
    await judge_all(queued)
    board = (await client.get("/api/problems/STD-001/leaderboard?dim=5")).json()
    assert [row["name"] for row in board] == ["AI-written optimizer (baseline)"]
