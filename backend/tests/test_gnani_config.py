"""Tests for Gnani speech configuration and environment loader."""

import os
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.speech.config import (
    DEFAULT_GNANI_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_STT_FORMAT,
    DEFAULT_STT_LANGUAGE_CODE,
    DEFAULT_STT_MODEL,
    DEFAULT_TTS_LANGUAGE,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_SPEED,
    DEFAULT_TTS_VOICE,
    GnaniConfig,
    load_gnani_config,
)
from backend.app.bot.config import BotConfig, load_bot_config


def test_gnani_config_defaults() -> None:
    """Verify default values in GnaniConfig."""
    cfg = GnaniConfig()
    assert cfg.api_key == ""
    assert cfg.api_key_id is None
    assert cfg.auth_key == ""
    assert cfg.is_configured is False
    assert cfg.api_base_url == DEFAULT_GNANI_BASE_URL
    assert cfg.stt_model == DEFAULT_STT_MODEL
    assert cfg.stt_language_code == DEFAULT_STT_LANGUAGE_CODE
    assert cfg.stt_format == DEFAULT_STT_FORMAT
    assert cfg.tts_model == DEFAULT_TTS_MODEL
    assert cfg.tts_voice == DEFAULT_TTS_VOICE
    assert cfg.tts_language == DEFAULT_TTS_LANGUAGE
    assert cfg.tts_speed == DEFAULT_TTS_SPEED
    assert cfg.request_timeout == DEFAULT_REQUEST_TIMEOUT


def test_gnani_config_auth_key_precedence() -> None:
    """Verify auth_key prefers api_key_id when both are present."""
    cfg = GnaniConfig(api_key="key_123", api_key_id="id_456")
    assert cfg.is_configured is True
    assert cfg.auth_key == "id_456"

    cfg_only_key = GnaniConfig(api_key="key_only")
    assert cfg_only_key.is_configured is True
    assert cfg_only_key.auth_key == "key_only"


def test_gnani_config_repr_masks_secret() -> None:
    """Verify string repr masks the secret key."""
    cfg = GnaniConfig(api_key="super_secret_gnani_token_12345")
    repr_str = repr(cfg)
    assert "super_secret" not in repr_str
    assert "auth_key='***'" in repr_str

    cfg_empty = GnaniConfig()
    assert "auth_key='NOT_SET'" in repr(cfg_empty)


def test_load_gnani_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify loading GnaniConfig from custom environment variables."""
    monkeypatch.setenv("GNANI_API_KEY", "test-gnani-api-key")
    monkeypatch.setenv("GNANI_API_KEY_ID", "test-key-id")
    monkeypatch.setenv("GNANI_API_BASE_URL", "https://custom.gnani.internal/")
    monkeypatch.setenv("GNANI_STT_MODEL", "prisma-v2.5")
    monkeypatch.setenv("GNANI_STT_LANGUAGE_CODE", "hi-IN")
    monkeypatch.setenv("GNANI_STT_FORMAT", "verbatim")
    monkeypatch.setenv("GNANI_TTS_MODEL", "timbre-v2.5")
    monkeypatch.setenv("GNANI_TTS_VOICE", "CustomVoice")
    monkeypatch.setenv("GNANI_TTS_LANGUAGE", "en-IN")
    monkeypatch.setenv("GNANI_TTS_SPEED", "1.25")
    monkeypatch.setenv("GNANI_REQUEST_TIMEOUT", "25.0")

    cfg = load_gnani_config(require_key=True)
    assert cfg.api_key == "test-gnani-api-key"
    assert cfg.api_key_id == "test-key-id"
    assert cfg.auth_key == "test-key-id"
    assert cfg.is_configured is True
    assert cfg.api_base_url == "https://custom.gnani.internal"
    assert cfg.stt_model == "prisma-v2.5"
    assert cfg.stt_language_code == "hi-IN"
    assert cfg.stt_format == "verbatim"
    assert cfg.tts_model == "timbre-v2.5"
    assert cfg.tts_voice == "CustomVoice"
    assert cfg.tts_language == "en-IN"
    assert cfg.tts_speed == 1.25
    assert cfg.request_timeout == 25.0


def test_load_gnani_config_require_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ValueError is raised when require_key is True and key is missing."""
    monkeypatch.delenv("GNANI_API_KEY", raising=False)
    monkeypatch.delenv("GNANI_API_KEY_ID", raising=False)

    with TemporaryDirectory() as tmpdir:
        dummy_env = Path(tmpdir) / ".env"
        dummy_env.write_text("UNRELATED_KEY=value\n", encoding="utf-8")
        with pytest.raises(ValueError, match="GNANI_API_KEY"):
            load_gnani_config(require_key=True, env_file=dummy_env)


def test_load_gnani_config_invalid_numbers_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify invalid numeric env variables safely fall back to defaults."""
    monkeypatch.setenv("GNANI_TTS_SPEED", "invalid-float")
    monkeypatch.setenv("GNANI_REQUEST_TIMEOUT", "-5.0")

    with TemporaryDirectory() as tmpdir:
        dummy_env = Path(tmpdir) / ".env"
        dummy_env.write_text("", encoding="utf-8")
        cfg = load_gnani_config(require_key=False, env_file=dummy_env)
        assert cfg.tts_speed == DEFAULT_TTS_SPEED
        assert cfg.request_timeout == DEFAULT_REQUEST_TIMEOUT


def test_bot_config_includes_gnani_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify BotConfig automatically loads gnani config when requested."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    monkeypatch.setenv("GNANI_API_KEY", "gnani-token-abc")

    bot_cfg = load_bot_config(require_token=True, load_speech=True)
    assert bot_cfg.gnani is not None
    assert bot_cfg.gnani.is_configured is True
    assert "gnani-token" not in repr(bot_cfg)
    assert "auth_key='***'" in repr(bot_cfg)
