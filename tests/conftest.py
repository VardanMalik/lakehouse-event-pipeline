"""Shared pytest fixtures for the lakehouse-event-pipeline test suite."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

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
