"""Tests for :mod:`lakehouse.producer.generator`."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from lakehouse.common.schemas import CustomerEvent
from lakehouse.producer.generator import (
    EVENT_TYPE_WEIGHTS,
    SESSION_MAX_EVENTS,
    SESSION_TIMEOUT,
    EventGenerator,
)


def test_generate_event_returns_valid_customer_event():
    gen = EventGenerator(user_pool_size=10, seed=42)
    event = gen.generate_event()
    assert isinstance(event, CustomerEvent)


def test_fixed_seed_yields_identical_sequences():
    gen_a = EventGenerator(user_pool_size=100, seed=2026)
    gen_b = EventGenerator(user_pool_size=100, seed=2026)

    for _ in range(20):
        a = gen_a.generate_event()
        b = gen_b.generate_event()
        assert a.event_id == b.event_id
        assert a.user_id == b.user_id
        assert a.event_type == b.event_type


def test_event_type_distribution_matches_weights():
    gen = EventGenerator(user_pool_size=500, seed=7)
    n = 10_000
    counts: dict[str, int] = {name: 0 for name, _ in EVENT_TYPE_WEIGHTS}
    for _ in range(n):
        counts[gen.generate_event().event_type] += 1

    for name, expected_weight in EVENT_TYPE_WEIGHTS:
        observed = counts[name] / n
        assert abs(observed - expected_weight) <= 0.03, (
            f"{name}: expected {expected_weight}, got {observed}"
        )


def test_revenue_is_set_iff_purchase():
    gen = EventGenerator(user_pool_size=500, seed=11)
    for _ in range(10_000):
        ev = gen.generate_event()
        if ev.event_type == "purchase":
            assert ev.revenue_usd is not None
            assert ev.revenue_usd > 0
        else:
            assert ev.revenue_usd is None


def test_session_rotates_after_max_events():
    gen = EventGenerator(user_pool_size=1, seed=1)
    sessions: list[str] = []
    for _ in range(SESSION_MAX_EVENTS + 5):
        sessions.append(gen.generate_event().session_id)

    initial = sessions[0]
    same_count = sum(1 for s in sessions if s == initial)
    assert same_count == SESSION_MAX_EVENTS
    assert sessions[SESSION_MAX_EVENTS] != initial


def test_session_rotates_after_timeout(monkeypatch: pytest.MonkeyPatch):
    gen = EventGenerator(user_pool_size=1, seed=1)
    base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    clock = {"now": base}

    def fake_now() -> datetime:
        return clock["now"]

    gen._now = fake_now  # type: ignore[attr-defined]

    first = gen.generate_event().session_id
    second = gen.generate_event().session_id
    assert first == second  # same session within timeout

    # Skip past the inactivity window.
    clock["now"] = base + SESSION_TIMEOUT + timedelta(seconds=1)
    third = gen.generate_event().session_id
    assert third != first
