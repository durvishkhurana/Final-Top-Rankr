import json
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from worker.main import grade_attempt

from ai import llm
from db.models import IntegrityEvent
from exams import numeric, similarity
from exams.grading import purge_events
from judge import templates

from .test_ai import Fake
from .test_api import RANDOM, judge_all, other_client, signup
from .test_contests import make

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC)
DE = templates.source("minimal_de")


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Fake:
    f = Fake()
    monkeypatch.setattr(llm, "TRANSPORT", httpx.MockTransport(f))
    return f


def rename(code: str) -> str:
    """The same code with every variable renamed and re-indented."""
    for old, new in [("best_x", "champion"), ("best_f", "record"), ("X", "cands"),
                     ("values", "fitness")]:
        code = code.replace(old, new)
    return code.replace("    ", "  ")


# --- units ---------------------------------------------------------------------------


def test_numeric_answers_are_computed_and_personal() -> None:
    assert numeric.FUNCTIONS["sphere"](np.array([1.0, 2.0])) == 5.0
    assert numeric.FUNCTIONS["rastrigin"](np.zeros(3)) == 0.0
    seeds = {numeric.personal_seed(1, student, 7) for student in range(50)}
    assert len(seeds) == 50
    assert numeric.instance("precision", 42) == numeric.instance("precision", 42)
    params, answer = numeric.instance("precision", 42)
    assert answer == pytest.approx(np.log10(params["f_best"] - params["f_ref"]))
    assert numeric.is_correct(answer * (1 + 1e-4), answer)
    assert not numeric.is_correct(answer + 1, answer)


def test_fill_only_replaces_known_plain_names() -> None:
    assert numeric.fill("budget {budget}", {"budget": "1,000"}) == "budget 1,000"
    assert numeric.fill("{nope}", {"budget": 1}) is None
    # no attribute access as with str.format
    assert numeric.fill("{budget.__class__}", {"budget": 1}) == "{budget.__class__}"


def test_similarity_sees_through_renaming_and_ignores_shared_templates() -> None:
    copy = similarity.compare(DE, rename(DE))
    assert copy["token"] > 0.95 and copy["structure"] > 0.95
    other = similarity.compare(DE, templates.source("random_search"))
    assert other["token"] < 0.5
    starters = {"minimal_de": DE}
    custom = DE + "\n\ndef helper(z):\n    return [v * 2 for v in z if v > 0]\n"
    pairs = similarity.similar_pairs([(1, DE), (2, DE), (3, custom), (4, rename(custom))],
                                     starters)
    assert (1, 2) not in {(p["a"], p["b"]) for p in pairs}  # both just the template
    assert (pairs[0]["a"], pairs[0]["b"]) == (3, 4)


# --- the whole flow ----------------------------------------------------------------------


