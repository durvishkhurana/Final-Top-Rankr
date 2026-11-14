from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import get_settings

from .routes import admin, auth, board, contests, courses, problems, submissions, users


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.queue = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    yield
    await app.state.queue.aclose()


app = FastAPI(title="TopRanker API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[get_settings().frontend_url],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def reject_cross_site_writes(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # Auth is cookie-based, so state-changing requests from another origin are refused.
    origin = request.headers.get("origin")
    if (request.method not in ("GET", "HEAD", "OPTIONS") and origin
            and origin != get_settings().frontend_url):
        return JSONResponse({"detail": "Cross-site request refused"}, status_code=403)
    return await call_next(request)


for module in (auth, users, problems, submissions, board, contests, courses, admin):
    app.include_router(module.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
