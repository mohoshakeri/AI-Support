"""OpenRouter chat completions client with structured JSON schema output."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import Settings
from app.constants import OPENROUTER_BASE_URL, OPENROUTER_CHAT_PATH
from app.schemas.ai import AIDecisionRaw, decision_json_schema
from app.services.cost import CostAccumulator


class OpenRouterError(Exception):
    pass


class OpenRouterClient:
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.openrouter_api_key
        self._base_url = OPENROUTER_BASE_URL

    async def decide(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        allow_tool_calls: bool,
        cost: CostAccumulator,
    ) -> AIDecisionRaw:
        schema = decision_json_schema(allow_tool_calls=allow_tool_calls)
        schema_name = "support_decision" if allow_tool_calls else "support_final_decision"

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
            "provider": {"require_parameters": True},
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ai-support",
            "X-Title": "AI-Support",
        }

        url = f"{self._base_url}{OPENROUTER_CHAT_PATH}"
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise OpenRouterError(
                f"OpenRouter connection error: {exc.__class__.__name__}: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise OpenRouterError(
                f"OpenRouter HTTP {response.status_code}: {response.text[:2000]}"
            )

        data = response.json()
        usage = data.get("usage") or {}
        cost.add_usage(
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
        )

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterError(
                f"Malformed OpenRouter response: {json.dumps(data)[:2000]}"
            ) from exc

        if isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            content = "".join(text_parts)

        if not isinstance(content, str) or not content.strip():
            raise OpenRouterError("Empty model content from OpenRouter")

        try:
            parsed_obj = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenRouterError(
                f"Model returned non-JSON content: {content[:1000]}"
            ) from exc

        try:
            decision = AIDecisionRaw.model_validate(parsed_obj)
        except Exception as exc:
            raise OpenRouterError(
                f"Model JSON failed schema validation: {exc}; raw={content[:1000]}"
            ) from exc

        if not allow_tool_calls and decision.action == "TOOL_CALLS":
            raise OpenRouterError(
                "Validation error: model returned TOOL_CALLS on final round; rejected"
            )

        return decision
