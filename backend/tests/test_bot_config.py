"""Tests for Telegram bot configuration loader."""

import os
from pathlib import Path
from unittest.mock import patch
import pytest

from backend.app.bot.config import BotConfig, load_bot_config


def test_bot_config_defaults() -> None:
    """BotConfig should have sensible default attributes."""
    config = BotConfig(bot_token="test_token_123")
    assert config.bot_token == "test_token_123"
    assert config.api_base_url == "http://127.0.0.1:8000"
    assert config.web_url is None
    assert config.request_timeout == 10.0
    assert config.max_facilities == 5


def test_bot_config_repr_masks_token() -> None:
    """String representation of BotConfig must mask sensitive token."""
    config = BotConfig(bot_token="super_secret_bot_token_abc")
    repr_str = repr(config)
    assert "super_secret_bot_token_abc" not in repr_str
    assert "***" in repr_str


def test_load_bot_config_from_environment(tmp_path: Path) -> None:
    """load_bot_config should parse env variables and strip trailing slashes."""
    empty_env = tmp_path / "empty.env"
    empty_env.touch()
    env = {
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "RAKTSETU_API_BASE_URL": "http://api.local:8080/",
        "RAKTSETU_WEB_URL": "https://raktsetu.example.org/",
    }
    with patch.dict(os.environ, env, clear=True):
        config = load_bot_config(require_token=True, env_file=empty_env)
        assert config.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert config.api_base_url == "http://api.local:8080"
        assert config.web_url == "https://raktsetu.example.org"


def test_load_bot_config_missing_token_raises(tmp_path: Path) -> None:
    """load_bot_config should raise ValueError when TELEGRAM_BOT_TOKEN is missing."""
    empty_env = tmp_path / "empty.env"
    empty_env.touch()
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN environment variable is not set"):
            load_bot_config(require_token=True, env_file=empty_env)


def test_load_bot_config_offline_mode_allows_blank_token(tmp_path: Path) -> None:
    """load_bot_config should allow empty token if require_token is False."""
    empty_env = tmp_path / "empty.env"
    empty_env.touch()
    with patch.dict(os.environ, {}, clear=True):
        config = load_bot_config(require_token=False, env_file=empty_env)
        assert config.bot_token == ""
        assert config.api_base_url == "http://127.0.0.1:8000"
        assert config.web_url is None


def test_load_bot_config_from_dotenv_file(tmp_path: Path) -> None:
    """load_bot_config should load variables from a local .env file."""
    mock_env = tmp_path / ".env"
    mock_env.write_text(
        "TELEGRAM_BOT_TOKEN=synthetic_file_token_999\n"
        "RAKTSETU_API_BASE_URL=http://file-api:8000/\n"
        "RAKTSETU_WEB_URL=https://web.example.org/\n"
    )
    with patch.dict(os.environ, {}, clear=True):
        config = load_bot_config(require_token=True, env_file=mock_env)
        assert config.bot_token == "synthetic_file_token_999"
        assert config.api_base_url == "http://file-api:8000"
        assert config.web_url == "https://web.example.org"


def test_load_bot_config_shell_env_overrides_dotenv_file(tmp_path: Path) -> None:
    """Existing shell environment variables must override .env values (override=False)."""
    mock_env = tmp_path / ".env"
    mock_env.write_text(
        "TELEGRAM_BOT_TOKEN=dotenv_file_token_low_priority\n"
        "RAKTSETU_API_BASE_URL=http://dotenv-api:8000\n"
    )
    shell_env = {
        "TELEGRAM_BOT_TOKEN": "shell_token_high_priority",
        "RAKTSETU_API_BASE_URL": "http://shell-api:9000/",
    }
    with patch.dict(os.environ, shell_env, clear=True):
        config = load_bot_config(require_token=True, env_file=mock_env)
        assert config.bot_token == "shell_token_high_priority"
        assert config.api_base_url == "http://shell-api:9000"


def test_load_bot_config_nonexistent_env_file_safe() -> None:
    """load_bot_config should not crash if specified env_file does not exist."""
    nonexistent = Path("nonexistent_directory_999") / "missing.env"
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "valid_token"}, clear=True):
        config = load_bot_config(require_token=True, env_file=nonexistent)
        assert config.bot_token == "valid_token"
