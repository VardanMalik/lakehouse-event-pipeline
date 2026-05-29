"""Synthetic customer-event generator backed by Faker."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, TypeVar
from uuid import UUID

from faker import Faker

from lakehouse.common.schemas import CustomerEvent


T = TypeVar("T")


SESSION_TIMEOUT = timedelta(minutes=30)
SESSION_MAX_EVENTS = 50

EVENT_TYPE_WEIGHTS: list[tuple[str, float]] = [
    ("page_view", 0.60),
    ("click", 0.20),
    ("search", 0.10),
    ("add_to_cart", 0.05),
    ("purchase", 0.03),
    ("signup", 0.01),
    ("logout", 0.01),
]

DEVICE_TYPE_WEIGHTS: list[tuple[str, float]] = [
    ("desktop", 0.50),
    ("mobile", 0.40),
    ("tablet", 0.10),
]

TOP_COUNTRY_WEIGHTS: list[tuple[str, float]] = [
    ("US", 0.40),
    ("IN", 0.15),
    ("GB", 0.08),
    ("DE", 0.06),
    ("FR", 0.05),
    ("BR", 0.05),
    ("JP", 0.05),
    ("CA", 0.04),
    ("AU", 0.04),
    ("MX", 0.03),
]
TOP_COUNTRY_TOTAL_WEIGHT = sum(w for _, w in TOP_COUNTRY_WEIGHTS)  # 0.95

PAGE_URL_EVENT_TYPES = {"page_view", "click", "search"}

REVENUE_LOG_MEDIAN = 50.0
REVENUE_LOG_SIGMA = 1.0
REVENUE_CAP = 5000.0


def _weighted_choice(items: list[tuple[T, float]], rng: random.Random) -> T:
    """Return one item from ``items`` chosen in proportion to its weight."""
    values = [v for v, _ in items]
    weights = [w for _, w in items]
    return rng.choices(values, weights=weights, k=1)[0]


def _uuid4_from(rng: random.Random) -> UUID:
    """Build a deterministic RFC 4122 v4 UUID from a seeded RNG."""
    bits = rng.getrandbits(128)
    # Force version 4 (bits 12-15 of time_hi_and_version).
    bits &= ~(0xF << 76)
    bits |= 0x4 << 76
    # Force variant 10xx (top 2 bits of clock_seq_hi_and_reserved).
    bits &= ~(0x3 << 62)
    bits |= 0x2 << 62
    return UUID(int=bits)


@dataclass
class _SessionState:
    session_id: str
    started_at: datetime
    event_count: int


class EventGenerator:
    """Generate synthetic :class:`CustomerEvent` instances."""

    def __init__(
        self,
        user_pool_size: int = 1000,
        seed: Optional[int] = None,
    ) -> None:
        self._rng = random.Random(seed)
        self._faker = Faker()
        if seed is not None:
            self._faker.seed_instance(seed)

        self._user_pool: list[str] = [
            str(_uuid4_from(self._rng)) for _ in range(user_pool_size)
        ]

        self._sessions: dict[str, _SessionState] = {}
        self._now: Callable[[], datetime] = _utc_now

    def generate_event(self) -> CustomerEvent:
        now = self._now()
        user_id = self._rng.choice(self._user_pool)
        session_id = self._resolve_session(user_id, now)

        event_type = _weighted_choice(EVENT_TYPE_WEIGHTS, self._rng)
        device_type = _weighted_choice(DEVICE_TYPE_WEIGHTS, self._rng)
        country = self._pick_country()

        page_url = self._faker.url() if event_type in PAGE_URL_EVENT_TYPES else None
        referrer = self._faker.url() if self._rng.random() < 0.30 else None

        properties = self._event_properties(event_type)
        revenue_usd = self._sample_revenue() if event_type == "purchase" else None

        return CustomerEvent(
            event_id=str(_uuid4_from(self._rng)),
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            event_timestamp=now,
            page_url=page_url,
            referrer=referrer,
            device_type=device_type,
            country=country,
            properties=properties,
            revenue_usd=revenue_usd,
        )

    def _resolve_session(self, user_id: str, now: datetime) -> str:
        state = self._sessions.get(user_id)
        if state is None or self._session_expired(state, now):
            state = _SessionState(
                session_id=str(_uuid4_from(self._rng)),
                started_at=now,
                event_count=0,
            )
        state.event_count += 1
        state.started_at = now
        self._sessions[user_id] = state
        return state.session_id

    @staticmethod
    def _session_expired(state: _SessionState, now: datetime) -> bool:
        if state.event_count >= SESSION_MAX_EVENTS:
            return True
        return now - state.started_at > SESSION_TIMEOUT

    def _pick_country(self) -> str:
        if self._rng.random() < TOP_COUNTRY_TOTAL_WEIGHT:
            return _weighted_choice(TOP_COUNTRY_WEIGHTS, self._rng)
        return self._faker.country_code().upper()

    def _event_properties(self, event_type: str) -> dict[str, str]:
        if event_type == "search":
            return {"query": self._faker.word()}
        if event_type == "click":
            return {"element_id": self._faker.uuid4()[:8]}
        if event_type == "page_view":
            return {"title": self._faker.sentence(nb_words=3)}
        if event_type == "add_to_cart":
            return {
                "product_id": self._faker.uuid4()[:8],
                "quantity": str(self._rng.randint(1, 5)),
            }
        if event_type == "purchase":
            return {"order_id": self._faker.uuid4()[:8]}
        if event_type == "signup":
            return {"source": self._faker.word()}
        if event_type == "logout":
            return {"reason": "user_initiated"}
        return {}

    def _sample_revenue(self) -> float:
        mu = math.log(REVENUE_LOG_MEDIAN)
        raw = self._rng.lognormvariate(mu, REVENUE_LOG_SIGMA)
        capped = min(raw, REVENUE_CAP)
        if capped <= 0:
            capped = 0.01
        return round(capped, 2)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
