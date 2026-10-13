"""Inbound request schemas."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from app.constants import MAX_Q_LENGTH
from app.security.url_validation import validate_tool_endpoint_url


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class ToolAct(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"


class ParamType(str, Enum):
    STR = "STR"
    INT = "INT"
    BOOL = "BOOL"


class SensitivityLevel(int, Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class BodyParam(BaseModel):
    param: str = Field(..., min_length=1)
    usecase: str = ""
    type: ParamType = ParamType.STR
    limits: str = ""
    required: bool = False


class ToolDefinition(BaseModel):
    id: int
    title: str = Field(..., min_length=1)
    endpoint: str
    usecase: str = ""
    method: HttpMethod
    act: ToolAct
    body_params: list[BodyParam] = Field(default_factory=list)
    sensitivity_level: SensitivityLevel = SensitivityLevel.LOW
    developer_message: str = ""

    @field_validator("endpoint")
    @classmethod
    def endpoint_must_be_safe(cls, value: str) -> str:
        return validate_tool_endpoint_url(value)


class SystemData(BaseModel):
    note_prompt: str = ""
    knowledge: str = ""
    tools: list[ToolDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_tool_ids(self) -> SystemData:
        ids = [t.id for t in self.tools]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate tool ids in system_data.tools")
        return self


class SupportStateLiteral(str, Enum):
    ERR = "ERR"
    DONE = "DONE"
    PASS = "PASS"
    WAITING = "WAITING"


class HistoryBotResponse(BaseModel):
    support_state: SupportStateLiteral
    message_for_user: str | None = None
    message_for_admin: str | None = None
    report_for_system: str | None = None
    tools_usage: list[int] | None = None
    cost_in_usd: float | None = None


class HistoryUserItem(BaseModel):
    role: Literal["user"]
    message: str


class HistoryBotItem(BaseModel):
    role: Literal["bot"]
    response: HistoryBotResponse


HistoryItem = Annotated[Union[HistoryUserItem, HistoryBotItem], Field(discriminator="role")]


class SupportRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=MAX_Q_LENGTH)
    initial_data: Any = None
    system_data: SystemData
    history: list[HistoryItem] = Field(default_factory=list)