async def test_test_lifecycle(client: AsyncClient, queued: list[int], session: AsyncSession,
                              jobs: list[tuple[str, int]], fake: Fake) -> None:
    await make(session, client, "teach", "instructor")
    course = (await client.post("/api/courses", json={"title": "Optimisation 101"})).json()
    exam = (await client.post("/api/tests", json={
        "course_id": course["id"], "title": "Quiz 1",
        "starts_at": (NOW - timedelta(hours=1)).isoformat(),
        "ends_at": (NOW + timedelta(hours=2)).isoformat()})).json()
    base = f"/api/tests/{exam['id']}"
    mcq = (await client.post(f"{base}/questions", json={
        "kind": "mcq", "prompt": "Which step keeps the better point?", "points": 1,
        "data": {"choices": ["mutation", "selection"], "correct": 1}})).json()
    num = (await client.post(f"{base}/questions", json={
        "kind": "numeric", "prompt": numeric.GENERATORS["precision"][1], "points": 2,
        "data": {"generator": "precision"}})).json()
    bad = await client.post(f"{base}/questions", json={
        "kind": "reasoning", "prompt": "Why {nonsense}?", "data": {"rubric": "x"}})
    assert bad.status_code == 422
    why = (await client.post(f"{base}/questions", json={
        "kind": "reasoning", "points": 4,
        "prompt": "Your run stopped improving after {last_improvement_evals} evaluations. Why?",
        "data": {"problem_id": "STD-001", "dim": 5, "rubric": "Names stagnation of sampling",
                 "follow_up": True}})).json()

    fake.groq.append(json.dumps({"distractors": ["crossover", "restart", "rotation"]}))
    r = await client.post(f"{base}/questions/{mcq['id']}/distractors")
    assert r.json()["distractors"][0] == "crossover"
    r = await client.put(f"{base}/questions/{mcq['id']}", json={
        "kind": "mcq", "prompt": mcq["prompt"],
        "data": {"choices": ["mutation", "selection", "crossover"], "correct": 1}})
    assert r.json()["data"]["choices"][-1] == "crossover"

    assert (await client.patch(base, json={"status": "live"})).status_code == 409
    fake.groq.append(json.dumps({"phrasings": [
        "After {last_improvement_evals} of {budget} evaluations nothing improved. Why?",
        "Uses an {unknown} placeholder", "Why did progress stop?"]}))
    pool = (await client.post(f"{base}/questions/{why['id']}/pool")).json()["data"]["pool"]
    assert len(pool) == 2 and not any("unknown" in p for p in pool)
    r = await client.post(f"{base}/questions/{why['id']}/approve-pool", json={"pool": pool[:1]})
    assert r.json()["pool_approved"]
    assert (await client.patch(base, json={"status": "live"})).json()["status"] == "live"

    async with await other_client() as ada:
        ada_me = await signup(ada, "ada")
        await ada.post("/api/courses/join", json={"code": course["invite_code"]})
        await ada.post("/api/submissions", json={"problem_id": "STD-001", "dim": 5,
                                                 "code": RANDOM})
        await judge_all(queued)
        assert (await ada.get(f"{base}/questions")).status_code == 403
        assert (await ada.post(f"{base}/attempt", json={"consent": False})).status_code == 422
        attempt = (await ada.post(f"{base}/attempt", json={"consent": True,
                                                            "camera_consent": True})).json()
        assert "correct" not in json.dumps(attempt)
        a_mcq, a_num, a_why = attempt["answers"]
        assert "{" not in a_num["prompt"] and "{" not in a_why["prompt"]
        assert "of 1" in a_why["prompt"]  # filled with Ada's own budget
        params, expected = numeric.instance("precision", numeric.personal_seed(
            exam["id"], ada_me["id"], num["id"]))
        assert str(params["f_best"]) in a_num["prompt"]

        await ada.put(f"/api/answers/{a_mcq['id']}", json={"response": "1", "time_ms": 4000})
        await ada.put(f"/api/answers/{a_num['id']}", json={"response": f"{expected:.5f}"})
        fake.groq.append(json.dumps({"question": "What would a restart change?"}))
        saved = await ada.put(f"/api/answers/{a_why['id']}", json={
            "response": "It sampled uniformly so it stagnated.", "paste_chars": 40})
        assert saved.json()["follow_up"] == "What would a restart change?"
        assert (await ada.put(f"/api/answers/{a_why['id']}/follow-up",
                              json={"response": "It would explore again."})).status_code == 204
        events = [{"kind": "tab_hidden", "at": NOW.isoformat(), "duration_ms": 3000},
                  {"kind": "paste", "at": NOW.isoformat(), "detail": "40 characters"}]
        assert (await ada.post(f"/api/attempts/{attempt['id']}/events",
                               json=events)).status_code == 204
        bad_event = [{"kind": "screenshot", "at": NOW.isoformat()}]
        assert (await ada.post(f"/api/attempts/{attempt['id']}/events",
                               json=bad_event)).status_code == 422

        await ada.post(f"/api/attempts/{attempt['id']}/submit")
        assert jobs[-1] == ("grade_attempt", attempt["id"])
        fake.groq.append(json.dumps({"level": 0.5, "rationale": "Partly right.",
                                     "confidence": 0.8, "contradiction": True,
                                     "contradiction_note": "the code never restarts"}))
        await grade_attempt({}, attempt["id"])
        # grades stay hidden from the student until the test is closed
        mine = (await ada.get(f"/api/attempts/{attempt['id']}")).json()
        assert mine["total"] is None and mine["answers"][0]["score"] is None
        assert (await ada.put(f"/api/answers/{a_mcq['id']}",
                              json={"response": "0"})).status_code == 409

        results = (await client.get(f"{base}/results")).json()
        row = results[0]
        assert row["total"] == 1 + 2 + 2.0
        assert [e["kind"] for e in row["events"]] == ["tab_hidden", "paste"]
        reasoning = row["answers"][2]
        assert reasoning["flags"] == ["possible contradiction: the code never restarts"]
        assert reasoning["follow_up_response"] == "It would explore again."
        assert reasoning["paste_chars"] == 40 and row["answers"][0]["time_ms"] == 4000
        assert row["answers"][1]["correct"] == f"{expected:.6g}"

        assert (await client.post(f"/api/answers/{reasoning['id']}/grade",
                                  json={"score": 9, "reason": "x"})).status_code == 422
        r = await client.post(f"/api/answers/{reasoning['id']}/grade",
                              json={"score": 3.5, "reason": "Restart idea is implied"})
        assert [h["actor"] for h in r.json()["history"]] == ["automatic", "Teach"]
        assert (await ada.post(f"/api/answers/{reasoning['id']}/grade",
                               json={"score": 4, "reason": "me"})).status_code == 403

        fake.groq.append(json.dumps({"questions": ["Why 50?", "What does line 3 do?",
                                                   "When does it stop?"]}))
        assert len((await client.post(f"/api/attempts/{attempt['id']}/viva")).json()) == 3
        assert (await ada.post(f"/api/attempts/{attempt['id']}/viva")).status_code == 403

        await client.patch(base, json={"status": "closed"})
        mine = (await ada.get(f"/api/attempts/{attempt['id']}")).json()
        assert mine["total"] == 6.5 and "viva" not in mine


