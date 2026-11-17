import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from worker.main import judge_submission

from ai.challenger import evolve
from db.models import Challenger, Generation
from judge import baselines

from .test_ai import Fake, fake, make_admin  # noqa: F401
from .test_api import RANDOM, other_client, signup, submit

pytestmark = pytest.mark.anyio


def reply(code: str, approach: str) -> str:
    return json.dumps({"approach": approach, "changes": "first try", "code": code})


async def judge(submission_id: int) -> None:
    await judge_submission({"sandbox": False}, submission_id)


async def test_only_admins_start_a_challenger_once(
    client: AsyncClient, session: AsyncSession, jobs: list[tuple[str, int]]
) -> None:
    me = await signup(client, "ada")
    body = {"problem_id": "STD-001", "dim": 5}
    assert (await client.post("/api/challengers", json=body)).status_code == 403
    await make_admin(session, me["id"])
    r = await client.post("/api/challengers", json=body)
    assert r.status_code == 201, r.text
    assert jobs == [("evolve_challenger", r.json()["id"])]
    assert (await client.post("/api/challengers", json=body)).status_code == 409
    bad = {"problem_id": "STD-001", "dim": 7}
    assert (await client.post("/api/challengers", json=bad)).status_code == 404

    cid = r.json()["id"]
    r = await client.patch(f"/api/challengers/{cid}", json={"is_active": False})
    assert r.json()["active"] is False
    assert (await client.post(f"/api/challengers/{cid}/evolve")).status_code == 202
    async with await other_client() as anyone:
        listed = (await anyone.get("/api/challengers", params={"problem_id": "STD-001"})).json()
        assert [c["id"] for c in listed] == [cid]
        assert (await anyone.post(f"/api/challengers/{cid}/evolve")).status_code == 401


async def test_generations_improve_on_the_champion(
    client: AsyncClient, queued: list[int], session: AsyncSession, fake: Fake  # noqa: F811
) -> None:
    await signup(client, "ada")
    human = await submit(client, queued, "STD-001", RANDOM)
    challenger = Challenger(problem_id="STD-001", dim=5)
    session.add(challenger)
    await session.commit()

    # generation 1: written from the public description alone
    fake.groq.append(reply(RANDOM, "random search"))
    first = await evolve(session, challenger.id, judge)
    assert first is not None and first.number == 1 and first.status == "done"
    assert "Write a black-box optimizer" in fake.prompt()

    # generation 2 starts from generation 1 and sees its statistics, not hidden data
    fake.groq.append(reply(baselines.source("cmaes"), "CMA-ES with restarts"))
    second = await evolve(session, challenger.id, judge)
    assert second is not None and second.parent_id == first.id
    prompt = fake.prompt()
    assert "generation 1, score" in prompt and "median_final_precision" in prompt
    assert f"human participant on this problem and dimension: {human['score']}" in prompt
    assert "1: " in prompt and "random search" in prompt
    for hidden in ("instance_seed", "f_ref", "rotation", "shift"):
        assert hidden not in prompt

    # generation 3 fails at the provider; the champion stays
    third = await evolve(session, challenger.id, judge)
    assert third is not None and third.status == "failed" and third.submission_id is None
    assert "could not answer" in third.error

    detail = (await client.get(f"/api/challengers/{challenger.id}")).json()
    assert [g["status"] for g in detail["history"]] == ["done", "done", "failed"]
    champion = [g for g in detail["history"] if g["is_champion"]]
    assert [g["number"] for g in champion] == [2]
    assert detail["best_score"] == champion[0]["score"] > detail["history"][0]["score"]
    assert detail["history"][1]["approach"] == "CMA-ES with restarts"

    # its best generation is its leaderboard entry, flagged as a baseline
    board = (await client.get("/api/problems/STD-001/leaderboard", params={"dim": 5})).json()
    bot = next(b for b in board if b["name"].startswith("AI challenger"))
    assert bot["is_baseline"] and bot["submission_id"] == champion[0]["submission_id"]
    # the code is not public
    sub = (await client.get(f"/api/submissions/{bot['submission_id']}")).json()
    assert sub["code"] == ""


async def test_one_generation_at_a_time(
    client: AsyncClient, session: AsyncSession, fake: Fake  # noqa: F811
) -> None:
    me = await signup(client, "ada")
    await make_admin(session, me["id"])
    challenger = Challenger(problem_id="STD-001", dim=5)
    session.add(challenger)
    await session.flush()
    session.add(Generation(challenger_id=challenger.id, number=1))
    await session.commit()
    assert await evolve(session, challenger.id, judge) is None
    assert not fake.calls
    assert (await client.post(f"/api/challengers/{challenger.id}/evolve")).status_code == 409
    assert (await client.get(f"/api/challengers/{challenger.id}")).json()["running"]
    assert await evolve(session, challenger.id + 1, judge) is None  # no such challenger
