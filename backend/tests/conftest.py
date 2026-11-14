import os
from collections.abc import AsyncIterator

# Tests use their own database; set before anything reads the settings.
from core.config import Settings  # noqa: E402

_BASE: str = os.environ.get("DATABASE_URL") or Settings().database_url
TEST_URL = _BASE.rsplit("/", 1)[0] + "/topranker_test"
os.environ["DATABASE_URL"] = TEST_URL
os.environ["SUBMIT_COOLDOWN_SEC"] = "0"
os.environ["FRONTEND_URL"] = "http://localhost:3000"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from api.deps import get_enqueue  # noqa: E402
from api.main import app  # noqa: E402
from db.base import Base, sessionmaker  # noqa: E402
from db.seed import sync_catalogue  # noqa: E402


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
async def _database() -> AsyncIterator[None]:
    admin = create_async_engine(_BASE, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(text("DROP DATABASE IF EXISTS topranker_test WITH (FORCE)"))
            await conn.execute(text("CREATE DATABASE topranker_test"))
    except OSError:
        pytest.skip("Postgres is not running (docker compose up -d)")
    engine = create_async_engine(TEST_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield
    await admin.dispose()


@pytest.fixture
async def session(_database: None) -> AsyncIterator[AsyncSession]:
    async with sessionmaker()() as s:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await s.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        await s.commit()
        await sync_catalogue(s)
        yield s


@pytest.fixture
def queued() -> list[int]:
    """Submission ids the API asked the worker to judge."""
    return []


@pytest.fixture
async def client(session: AsyncSession, queued: list[int]) -> AsyncIterator[AsyncClient]:
    async def enqueue(job: str, target_id: int) -> None:
        if job == "judge_submission":
            queued.append(target_id)

    app.dependency_overrides[get_enqueue] = lambda: enqueue
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
