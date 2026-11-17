from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from worker.main import finalise_contest, heldout_seeds

from db.models import Contest, FinalResult, FRef, Run, User
from judge import baselines

from .test_api import RANDOM, judge_all, other_client, signup

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC)
TASKS = [{"problem_id": "STD-001", "dim": 5}, {"problem_id": "TR-001", "dim": 5}]


async def make(session: AsyncSession, client: AsyncClient, name: str, role: str) -> dict[str, Any]:
    me = await signup(client, name)
    user = await session.get(User, me["id"])
    assert user is not None
    user.role = role
    await session.commit()
    return me


def contest_body(**extra: Any) -> dict[str, Any]:
    return {"title": "Autumn cup", "tasks": TASKS,
            "starts_at": (NOW - timedelta(hours=1)).isoformat(),
            "ends_at": (NOW + timedelta(days=1)).isoformat(), **extra}


async def enter(client: AsyncClient, queued: list[int], contest_id: int, problem: str,
                code: str) -> dict[str, Any]:
    r = await client.post("/api/submissions", json={"problem_id": problem, "dim": 5,
                                                    "code": code, "contest_id": contest_id})
    assert r.status_code == 201, r.text
    await judge_all(queued)
    return r.json()


async def test_only_staff_create_and_invite_code_is_required(
    client: AsyncClient, session: AsyncSession
) -> None:
    await signup(client, "stu")
    assert (await client.post("/api/contests", json=contest_body())).status_code == 403
    async with await other_client() as teacher:
        await make(session, teacher, "teach", "instructor")
        bad = contest_body(tasks=[{"problem_id": "STD-001", "dim": 7}])
        assert (await teacher.post("/api/contests", json=bad)).status_code == 422
        backwards = contest_body(ends_at=(NOW - timedelta(days=2)).isoformat())
        assert (await teacher.post("/api/contests", json=backwards)).status_code == 422
        made = (await teacher.post("/api/contests", json=contest_body(invite_only=True))).json()
        assert made["phase"] == "running" and made["invite_only"] and len(made["invite_code"]) >= 8

    seen = (await client.get(f"/api/contests/{made['id']}")).json()
    assert seen["invite_code"] is None and not seen["joined"] and not seen["can_manage"]
    r = await client.post(f"/api/contests/{made['id']}/join", json={"code": "nope"})
    assert r.status_code == 403
    body = {"problem_id": "STD-001", "dim": 5, "code": RANDOM, "contest_id": made["id"]}
    assert (await client.post("/api/submissions", json=body)).status_code == 403
    r = await client.post(f"/api/contests/{made['id']}/join", json={"code": made["invite_code"]})
    assert r.json()["joined"] and r.json()["participants"] == 1
    off_task = {**body, "problem_id": "STD-002"}
    assert (await client.post("/api/submissions", json=off_task)).status_code == 422
    assert (await client.post("/api/submissions", json=body)).status_code == 201
    assert (await client.post(f"/api/contests/{made['id']}/finalise")).status_code == 403


