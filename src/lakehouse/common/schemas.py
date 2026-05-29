"""Pydantic v2 schemas for customer events flowing through the pipeline."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EventType = Literal[
    "page_view",
    "click",
    "add_to_cart",
    "purchase",
    "search",
    "signup",
    "logout",
]

DeviceType = Literal["desktop", "mobile", "tablet"]

_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


class CustomerEvent(BaseModel):
    """A single customer interaction event."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: str
    user_id: str
    session_id: str
    event_type: EventType
    event_timestamp: datetime
    page_url: Optional[str] = None
    referrer: Optional[str] = None
    device_type: DeviceType
    country: str
    properties: dict[str, Any] = Field(default_factory=dict)
    revenue_usd: Optional[float] = None

    @field_validator("event_id")
    @classmethod
    def _validate_event_id(cls, v: str) -> str:
        try:
            UUID(v)
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError("event_id must be a valid UUID") from exc
        return v

    @field_validator("user_id", "session_id")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be a non-empty string")
        return v

    @field_validator("country")
    @classmethod
    def _validate_country(cls, v: str) -> str:
        if not _COUNTRY_RE.match(v):
            raise ValueError("country must be an uppercase ISO-2 code (e.g. 'US')")
        return v

    @field_validator("event_timestamp")
    @classmethod
    def _validate_timestamp(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("event_timestamp must be timezone-aware")
        if v.utcoffset() != timezone.utc.utcoffset(v):
            raise ValueError("event_timestamp must be in UTC")
        return v

    @model_validator(mode="after")
    def _validate_revenue(self) -> "CustomerEvent":
        is_purchase = self.event_type == "purchase"
        if is_purchase and self.revenue_usd is None:
            raise ValueError("revenue_usd is required for purchase events")
        if not is_purchase and self.revenue_usd is not None:
            raise ValueError("revenue_usd is only allowed for purchase events")
        if self.revenue_usd is not None and not (0 < self.revenue_usd < 100000):
            raise ValueError("revenue_usd must be > 0 and < 100000")
        return self

    def to_kafka_json(self) -> str:
        """Serialize deterministically for Kafka publishing."""
        payload = self.model_dump(mode="json")
        payload["event_timestamp"] = self.event_timestamp.astimezone(timezone.utc).isoformat()
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
