"""Seeds the database. Safe to run again: existing rows are kept.

    python scripts/seed.py                 catalogue, reference values, first admin
    python scripts/seed.py --baselines     also judge the three baselines on every problem
    python scripts/seed.py --demo          also create demo users with judged submissions

Baseline and demo submissions are built-in, trusted code, so they are judged as plain
local processes (no container) to keep seeding fast. Their scores are real results of
real runs. Demo users are flagged is_demo and removed by scripts/reset.py.
"""

import argparse
import asyncio
import random
import secrets
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from api.routes.admin import baseline_user  # noqa: E402
from core.config import get_settings  # noqa: E402
from core.security import hash_password  # noqa: E402
from db.base import sessionmaker  # noqa: E402
from db.models import Problem, Submission, User  # noqa: E402
from db.results import judge_refs, store_result  # noqa: E402
from db.seed import ensure_admin, load_f_refs, sync_catalogue  # noqa: E402
from judge import baselines, templates  # noqa: E402
from judge.evaluate import judge  # noqa: E402
from judge.functions import PROBLEMS  # noqa: E402

DE, ES = templates.source("minimal_de"), templates.source("one_plus_one_es")
# (label, code): the starter templates and simple parameter variations of them
DEMO_OPTIMIZERS = [
    ("random search", templates.source("random_search")),
    ("(1+1)-ES", ES),
    ("(1+1)-ES, small steps", ES.replace("0.3 * (upper", "0.05 * (upper")),
    ("DE", DE),
    ("DE, F=0.5", DE.replace("0.7, 0.9", "0.5, 0.9")),
    ("DE, low crossover", DE.replace("0.7, 0.9", "0.7, 0.3")),
    ("DE, small population", DE.replace("10 * dim", "4 * dim")),
    ("CMA-ES", baselines.source("cmaes")),
]
DEMO_PEOPLE = [
    ("Demo Instructor", "instructor", "India", "Demo Institute of Technology"),
    ("Aarav Demo", "student", "India", "Demo Institute of Technology"),
    ("Meera Demo", "student", "India", "Demo Institute of Technology"),
    ("Kabir Demo", "student", "India", "Sample State University"),
    ("Ananya Demo", "student", "India", "Sample State University"),
    ("Lukas Demo", "student", "Germany", "Beispiel University"),
    ("Sofia Demo", "student", "Spain", "Universidad de Ejemplo"),
    ("Kenji Demo", "student", "Japan", "Example Institute"),
    ("Grace Demo", "student", "Kenya", "Example Institute"),
]


async def judge_and_store(session: AsyncSession, user: User, problem_id: str, dim: int,
                          code: str, when: datetime | None = None) -> Submission:
    sub = Submission(user_id=user.id, problem_id=problem_id, dim=dim, code=code)
    session.add(sub)
    await session.flush()
    f_ref = await judge_refs(session, problem_id, dim)
    out = await asyncio.to_thread(judge, code, PROBLEMS[problem_id], dim, f_ref=f_ref,
                                  sandbox=False)
    await store_result(session, sub, out)
    if when:
        sub.created_at, sub.finished_at = when, when + timedelta(seconds=20)
        await session.commit()
    print(f"  {user.name:<34} {problem_id} d{dim:<3} score {sub.score:>5.0f}", flush=True)
    return sub


async def seed_baselines(session: AsyncSession) -> None:
    print("Judging baselines (this takes a while)...")
    problems = list(await session.scalars(select(Problem).order_by(Problem.id)))
    for key in baselines.NAMES:
        bot = await baseline_user(session, key)
        await session.commit()
        done = set((await session.execute(
            select(Submission.problem_id, Submission.dim)
            .where(Submission.user_id == bot.id))).all())
        for problem in problems:
            for dim in problem.dims:
                if (problem.id, dim) not in done:
                    await judge_and_store(session, bot, problem.id, dim, baselines.source(key))


async def seed_demo(session: AsyncSession) -> str | None:
    if await session.scalar(select(User.id).where(User.is_demo).limit(1)):
        print("Demo users already exist; run scripts/reset.py first to recreate them.")
        return None
    print("Creating demo users and judging their submissions...")
    password = secrets.token_urlsafe(9)
    hashed = hash_password(password)
    rng = random.Random(2026)
    problem_ids = sorted(PROBLEMS)
    now = datetime.now(UTC)
    for i, (name, role, country, institution) in enumerate(DEMO_PEOPLE):
        user = User(email=f"demo{i}@topranker.invalid" if i else "instructor@topranker.invalid",
                    name=name, role=role, country=country, institution=institution,
                    password_hash=hashed, is_demo=True, email_verified=True)
        session.add(user)
        await session.commit()
        if role != "student":
            continue
        # each student tries a few optimizers on a handful of problems, improving over time
        for problem_id in rng.sample(problem_ids, rng.randint(5, 9)):
            dim = rng.choice([5, 5, 5, 10])
            picks = sorted(rng.sample(range(len(DEMO_OPTIMIZERS)), rng.randint(1, 3)))
            start = now - timedelta(days=rng.uniform(2, 29))
            for attempt, pick in enumerate(picks):
                when = min(now, start + timedelta(days=attempt * rng.uniform(0.2, 2)))
                await judge_and_store(session, user, problem_id, dim, DEMO_OPTIMIZERS[pick][1],
                                      when)
    return password


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--baselines", action="store_true")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    async with sessionmaker()() as session:
        print(f"Problems in catalogue: {await sync_catalogue(session)}")
        print(f"Reference values loaded: {await load_f_refs(session, ROOT / 'data/f_ref.json')}")
        admin = await ensure_admin(session)
        print(f"Admin: {admin.email if admin else 'not created (set ADMIN_EMAIL in .env)'}")
        if args.baselines:
            await seed_baselines(session)
        demo_password = await seed_demo(session) if args.demo else None

    s = get_settings()
    print(f"\nFrontend: {s.frontend_url}\nAPI docs: http://localhost:8000/docs")
    if admin:
        print(f"Admin login: {admin.email} / the ADMIN_PASSWORD value in .env")
    if demo_password:
        print("Demo logins (shown once, not stored anywhere):")
        print(f"  instructor@topranker.invalid / {demo_password}")
        print(f"  demo1@topranker.invalid ... demo{len(DEMO_PEOPLE) - 1}@topranker.invalid "
              f"/ {demo_password}")


if __name__ == "__main__":
    asyncio.run(main())
