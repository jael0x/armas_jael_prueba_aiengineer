"""Shared test setup: offline by default, never reading a developer's `.env` or real key."""

from __future__ import annotations

import pytest

import morpho.config

_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "MORPHO_LLM_MODEL",
    "MORPHO_EMBEDDING_MODEL",
    "MORPHO_REASONING_EFFORT",
    "MORPHO_VAR_DIR",
)


@pytest.fixture(autouse=True)
def _offline_environment(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    # Tests marked `live` talk to the real API on purpose, so they keep the real environment.
    if request.node.get_closest_marker("live"):
        return
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(morpho.config, "_read_dotenv", lambda: None)