async def test_similar_pairs_for_the_instructor(
        client: AsyncClient, queued: list[int], session: AsyncSession, fake: Fake) -> None:
    await make(session, client, "teach", "instructor")
    course = (await client.post("/api/courses", json={"title": "Optimisation 101"})).json()
    custom = DE + "\n\ndef helper(z):\n    return [v * 2 for v in z if v > 0]\n"
    ids = []
    for name, code in [("ada", custom), ("bob", rename(custom)), ("eve", RANDOM)]:
        async with await other_client() as c:
            await signup(c, name)
            await c.post("/api/courses/join", json={"code": course["invite_code"]})
            r = await c.post("/api/submissions", json={"problem_id": "STD-001", "dim": 5,
                                                       "code": code})
            ids.append(r.json()["id"])
            await judge_all(queued)
            assert (await c.get(f"/api/courses/{course['id']}/similarity?problem_id=STD-001"
                                "&dim=5")).status_code == 403
    pairs = (await client.get(f"/api/courses/{course['id']}/similarity?problem_id=STD-001"
                              "&dim=5")).json()
    assert (pairs[0]["a_name"], pairs[0]["b_name"]) == ("Ada", "Bob")
    assert pairs[0]["similarity"] > 0.9
    fake.groq.append(json.dumps({"verdict": "likely shared", "reasons": "Same helper."}))
    r = await client.post(f"/api/courses/{course['id']}/similarity/opinion",
                          json={"a": ids[0], "b": ids[1]})
    assert r.json()["verdict"] == "likely shared"


async def test_integrity_events_are_deleted_after_retention(
        client: AsyncClient, session: AsyncSession) -> None:
    await make(session, client, "teach", "instructor")
    course = (await client.post("/api/courses", json={"title": "C"})).json()
    exam = (await client.post("/api/tests", json={
        "course_id": course["id"], "title": "Q", "starts_at": NOW.isoformat(),
        "ends_at": (NOW + timedelta(hours=1)).isoformat()})).json()
    await client.post(f"/api/tests/{exam['id']}/questions", json={
        "kind": "mcq", "prompt": "?", "data": {"choices": ["a", "b"], "correct": 0}})
    await client.patch(f"/api/tests/{exam['id']}", json={"status": "live"})
    async with await other_client() as ada:
        await signup(ada, "ada")
        await ada.post("/api/courses/join", json={"code": course["invite_code"]})
        attempt = (await ada.post(f"/api/tests/{exam['id']}/attempt",
                                  json={"consent": True})).json()
    old, new = NOW - timedelta(days=40), NOW - timedelta(days=1)
    session.add_all([IntegrityEvent(attempt_id=attempt["id"], kind="copy", at=old,
                                    received_at=old),
                     IntegrityEvent(attempt_id=attempt["id"], kind="copy", at=new,
                                    received_at=new)])
    await session.commit()
    assert await purge_events(session, NOW - timedelta(days=30)) == 1
