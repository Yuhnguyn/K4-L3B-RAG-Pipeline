import pytest

import src.task10_generation as generation


def test_openai_client_kwargs_defaults_without_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    kwargs = generation.openai_client_kwargs()

    assert kwargs["api_key"] == "test-key"
    assert "base_url" not in kwargs


def test_openai_client_kwargs_forwards_command_code_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "command-code-key")
    monkeypatch.setenv(
        "OPENAI_BASE_URL", "https://api.commandcode.ai/provider/v1"
    )

    kwargs = generation.openai_client_kwargs()

    assert kwargs["api_key"] == "command-code-key"
    assert kwargs["base_url"] == "https://api.commandcode.ai/provider/v1"


def test_openai_client_kwargs_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        generation.openai_client_kwargs()
