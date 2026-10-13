"""Structured AI decision schemas (OpenRouter json_schema)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class AIToolArg(BaseModel):
    param: str = Field(..., min_length=1, description="Parameter name from body_params")
    value: str = Field(..., description="Argument value as string; runtime coerces types")


class AIToolCall(BaseModel):
    """Model may only choose tool id + argument values — never raw endpoints."""

    tool_id: int = Field(..., description="Numeric id of a tool from the provided catalog")
    arguments: list[AIToolArg] = Field(
        default_factory=list,
        description="Args matching the tool body_params.param names",
    )

    def arguments_dict(self) -> dict[str, Any]:
        return {item.param: item.value for item in self.arguments}


class AIDecisionRaw(BaseModel):
    """
    Flat schema sent to OpenRouter (strict-friendly).

    Unused string fields should be empty strings when not applicable.
    """

    action: Literal["TOOL_CALLS", "WAITING", "DONE", "PASS"] = Field(
        ...,
        description="Decision type for this turn",
    )
    tool_calls: list[AIToolCall] = Field(
        default_factory=list,
        description="Required when action=TOOL_CALLS; otherwise empty",
    )
    message_for_user: str = Field(
        default="",
        description="Persian user-facing message (WAITING/DONE/PASS); empty for TOOL_CALLS",
    )
    message_for_admin: str = Field(
        default="",
        description="Operational admin brief (PASS only); empty otherwise",
    )
    report_for_system: str = Field(
        ...,
        description="English developer-facing investigation report",
    )

    @field_validator(
        "message_for_user",
        "message_for_admin",
        "report_for_system",
        "tool_calls",
        mode="before",
    )
    @classmethod
    def coerce_nullables(cls, value: Any, info) -> Any:
        # Models/providers sometimes emit JSON null for unused string fields.
        if info.field_name == "tool_calls" and value is None:
            return []
        if value is None:
            return ""
        if info.field_name != "tool_calls" and isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_by_action(self) -> AIDecisionRaw:
        if self.action == "TOOL_CALLS":
            if not self.tool_calls:
                raise ValueError("tool_calls must be non-empty when action=TOOL_CALLS")
        else:
            if not self.message_for_user:
                raise ValueError(
                    f"message_for_user is required when action={self.action}"
                )
            if self.action == "PASS" and not self.message_for_admin:
                raise ValueError("message_for_admin is required when action=PASS")
            if self.tool_calls:
                raise ValueError("tool_calls must be empty unless action=TOOL_CALLS")
        if not self.report_for_system:
            raise ValueError("report_for_system is required")
        return self


def is_tool_calls(decision: AIDecisionRaw) -> bool:
    return decision.action == "TOOL_CALLS"


def decision_json_schema(*, allow_tool_calls: bool) -> dict[str, Any]:
    """Build a flat OpenRouter-compatible JSON Schema (strict-safe)."""
    actions: list[str]
    if allow_tool_calls:
        actions = ["TOOL_CALLS", "WAITING", "DONE", "PASS"]
    else:
        actions = ["WAITING", "DONE", "PASS"]

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": actions,
                "description": "Decision type for this turn",
            },
            "tool_calls": {
                "type": "array",
                "description": "Tool invocations when action=TOOL_CALLS",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "tool_id": {"type": "integer"},
                        "arguments": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "param": {"type": "string"},
                                    "value": {"type": "string"},
                                },
                                "required": ["param", "value"],
                            },
                        },
                    },
                    "required": ["tool_id", "arguments"],
                },
            },
            "message_for_user": {
                "type": "string",
                "description": "Persian user-facing message; empty for TOOL_CALLS",
            },
            "message_for_admin": {
                "type": "string",
                "description": "Operational admin brief; required for PASS else empty",
            },
            "report_for_system": {
                "type": "string",
                "description": "English developer-facing report",
            },
        },
        "required": [
            "action",
            "tool_calls",
            "message_for_user",
            "message_for_admin",
            "report_for_system",
        ],
    }
