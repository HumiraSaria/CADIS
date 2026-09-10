"""Unit tests for get_openrouter_api_key() (newplan.md section 6 key resolution)."""

from pentestagent.config.constants import get_openrouter_api_key


def test_env_var_takes_priority(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-env-value")
    assert get_openrouter_api_key() == "sk-env-value"


def test_env_var_is_stripped(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "  sk-padded  ")
    assert get_openrouter_api_key() == "sk-padded"


def test_file_fallback_when_env_absent(monkeypatch, tmp_path):
    # No env var -> read openrouterkey.txt from the current working directory.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "openrouterkey.txt").write_text("sk-from-file\n", encoding="utf-8")
    assert get_openrouter_api_key() == "sk-from-file"
    # loaded-from-file key is exported so LiteLLM can read it from the environment
    import os

    assert os.environ.get("OPENROUTER_API_KEY") == "sk-from-file"


def test_blank_env_var_falls_back_to_file(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "   ")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "openrouterkey.txt").write_text("sk-file2", encoding="utf-8")
    assert get_openrouter_api_key() == "sk-file2"
