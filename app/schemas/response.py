"""Outbound API response schemas."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SupportState(str, Enum):
    ERR = "ERR"
    DONE = "DONE"
    PASS = "PASS"
    WAITING = "WAITING"


class SupportResponse(BaseModel):
    support_state: SupportState
    message_for_user: str | None = None
    message_for_admin: str | None = None
    report_for_system: str | None = None
    tools_usage: list[int] | None = None
    cost_in_usd: float | None = None


class JobAcceptedResponse(BaseModel):
    job_id: str


class JobStatus(str, Enum):
    PENDING = "PENDING"
    DONE = "DONE"


class JobPendingResponse(BaseModel):
    status: Literal["PENDING"] = "PENDING"
    job_id: str


class JobDoneEnvelope(BaseModel):
    status: Literal["DONE"] = "DONE"
    job_id: str
    result: SupportResponse
