"""Demo activity on top of the demo users, so every page has something to show:
two courses, three contests (running, final, upcoming), three course tests (graded and
closed, open now, draft) and contributed problems in every review state.

It goes through the real API in this process, signed in as each demo user, so the data
is exactly what the app itself would store. Queued jobs (judging, contest finalisation,
smoke tests, grading) run right here on trusted built-in code, without a container.
AI features are switched off while seeding: no provider calls are made, and reasoning
answers are graded by the demo instructor by hand.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from worker.main import finalise_contest, grade_attempt, judge_submission, smoke_contribution

from api.deps import get_enqueue
from api.main import app
from core.config import get_settings
from db.base import sessionmaker
from db.models import Answer, Question
from exams import numeric
from judge import baselines, templates

JOBS = {"judge_submission": judge_submission, "finalise_contest": finalise_contest,
        "smoke_contribution": smoke_contribution, "grade_attempt": grade_attempt}
DE, ES = templates.source("minimal_de"), templates.source("one_plus_one_es")
RANDOM, CMAES = templates.source("random_search"), baselines.source("cmaes")
# a custom optimizer and a renamed copy of it, for the course's code-similarity panel
CUSTOM = DE.replace("0.7, 0.9", "0.6, 0.8") + (
    "\n\ndef clip_steps(steps, limit):\n    return [max(-limit, min(limit, s)) for s in steps]\n")
COPIED = CUSTOM
for old, new in [("best_x", "champion"), ("best_f", "record"), ("X", "cands"),
                 ("values", "fitness"), ("clip_steps", "bound_moves")]:
    COPIED = COPIED.replace(old, new)


async def _run(job: str, target_id: int) -> None:
    await JOBS[job]({"sandbox": False}, target_id)


@asynccontextmanager
async def _signed_in(email: str, password: str) -> AsyncIterator[AsyncClient]:
    # https so the session cookies are sent back even when they are marked Secure
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://seed") as c:
        r = await c.post("/api/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        yield c


async def _ok(response: Any) -> Any:
    if response.status_code >= 400:
        raise RuntimeError(f"{response.request.method} {response.request.url.path}: "
                           f"{response.status_code} {response.text}")
    return response.json() if response.content else None


async def _submit(c: AsyncClient, problem_id: str, dim: int, code: str,
                  contest_id: int | None = None) -> dict[str, Any]:
    sub = await _ok(await c.post("/api/submissions", json={
        "problem_id": problem_id, "dim": dim, "code": code, "contest_id": contest_id}))
    return dict(await _ok(await c.get(f"/api/submissions/{sub['id']}")))


async def seed_activity(password: str, students: list[str], instructor: str, admin: str
                        ) -> dict[str, str]:
    """Returns what to print: invite codes and where to look."""
    s = get_settings()
    s.groq_api_key = s.gemini_api_key = ""
    s.submit_cooldown_sec, s.submit_daily_cap = 0, 10_000
    app.dependency_overrides[get_enqueue] = lambda: _run
    now = datetime.now(UTC)

    def iso(offset: timedelta) -> str:
        return (now + offset).isoformat()

    try:
        async with _signed_in(instructor, password) as teacher:
            course = await _ok(await teacher.post("/api/courses", json={
                "title": "Optimization Algorithms (demo course)",
                "description": "Black-box optimization: random search, evolution "
                               "strategies, differential evolution and CMA-ES."}))
            lab = await _ok(await teacher.post("/api/courses", json={
                "title": "Metaheuristics Lab (demo course)",
                "description": "Weekly lab on the real-world problem packs."}))
            weekly = await _ok(await teacher.post("/api/contests", json={
                "title": "Weekly Challenge (demo, running)",
                "description": "Open to everyone. Rosenbrock and Rastrigin in dimension 5.",
                "tasks": [{"problem_id": "STD-003", "dim": 5}, {"problem_id": "STD-004", "dim": 5}],
                "starts_at": iso(timedelta(days=-2)), "ends_at": iso(timedelta(days=7))}))
            sprint = await _ok(await teacher.post("/api/contests", json={
                "title": "Course Sprint (demo, final ranking)",
                "description": "For the demo course. Ranked on held-out instances.",
                "tasks": [{"problem_id": "STD-001", "dim": 5}, {"problem_id": "TR-001", "dim": 5}],
                "starts_at": iso(timedelta(days=-10)), "ends_at": iso(timedelta(hours=1)),
                "course_id": course["id"], "hint_level": "concept"}))
            upcoming = await _ok(await teacher.post("/api/contests", json={
                "title": "Invitational (demo, starts in three days)",
                "description": "Invite only.", "invite_only": True,
                "tasks": [{"problem_id": "RW-002", "dim": 6}],
                "starts_at": iso(timedelta(days=3)), "ends_at": iso(timedelta(days=10))}))

            for i, email in enumerate(students):
                async with _signed_in(email, password) as c:
                    if i < 6:
                        await _ok(await c.post("/api/courses/join",
                                               json={"code": course["invite_code"]}))
                        await _ok(await c.post(f"/api/contests/{sprint['id']}/join", json={}))
                        code = [CUSTOM, COPIED, ES, DE, CMAES, RANDOM][i]
                        await _submit(c, "STD-001", 5, code, sprint["id"])
                        await _submit(c, "TR-001", 5, [DE, ES, CMAES, RANDOM, DE, ES][i],
                                      sprint["id"])
                    if i >= 4:
                        await _ok(await c.post("/api/courses/join",
                                               json={"code": lab["invite_code"]}))
                    if i < 5:
                        await _ok(await c.post(f"/api/contests/{weekly['id']}/join", json={}))
                        await _submit(c, "STD-003", 5, [ES, DE, CMAES, RANDOM, DE][i],
                                      weekly["id"])
                        await _submit(c, "STD-004", 5, [DE, CMAES, ES, DE, RANDOM][i],
                                      weekly["id"])
            await _ok(await teacher.post(f"/api/contests/{sprint['id']}/finalise"))

            # tests: one graded and closed, one open now, one draft
            quiz = await _ok(await teacher.post("/api/tests", json={
                "course_id": course["id"], "title": "Quiz 1: search basics (demo, graded)",
                "description": "Three questions, one about your own runs.",
                "starts_at": iso(timedelta(hours=-2)), "ends_at": iso(timedelta(hours=2))}))
            base = f"/api/tests/{quiz['id']}"
            await _ok(await teacher.post(f"{base}/questions", json={
                "kind": "mcq", "prompt": "Which step keeps the better of two points?",
                "points": 1, "data": {"choices": ["mutation", "selection", "crossover",
                                                  "restart"], "correct": 1}}))
            await _ok(await teacher.post(f"{base}/questions", json={
                "kind": "numeric", "prompt": numeric.GENERATORS["precision"][1], "points": 2,
                "data": {"generator": "precision"}}))
            why = await _ok(await teacher.post(f"{base}/questions", json={
                "kind": "reasoning", "points": 4,
                "prompt": "Your run stopped improving after {last_improvement_evals} "
                          "evaluations. Why?",
                "data": {"problem_id": "STD-001", "dim": 5,
                         "rubric": "Names the cause of stagnation in the student's own code "
                                   "(for example a shrinking step or no restarts)."}}))
            await _ok(await teacher.post(f"{base}/questions/{why['id']}/approve-pool", json={
                "pool": ["Your run stopped improving after {last_improvement_evals} of "
                         "{budget} evaluations. Why?",
                         "After {last_improvement_evals} evaluations your best value no "
                         "longer changed. What in your code caused that?"]}))
            await _ok(await teacher.patch(base, json={"status": "live"}))

            for i, email in enumerate(students[:5]):
                async with _signed_in(email, password) as c:
                    attempt = await _ok(await c.post(f"{base}/attempt", json={
                        "consent": True, "camera_consent": i % 2 == 0}))
                    a_mcq, a_num, a_why = attempt["answers"]
                    me = await _ok(await c.get("/api/auth/me"))
                    _, value = numeric.expected("precision", quiz["id"], me["id"],
                                                a_num["question_id"])
                    await c.put(f"/api/answers/{a_mcq['id']}", json={
                        "response": "1" if i != 3 else "0", "time_ms": 9000 + 1000 * i})
                    await c.put(f"/api/answers/{a_num['id']}", json={
                        "response": f"{value:.5f}" if i < 3 else f"{value + 1:.5f}",
                        "time_ms": 40_000})
                    await c.put(f"/api/answers/{a_why['id']}", json={
                        "response": ["The step size shrank until it stopped moving.",
                                     "Selection kept only the best point, so the population "
                                     "lost diversity.",
                                     "It never restarts once it is stuck in a basin.",
                                     "Not sure, maybe the budget ran out.",
                                     "Random sampling does not use what it has learned."][i],
                        "time_ms": 60_000, "paste_chars": 120 if i == 3 else 0})
                    events = [{"kind": "tab_hidden", "at": iso(timedelta(minutes=-30)),
                               "duration_ms": 4000}] if i in (1, 3) else []
                    if i == 3:
                        events.append({"kind": "paste", "at": iso(timedelta(minutes=-29)),
                                       "detail": "120 characters"})
                    if events:
                        await c.post(f"/api/attempts/{attempt['id']}/events", json=events)
                    await _ok(await c.post(f"/api/attempts/{attempt['id']}/submit"))

            async with sessionmaker()() as session:
                reasoning = list(await session.scalars(
                    select(Answer.id).join(Question, Question.id == Answer.question_id)
                    .where(Question.id == why["id"]).order_by(Answer.id)))
            for answer_id, (score, reason) in zip(reasoning, [
                    (4, "Correct cause, linked to the code."), (3, "Right idea, not specific."),
                    (4, "Correct."), (1, "Guess; does not match the runs.")], strict=False):
                await _ok(await teacher.post(f"/api/answers/{answer_id}/grade",
                                             json={"score": score, "reason": reason}))
            await _ok(await teacher.patch(base, json={"status": "closed"}))

            open_quiz = await _ok(await teacher.post("/api/tests", json={
                "course_id": course["id"], "title": "Quiz 2: precision (demo, open now)",
                "starts_at": iso(timedelta(hours=-1)), "ends_at": iso(timedelta(days=7)),
                "camera_checks": False}))
            await _ok(await teacher.post(f"/api/tests/{open_quiz['id']}/questions", json={
                "kind": "numeric", "prompt": numeric.GENERATORS["evaluate"][1], "points": 2,
                "data": {"generator": "evaluate"}}))
            await _ok(await teacher.post(f"/api/tests/{open_quiz['id']}/questions", json={
                "kind": "mcq", "prompt": "What does a lower AOCC mean?", "points": 1,
                "data": {"choices": ["faster convergence", "slower convergence"],
                         "correct": 1}}))
            await _ok(await teacher.patch(f"/api/tests/{open_quiz['id']}",
                                          json={"status": "live"}))
            draft = await _ok(await teacher.post("/api/tests", json={
                "course_id": lab["id"], "title": "Lab test (demo, draft)",
                "starts_at": iso(timedelta(days=5)), "ends_at": iso(timedelta(days=6))}))
            await _ok(await teacher.post(f"/api/tests/{draft['id']}/questions", json={
                "kind": "mcq", "prompt": "Which pack models exam timetabling?", "points": 1,
                "data": {"choices": ["RW-001", "RW-002", "RW-003"], "correct": 0}}))

        # contributed problems: approved and used, waiting for review, failed its check
        contributions = []
        for i, body in [(3, {"name": "Tilted bowl (demo)", "summary": "A rotated ellipsoid.",
                             "source": "import numpy as np\n\ndef f(X):\n"
                                       "    w = np.arange(1, X.shape[1] + 1)\n"
                                       "    return ((X + 0.3 * X[:, ::-1]) ** 2 * w).sum(axis=1)\n",
                             "lower": -5, "upper": 5, "dims": [5, 10], "tags": ["unimodal"]}),
                        (6, {"name": "Ridge walk (demo)", "summary": "A narrow curved valley.",
                             "source": "def f(X):\n    return (100 * (X[:, 1:] - X[:, :-1] ** 2)"
                                       " ** 2 + (1 - X[:, :-1]) ** 2).sum(axis=1)\n",
                             "lower": -3, "upper": 3, "dims": [5], "level": "Hard"}),
                        (7, {"name": "Broken (demo)", "summary": "Returns NaN on purpose.",
                             "source": "def f(X):\n    return X[:, 0] * float('nan')\n",
                             "lower": -1, "upper": 1, "dims": [5]})]:
            async with _signed_in(students[i], password) as c:
                contributions.append(await _ok(await c.post("/api/contributions", json=body)))
        async with _signed_in(admin, password) as boss:
            approved = await _ok(await boss.post(
                f"/api/admin/contributions/{contributions[0]['id']}/approve"))
        for i, code in enumerate([DE, ES, CMAES]):
            async with _signed_in(students[i], password) as c:
                await _submit(c, approved["problem_id"], 5, code)
    finally:
        app.dependency_overrides.clear()
    return {"Course invite codes": f"{course['invite_code']} (demo course), "
                                   f"{lab['invite_code']} (lab)",
            "Invitational contest code": upcoming["invite_code"],
            "Contributed problem": f"{approved['problem_id']} (approved), one pending, "
                                   "one failed its check"}
