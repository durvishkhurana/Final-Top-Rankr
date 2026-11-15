"""The one place that talks to a language model.

Rules enforced here: provider and model come from settings; prompts are versioned
files; output is JSON validated against a Pydantic schema (one retry, then a clean
failure); every call is logged; daily limits apply; identical requests are served
from the log. Callers must never pass hidden data (instance seeds, shifts, rotations,
held-out results) into a prompt.
"""

import base64
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from string import Template
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings, get_settings
from db.models import LlmCall

PROMPTS = Path(__file__).parent / "prompts"
TRANSPORT: httpx.AsyncBaseTransport | None = None  # tests replace the network here

M = TypeVar("M", bound=BaseModel)


class AiDisabled(Exception):
    """No provider key is configured."""


class AiLimit(Exception):
    """A daily limit has been reached."""


class AiError(Exception):
    """The provider failed or returned output that does not match the schema."""


def render(prompt: str, **variables: Any) -> str:
    """prompt is a file name under ai/prompts, e.g. 'analysis.v1'. Placeholders are $name."""
    text = (PROMPTS / f"{prompt}.md").read_text(encoding="utf-8")
    return Template(text).substitute({k: str(v) for k, v in variables.items()})


def enabled(s: Settings | None = None) -> bool:
    s = s or get_settings()
    return bool(s.groq_api_key or s.gemini_api_key)


async def _groq(client: httpx.AsyncClient, s: Settings, prompt: str) -> tuple[str, int, int]:
    r = await client.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {s.groq_api_key}"},
        json={"model": s.groq_model, "temperature": 0.2,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    body = r.json()
    usage = body.get("usage", {})
    return (body["choices"][0]["message"]["content"], usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0))


async def _gemini(client: httpx.AsyncClient, s: Settings, prompt: str,
                  image: bytes | None, image_mime: str) -> tuple[str, int, int]:
    parts: list[dict[str, Any]] = [{"text": prompt}]
    if image:
        parts.append({"inline_data": {"mime_type": image_mime,
                                      "data": base64.b64encode(image).decode()}})
    r = await client.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{s.gemini_model}:generateContent",
        headers={"x-goog-api-key": s.gemini_api_key},
        json={"contents": [{"parts": parts}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}})
    r.raise_for_status()
    body = r.json()
    usage = body.get("usageMetadata", {})
    return (body["candidates"][0]["content"]["parts"][0]["text"],
            usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0))


async def _count_today(session: AsyncSession, *where: Any) -> int:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return await session.scalar(select(func.count()).select_from(LlmCall).where(
        LlmCall.created_at >= today, LlmCall.cached.is_(False), *where)) or 0


async def remaining_today(session: AsyncSession, user_id: int) -> int:
    s = get_settings()
    return max(0, min(
        s.ai_daily_limit_per_user - await _count_today(session, LlmCall.user_id == user_id),
        s.ai_daily_limit_global - await _count_today(session)))


async def ask(session: AsyncSession, *, feature: str, prompt: str, schema: type[M],
              user_id: int | None, prefer: str = "groq", image: bytes | None = None,
              image_mime: str = "image/png") -> M:
    """Sends prompt (already rendered) and returns the validated answer."""
    s = get_settings()
    full = (f"{prompt}\n\nRespond with one JSON object and nothing else. It must match this "
            f"JSON schema:\n{json.dumps(schema.model_json_schema())}")
    key = hashlib.sha256(f"{feature}\0{full}\0".encode() + (image or b"")).hexdigest()

    hit = await session.scalar(select(LlmCall).where(LlmCall.cache_key == key, LlmCall.ok)
                               .order_by(LlmCall.id.desc()).limit(1))
    if hit is not None:
        session.add(LlmCall(feature=feature, provider=hit.provider, model=hit.model,
                            user_id=user_id, cache_key=key, ok=True, cached=True,
                            response=hit.response))
        await session.commit()
        return schema.model_validate_json(hit.response)

    if not enabled(s):
        raise AiDisabled
    if user_id is not None and await remaining_today(session, user_id) <= 0:
        raise AiLimit("The daily limit for AI features has been reached. Try again tomorrow.")

    order = [prefer, "gemini" if prefer == "groq" else "groq"]
    providers = []
    for name in order:
        if name == "groq" and s.groq_api_key and image is None:
            providers.append(name)
        if (name == "gemini" and s.gemini_api_key and await _count_today(
                session, LlmCall.provider == "gemini") < s.gemini_daily_limit):
            providers.append(name)
    if not providers:
        raise AiLimit("No AI provider is available for this request today.")

    problem = "no attempt was made"
    async with httpx.AsyncClient(timeout=120, transport=TRANSPORT) as client:
        # one attempt per provider, plus one retry of the last one on unusable output
        for attempt, name in enumerate([*providers, providers[-1]]):
            model = s.groq_model if name == "groq" else s.gemini_model
            call = LlmCall(feature=feature, provider=name, model=model, user_id=user_id,
                           cache_key=key, ok=False, cached=False)
            started = time.monotonic()
            try:
                text, call.tokens_in, call.tokens_out = (
                    await _groq(client, s, full) if name == "groq"
                    else await _gemini(client, s, full, image, image_mime))
                answer = schema.model_validate_json(text)
                call.ok, call.response = True, answer.model_dump_json()
            except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
                problem = f"{name} request failed ({type(exc).__name__})"
            except ValidationError:
                problem = f"{name} returned output that does not match the expected format"
            call.latency_ms = int((time.monotonic() - started) * 1000)
            call.cost_usd = (call.tokens_in * s.llm_price_in_per_million
                             + call.tokens_out * s.llm_price_out_per_million) / 1e6
            call.error = "" if call.ok else problem
            session.add(call)
            await session.commit()
            if call.ok:
                return answer
            if attempt == len(providers) - 1 and "request failed" in problem:
                break  # the last provider is down: retrying it will not help
    raise AiError(f"The AI service could not answer: {problem}.")
