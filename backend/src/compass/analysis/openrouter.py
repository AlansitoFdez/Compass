"""Minimal REST client for OpenRouter's chat completions API -- structured extraction only.

No SDK: OpenRouter's API is OpenAI-compatible over plain REST, and httpx2 (already a
dependency) is enough for the one call this needs (see docs/phases/phase3/phase3.md).

Streams the response (`stream: true`) instead of a single blocking POST: a free-tier
reasoning model can take minutes on a full pliego with zero intermediate signal
otherwise -- indistinguishable from a hang. Streaming gives a caller real progress
(chars received, elapsed time) to log, found necessary during the 3.4 golden-set run
against real PCAPs, not a hypothetical nicety.
"""

import json
from collections.abc import Callable
from typing import Any

import httpx2
from pydantic import BaseModel

CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(Exception):
    """An inline `error` object received instead of a completion (mid-stream or not)."""


class OpenRouterUsage(BaseModel):
    """Token accounting OpenRouter reports back for one call -- the basis for the
    per-analysis cost number the design doc wants in the Fase 4 README.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float | None = None


class OpenRouterResult(BaseModel):
    """The raw structured-output content plus its usage, before Pydantic validation.

    Kept separate from parsing so a model's malformed JSON is a caller-visible failure
    mode (counted in the 3.4 comparison) rather than swallowed here.
    """

    content: str
    usage: OpenRouterUsage


# (content_chars_so_far, reasoning_chars_so_far) -- reasoning models stream a
# separate `reasoning` delta before/alongside `content`, and it's usually where
# the minutes go, so it's surfaced too instead of looking like silence.
ProgressCallback = Callable[[int, int], None]


async def extract_structured(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema: type[BaseModel],
    api_key: str,
    client: httpx2.AsyncClient,
    on_progress: ProgressCallback | None = None,
) -> OpenRouterResult:
    """Calls an OpenRouter chat model and asks for output matching `schema`.

    Args:
        model: OpenRouter model slug, e.g. "nvidia/nemotron-3-super-120b-a12b:free".
        system_prompt: System role instructions.
        user_prompt: The clause text to extract from.
        schema: Pydantic model the response must validate against.
        api_key: OpenRouter API key.
        client: The async HTTP client to call with.
        on_progress: Called after each streamed chunk with the running
            (content_chars, reasoning_chars) totals, so a caller can log
            liveness on a long call instead of waiting on it blind.

    Returns:
        The model's raw JSON content string and the token usage/cost OpenRouter reports.
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "strict": True,
                "schema": schema.model_json_schema(),
            },
        },
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    content_parts: list[str] = []
    reasoning_chars = 0
    usage: dict[str, Any] = {}

    async with client.stream(
        "POST",
        CHAT_COMPLETIONS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=180.0,
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            if "error" in chunk:
                raise OpenRouterError(chunk["error"])
            if chunk.get("usage"):
                usage = chunk["usage"]
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            if delta.get("content"):
                content_parts.append(delta["content"])
            if delta.get("reasoning"):
                reasoning_chars += len(delta["reasoning"])
            if on_progress:
                on_progress(sum(len(p) for p in content_parts), reasoning_chars)

    content = "".join(content_parts)
    if not content:
        raise OpenRouterError({"message": "empty completion (no content chunks received)"})
    return OpenRouterResult(
        content=content,
        usage=OpenRouterUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            cost=usage.get("cost"),
        ),
    )
