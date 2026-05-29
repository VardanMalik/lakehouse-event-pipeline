"""Tests for :mod:`lakehouse.common.schemas`."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from lakehouse.common.schemas import CustomerEvent


def _base_payload(**overrides):
    payload = {
        "event_id": str(uuid4()),
        "user_id": "user-1",
        "session_id": "sess-1",
        "event_type": "page_view",
        "event_timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        "page_url": "https://example.com/",
        "referrer": None,
        "device_type": "desktop",
        "country": "US",
        "properties": {"campaign": "spring"},
        "revenue_usd": None,
    }
    payload.update(overrides)
    return payload


def test_valid_page_view_event_passes():
    event = CustomerEvent(**_base_payload())
    assert event.event_type == "page_view"
    assert event.revenue_usd is None


def test_valid_purchase_event_with_revenue_passes():
    event = CustomerEvent(
        **_base_payload(event_type="purchase", revenue_usd=49.99)
    )
    assert event.event_type == "purchase"
    assert event.revenue_usd == pytest.approx(49.99)


def test_non_purchase_with_revenue_raises():
    with pytest.raises(ValidationError):
        CustomerEvent(**_base_payload(event_type="click", revenue_usd=10.0))


def test_purchase_without_revenue_raises():
    with pytest.raises(ValidationError):
        CustomerEvent(**_base_payload(event_type="purchase", revenue_usd=None))


def test_purchase_with_zero_revenue_raises():
    with pytest.raises(ValidationError):
        CustomerEvent(**_base_payload(event_type="purchase", revenue_usd=0.0))


def test_purchase_with_too_large_revenue_raises():
    with pytest.raises(ValidationError):
        CustomerEvent(**_base_payload(event_type="purchase", revenue_usd=100000.0))


def test_invalid_event_type_raises():
    with pytest.raises(ValidationError):
        CustomerEvent(**_base_payload(event_type="not_a_real_event"))


def test_non_uuid_event_id_raises():
    with pytest.raises(ValidationError):
        CustomerEvent(**_base_payload(event_id="not-a-uuid"))


def test_lowercase_country_raises():
    with pytest.raises(ValidationError):
        CustomerEvent(**_base_payload(country="us"))


def test_three_letter_country_raises():
    with pytest.raises(ValidationError):
        CustomerEvent(**_base_payload(country="USA"))


def test_naive_datetime_raises():
    with pytest.raises(ValidationError):
        CustomerEvent(**_base_payload(event_timestamp=datetime(2026, 1, 1, 12, 0)))


def test_non_utc_datetime_raises():
    from datetime import timedelta, timezone as tz

    eastern = tz(timedelta(hours=-5))
    with pytest.raises(ValidationError):
        CustomerEvent(
            **_base_payload(event_timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=eastern))
        )


def test_empty_user_id_raises():
    with pytest.raises(ValidationError):
        CustomerEvent(**_base_payload(user_id=""))


def test_to_kafka_json_round_trips():
    original = CustomerEvent(
        **_base_payload(event_type="purchase", revenue_usd=12.50)
    )
    serialized = original.to_kafka_json()
    decoded = json.loads(serialized)
    roundtripped = CustomerEvent(**decoded)
    assert roundtripped == original


def test_to_kafka_json_is_deterministic():
    event = CustomerEvent(**_base_payload())
    assert event.to_kafka_json() == event.to_kafka_json()
    decoded = json.loads(event.to_kafka_json())
    assert list(decoded.keys()) == sorted(decoded.keys())