async def test_contest_runs_then_final_ranking_uses_heldout_instances(
    client: AsyncClient, queued: list[int], session: AsyncSession
) -> None:
    await make(session, client, "teach", "instructor")
    contest = (await client.post("/api/contests", json=contest_body())).json()
    cid = contest["id"]
    assert [c["id"] for c in (await client.get("/api/contests")).json()] == [cid]

    async with await other_client() as ada, await other_client() as bob:
        await signup(ada, "ada")
        await signup(bob, "bob")
        for c in (ada, bob):
            assert (await c.post(f"/api/contests/{cid}/join", json={})).status_code == 200
        await enter(ada, queued, cid, "STD-001", RANDOM)
        await enter(ada, queued, cid, "TR-001", RANDOM)
        await enter(bob, queued, cid, "STD-001", baselines.source("cmaes"))
        # a submission outside the contest does not count for it
        await bob.post("/api/submissions", json={"problem_id": "TR-001", "dim": 5,
                                                 "code": baselines.source("cmaes")})
        await judge_all(queued)

        board = (await ada.get(f"/api/contests/{cid}/leaderboard")).json()
        assert [b["name"] for b in board] == ["Bob", "Ada"] and not board[0]["final"]
        assert set(board[1]["scores"]) == {"STD-001@5", "TR-001@5"}
        assert set(board[0]["scores"]) == {"STD-001@5"}
        public_bob = board[0]["scores"]["STD-001@5"]

        done = (await client.post(f"/api/contests/{cid}/finalise")).json()
        assert done["phase"] == "finalising"
        assert (await client.post(f"/api/contests/{cid}/finalise")).status_code == 409
        late = {"problem_id": "STD-001", "dim": 5, "code": RANDOM, "contest_id": cid}
        assert (await ada.post("/api/submissions", json=late)).status_code == 409

        refs_before = len(list(await session.scalars(select(FRef))))
        await finalise_contest({"sandbox": False}, cid)
        final = (await ada.get(f"/api/contests/{cid}/leaderboard")).json()
        assert (await ada.get(f"/api/contests/{cid}")).json()["phase"] == "final"
        assert [b["name"] for b in final] == ["Bob", "Ada"] and all(b["final"] for b in final)
        # different instances: the final score is close to the public one, and the
        # held-out runs are not the public runs (rounded scores can still tie)
        assert abs(final[0]["scores"]["STD-001@5"] - public_bob) < 150
        held_out = await session.scalar(select(FinalResult).where(
            FinalResult.contest_id == cid, FinalResult.problem_id == "STD-001",
            FinalResult.user_id == board[0]["user_id"]))
        assert held_out is not None
        public_runs = await session.scalars(select(Run.aocc).where(
            Run.submission_id == held_out.submission_id))
        assert sorted(r["aocc"] for r in held_out.runs) != sorted(public_runs)
        # Ada is the only TR-001 entry, so she is scored against her own best there
        assert final[1]["scores"]["TR-001@5"] > 0
        # held-out reference values are not written to the public store
        assert len(list(await session.scalars(select(FRef)))) == refs_before

    seeds = heldout_seeds(cid)
    assert len(set(seeds)) == 3 and min(seeds) >= 10**6 and seeds != heldout_seeds(cid + 1)
    assert str(seeds[0]) not in (await client.get(f"/api/contests/{cid}")).text
    stored = await session.get(Contest, cid)
    assert stored is not None and str(seeds[0]) not in str(stored.__dict__)


async def test_courses_enrolment_course_contest_and_dashboard(
    client: AsyncClient, queued: list[int], session: AsyncSession
) -> None:
    await make(session, client, "teach", "instructor")
    course = (await client.post("/api/courses", json={"title": "Optimisation 101"})).json()
    assert course["teaches"] and course["invite_code"]
    contest = (await client.post("/api/contests",
                                 json=contest_body(course_id=course["id"]))).json()

    async with await other_client() as ada, await other_client() as eve:
        await signup(ada, "ada")
        await signup(eve, "eve")
        assert (await ada.post("/api/courses", json={"title": "x"})).status_code == 403
        assert (await ada.post("/api/courses/join", json={"code": "wrong"})).status_code == 404
        # course contests are hidden from, and closed to, people outside the course
        assert (await eve.get("/api/contests")).json() == []
        assert (await eve.post(f"/api/contests/{contest['id']}/join",
                               json={})).status_code == 403
        joined = (await ada.post("/api/courses/join",
                                 json={"code": course["invite_code"]})).json()
        assert joined["invite_code"] is None and not joined["teaches"] and joined["students"] == 1
        assert [c["id"] for c in (await ada.get("/api/courses")).json()] == [course["id"]]
        assert len((await ada.get("/api/contests")).json()) == 1
        assert (await ada.post(f"/api/contests/{contest['id']}/join", json={})).status_code == 200
        await enter(ada, queued, contest["id"], "STD-001", RANDOM)
        assert (await ada.get(f"/api/courses/{course['id']}/dashboard")).status_code == 403

    board = (await client.get(f"/api/courses/{course['id']}/dashboard")).json()
    assert [c["key"] for c in board["columns"]] == [f"{contest['id']}:STD-001@5",
                                                    f"{contest['id']}:TR-001@5"]
    (student,) = board["students"]
    assert student["name"] == "Ada" and student["submissions"] == 1 and student["last_active"]
    assert student["scores"][f"{contest['id']}:STD-001@5"] > 0
