"""Tests for Telegram bot configuration loader."""

import os
import pytest
from unittest.mock import patch

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


def test_load_bot_config_from_environment() -> None:
    """load_bot_config should parse env variables and strip trailing slashes."""
    env = {
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "RAKTSETU_API_BASE_URL": "http://api.local:8080/",
        "RAKTSETU_WEB_URL": "https://raktsetu.example.org/",
    }
    with patch.dict(os.environ, env, clear=True):
        config = load_bot_config(require_token=True)
        assert config.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert config.api_base_url == "http://api.local:8080"
        assert config.web_url == "https://raktsetu.example.org"


def test_load_bot_config_missing_token_raises() -> None:
    """load_bot_config should raise ValueError when TELEGRAM_BOT_TOKEN is missing."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN environment variable is not set"):
            load_bot_config(require_token=True)


def test_load_bot_config_offline_mode_allows_blank_token() -> None:
    """load_bot_config should allow empty token if require_token is False."""
    with patch.dict(os.environ, {}, clear=True):
        config = load_bot_config(require_token=False)
        assert config.bot_token == ""
        assert config.api_base_url == "http://127.0.0.1:8000"
        assert config.web_url is None
