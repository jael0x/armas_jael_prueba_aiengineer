from pathlib import Path

import pytest

from morpho.config import Settings, load_settings


def test_defaults_apply_when_nothing_is_set() -> None:
    settings = Settings.from_env({})
    assert settings.openai_api_key is None
    assert settings.has_api_key is False
    assert settings.openai_base_url is None
    assert settings.llm_model == "gpt-6-luna"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.reasoning_effort == "low"
    assert settings.var_dir == Path("var")


def test_empty_values_from_env_example_count_as_unset() -> None:
    settings = Settings.from_env({"OPENAI_API_KEY": "", "OPENAI_BASE_URL": "  "})
    assert settings.openai_api_key is None
    assert settings.openai_base_url is None


def test_values_from_the_environment_override_defaults() -> None:
    settings = Settings.from_env(
        {
            "OPENAI_API_KEY": "sk-example",
            "OPENAI_BASE_URL": "https://tiendahogar.openai.azure.com/openai/v1/",
            "MORPHO_LLM_MODEL": "gpt-6.1-sol",
            "MORPHO_REASONING_EFFORT": "medium",
        }
    )
    assert settings.has_api_key is True
    assert settings.openai_base_url == "https://tiendahogar.openai.azure.com/openai/v1/"
    assert settings.llm_model == "gpt-6.1-sol"
    assert settings.reasoning_effort == "medium"


def test_unknown_reasoning_effort_is_rejected() -> None:
    with pytest.raises(ValueError, match="MORPHO_REASONING_EFFORT"):
        Settings.from_env({"MORPHO_REASONING_EFFORT": "turbo"})


def test_load_settings_works_without_an_api_key() -> None:
    assert load_settings().has_api_key is False
