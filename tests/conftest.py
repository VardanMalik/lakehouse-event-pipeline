"""Shared pytest fixtures for the lakehouse-event-pipeline test suite."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Absolute path to the repository root."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def configs_dir(project_root: Path) -> Path:
    """Directory holding YAML configuration files."""
    return project_root / "configs"


@pytest.fixture()
def env_overrides(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, str]]:
    """Apply a set of environment variables for the duration of a test."""
    applied: dict[str, str] = {}

    def _apply(values: dict[str, str]) -> dict[str, str]:
        for key, value in values.items():
            monkeypatch.setenv(key, value)
            applied[key] = value
        return applied

    yield _apply  # type: ignore[misc]

    for key in list(applied.keys()):
        os.environ.pop(key, None)


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    """Ensure each test sees a fresh ``get_settings()`` cache."""
    from lakehouse.common.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_structlog() -> Iterator[None]:
    """Reset structlog's global config so a closed capsys stream can't leak."""
    import structlog

    yield
    structlog.reset_defaults()


@pytest.fixture()
def chdir_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run the test from an empty directory so the project ``.env`` is not loaded."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def sample_customer_event():
    """A minimal valid :class:`CustomerEvent` instance for use in tests."""
    from lakehouse.common.schemas import CustomerEvent

    return CustomerEvent(
        event_id=str(uuid4()),
        user_id="user-123",
        session_id="session-abc",
        event_type="page_view",
        event_timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        page_url="https://example.com/",
        referrer=None,
        device_type="desktop",
        country="US",
        properties={"campaign": "spring"},
        revenue_usd=None,
    )
