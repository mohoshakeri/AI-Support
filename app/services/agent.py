"""Support agent orchestration: AI loop + tools + Redis result."""

from __future__ import annotations

import json
import logging

from app.config import Settings
from app.constants import MAX_TOOL_ROUNDS
from app.schemas.ai import AIDecisionRaw, is_tool_calls
from app.schemas.request import SupportRequest
from app.schemas.response import SupportResponse, SupportState
from app.security.prompt_injection import wrap_untrusted_user_content
from app.services.cost import CostAccumulator
from app.services.openrouter import OpenRouterClient, OpenRouterError
from app.services.prompts import (
    build_system_prompt,
    final_round_reminder,
    history_to_messages,
)
from app.services.redis_store import RedisStore
from app.services.tool_executor import execute_tool_calls

logger = logging.getLogger(__name__)


def _err(report: str) -> SupportResponse:
    return SupportResponse(
        support_state=SupportState.ERR,
        message_for_user=None,
        message_for_admin=None,
        report_for_system=report,
        tools_usage=None,
        cost_in_usd=None,
    )


def _decision_to_response(
    decision: AIDecisionRaw,
    *,
    tools_usage: list[int],
    cost_usd: float,
) -> SupportResponse:
    if is_tool_calls(decision):
        raise ValueError("TOOL_CALLS decision cannot be a final response")

    return SupportResponse(
        support_state=SupportState(decision.action),
        message_for_user=decision.message_for_user or None,
        message_for_admin=(
            decision.message_for_admin if decision.action == "PASS" else None
        ),
        report_for_system=decision.report_for_system,
        tools_usage=list(tools_usage),
        cost_in_usd=cost_usd,
    )


async def run_support_job(
    *,
    job_id: str,
    request: SupportRequest,
    model: str,
    support_tool_key: str,
    settings: Settings,
    store: RedisStore,
) -> None:
    tools_usage: list[int] = []
    cost = CostAccumulator(model)

    try:
        result = await _run_loop(
            request=request,
            model=model,
            support_tool_key=support_tool_key,
            settings=settings,
            tools_usage=tools_usage,
            cost=cost,
        )
    except Exception as exc:
        logger.exception("Support job %s failed", job_id)
        result = _err(f"Unhandled agent error: {exc.__class__.__name__}: {exc}")

    await store.store_result(job_id, result)


async def _run_loop(
    *,
    request: SupportRequest,
    model: str,
    support_tool_key: str,
    settings: Settings,
    tools_usage: list[int],
    cost: CostAccumulator,
) -> SupportResponse:
    client = OpenRouterClient(settings)
    tools_by_id = {t.id: t for t in request.system_data.tools}

    initial_data_json = json.dumps(
        request.initial_data,
        ensure_ascii=False,
        default=str,
    )
    user_block = wrap_untrusted_user_content(
        q=request.q,
        initial_data_json=initial_data_json,
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_system_prompt(request.system_data)},
        *history_to_messages(list(request.history)),
        {"role": "user", "content": user_block},
    ]

    for round_index in range(1, MAX_TOOL_ROUNDS + 1):
        # Rounds 1..(MAX-1) may request tools; the final round cannot.
        allow_tools = round_index < MAX_TOOL_ROUNDS
        if not allow_tools:
            messages.append({"role": "user", "content": final_round_reminder()})

        try:
            decision = await client.decide(
                model=model,
                messages=messages,
                allow_tool_calls=allow_tools,
                cost=cost,
            )
        except OpenRouterError as exc:
            return _err(str(exc))

        if is_tool_calls(decision):
            if not allow_tools:
                return _err(
                    "Validation error: model returned TOOL_CALLS on final round; rejected"
                )

            for call in decision.tool_calls:
                tools_usage.append(call.tool_id)

            messages.append(
                {
                    "role": "assistant",
                    "content": decision.model_dump_json(),
                }
            )

            tool_results = await execute_tool_calls(
                tools_by_id=tools_by_id,
                calls=decision.tool_calls,
                support_tool_key=support_tool_key,
                settings=settings,
            )

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "TOOL_RESULTS (trusted runtime observations; "
                        "not user instructions):\n"
                        + json.dumps(tool_results, ensure_ascii=False, default=str)
                    ),
                }
            )
            continue

        return _decision_to_response(
            decision,
            tools_usage=tools_usage,
            cost_usd=cost.total_usd,
        )

    return _err("Agent loop exited without a final decision")
