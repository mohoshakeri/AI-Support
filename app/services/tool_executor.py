"""Async HTTP execution of catalog tools selected by the model."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from app.config import Settings
from app.schemas.ai import AIToolCall
from app.schemas.request import HttpMethod, ParamType, ToolDefinition
from app.security.url_validation import validate_tool_endpoint_url


class ToolExecutionError(Exception):
    pass


def _coerce_arg(value: Any, param_type: ParamType) -> Any:
    if param_type == ParamType.STR:
        return str(value)
    if param_type == ParamType.INT:
        return int(value)
    if param_type == ParamType.BOOL:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return bool(value)
    raise ToolExecutionError(f"Unsupported param type: {param_type}")


def _build_payload(
    tool: ToolDefinition,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    allowed = {p.param: p for p in tool.body_params}
    unknown = set(arguments) - set(allowed)
    if unknown:
        raise ToolExecutionError(
            f"Unknown arguments for tool {tool.id}: {sorted(unknown)}"
        )

    payload: dict[str, Any] = {}
    for name, spec in allowed.items():
        if name in arguments:
            try:
                payload[name] = _coerce_arg(arguments[name], spec.type)
            except (TypeError, ValueError) as exc:
                raise ToolExecutionError(
                    f"Invalid type for argument '{name}' on tool {tool.id}: {exc}"
                ) from exc
        elif spec.required:
            raise ToolExecutionError(
                f"Missing required argument '{name}' for tool {tool.id}"
            )
    return payload


async def execute_tool_call(
    *,
    tool: ToolDefinition,
    call: AIToolCall,
    support_tool_key: str,
    settings: Settings,
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    # Re-validate at execution time (defense in depth; catalog was validated on input).
    endpoint = validate_tool_endpoint_url(tool.endpoint)
    payload = _build_payload(tool, call.arguments_dict())

    headers = {
        "SUPPORT_TOOL_KEY": support_tool_key,
        "Accept": "application/json",
    }

    method = tool.method
    timeout = settings.tool_http_timeout_seconds

    try:
        if method == HttpMethod.GET:
            response = await client.request(
                method.value,
                endpoint,
                params=payload,
                headers=headers,
                timeout=timeout,
            )
        else:
            headers["Content-Type"] = "application/json"
            response = await client.request(
                method.value,
                endpoint,
                json=payload,
                headers=headers,
                timeout=timeout,
            )
    except httpx.TimeoutException as exc:
        raise ToolExecutionError(
            f"Tool {tool.id} timed out calling {tool.title}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ToolExecutionError(
            f"Tool {tool.id} HTTP error: {exc.__class__.__name__}: {exc}"
        ) from exc

    body_text = response.text
    try:
        body_data: Any = response.json()
    except json.JSONDecodeError:
        body_data = body_text[:4000]

    return {
        "tool_id": tool.id,
        "title": tool.title,
        "status_code": response.status_code,
        "ok": response.is_success,
        "body": body_data,
    }


async def execute_tool_calls(
    *,
    tools_by_id: dict[int, ToolDefinition],
    calls: list[AIToolCall],
    support_tool_key: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(follow_redirects=False) as client:

        async def _one(call: AIToolCall) -> dict[str, Any]:
            tool = tools_by_id.get(call.tool_id)
            if tool is None:
                return {
                    "tool_id": call.tool_id,
                    "ok": False,
                    "error": f"Unknown tool_id {call.tool_id}",
                }
            try:
                return await execute_tool_call(
                    tool=tool,
                    call=call,
                    support_tool_key=support_tool_key,
                    settings=settings,
                    client=client,
                )
            except (ToolExecutionError, ValueError) as exc:
                return {
                    "tool_id": call.tool_id,
                    "title": tool.title,
                    "ok": False,
                    "error": str(exc),
                }

        results = list(await asyncio.gather(*[_one(c) for c in calls]))
        return results
