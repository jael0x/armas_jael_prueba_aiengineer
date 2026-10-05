from pathlib import Path

import pytest

from morpho.config import DEFAULT_MODELS_DIR, Settings, load_settings


def test_defaults_apply_when_nothing_is_set() -> None:
    settings = Settings.from_env({})
    assert settings.anthropic_api_key is None
    assert settings.has_api_key is False
    assert settings.llm_model == "claude-haiku-4-5"
    assert settings.embedding_model == "google/embeddinggemma-300m"
    assert settings.effort is None
    assert settings.models_dir == DEFAULT_MODELS_DIR
    assert settings.var_dir == Path("var")


def test_empty_values_from_env_example_count_as_unset() -> None:
    settings = Settings.from_env({"ANTHROPIC_API_KEY": "", "MORPHO_EFFORT": "  "})
    assert settings.anthropic_api_key is None
    assert settings.effort is None


def test_values_from_the_environment_override_defaults() -> None:
    settings = Settings.from_env(
        {
            "ANTHROPIC_API_KEY": "sk-ant-example",
            "MORPHO_LLM_MODEL": "claude-sonnet-5-5",
            "MORPHO_EFFORT": "medium",
            "MORPHO_MODELS_DIR": "/opt/models",
        }
    )
    assert settings.has_api_key is True
    assert settings.llm_model == "claude-sonnet-5-5"
    assert settings.effort == "medium"
    assert settings.models_dir == Path("/opt/models")


def test_unknown_effort_is_rejected() -> None:
    with pytest.raises(ValueError, match="MORPHO_EFFORT"):
        Settings.from_env({"MORPHO_EFFORT": "turbo"})


def test_load_settings_works_without_an_api_key() -> None:
    assert load_settings().has_api_key is False
