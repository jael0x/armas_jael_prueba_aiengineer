"""Runtime settings, read from the environment and from a local `.env` when present."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

DEFAULT_LLM_MODEL = "gpt-6-luna"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_REASONING_EFFORT = "low"
REASONING_EFFORTS = frozenset({"none", "low", "medium", "high", "xhigh", "max"})

# USD per 1M tokens, from developers.openai.com/api/docs/pricing (checked 2026-10-04).
PRICES_PER_MTOK: dict[str, dict[str, float]] = {
    "gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "output": 0.50},
    "text-embedding-3-small": {"input": 0.02},
}


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_base_url: str | None
    llm_model: str
    embedding_model: str
    reasoning_effort: str
    var_dir: Path

    @property
    def has_api_key(self) -> bool:
        return self.openai_api_key is not None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Settings:
        effort = _value(env, "MORPHO_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT
        if effort not in REASONING_EFFORTS:
            allowed = ", ".join(sorted(REASONING_EFFORTS))
            raise ValueError(f"MORPHO_REASONING_EFFORT={effort!r} is not one of: {allowed}")
        return cls(
            openai_api_key=_value(env, "OPENAI_API_KEY"),
            openai_base_url=_value(env, "OPENAI_BASE_URL"),
            llm_model=_value(env, "MORPHO_LLM_MODEL") or DEFAULT_LLM_MODEL,
            embedding_model=_value(env, "MORPHO_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL,
            reasoning_effort=effort,
            var_dir=Path(_value(env, "MORPHO_VAR_DIR") or "var"),
        )


def load_settings() -> Settings:
    """Settings for a real run: the process environment wins over `.env`."""
    _read_dotenv()
    return Settings.from_env(os.environ)


def _read_dotenv() -> None:
    # Looks for `.env` from the working directory up. Tests replace this with a no-op.
    load_dotenv(find_dotenv(usecwd=True), override=False)


def _value(env: Mapping[str, str], name: str) -> str | None:
    # `.env.example` ships keys with empty values; treat those as unset.
    value = env.get(name, "").strip()
    return value or None
