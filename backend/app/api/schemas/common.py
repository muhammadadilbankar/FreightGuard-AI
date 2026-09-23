"""Shared response envelopes and safe error contracts."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PaginationMeta(WireModel):
    total: int
    limit: int
    offset: int
    has_more: bool


class ResponseMeta(WireModel):
    schema_version: Literal["1.0"] = "1.0"
    snapshot_id: str | None = None
    pagination: PaginationMeta | None = None


class DataEnvelope(WireModel, Generic[T]):
    data: T
    meta: ResponseMeta


class ErrorDetail(WireModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)
    request_id: str


class ErrorResponse(WireModel):
    error: ErrorDetail
