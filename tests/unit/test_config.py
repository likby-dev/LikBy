"""
tests/unit/test_config.py
Tests for Settings loading and validation rules.
"""

import pytest
from pydantic import SecretStr, ValidationError
from likby.config import Settings


def test_valid_settings_loading():
    settings = Settings(
        bot_token=SecretStr("123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"),
        base_url="https://api.likby.com",
        environment="development",
    )
    assert settings.environment == "development"
    assert settings.base_url == "https://api.likby.com"
    assert settings.bot_token.get_secret_value() == "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"


def test_invalid_bot_token_format_raises_error():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            bot_token=SecretStr("not-a-valid-token"),
            base_url="https://api.likby.com",
        )
    assert "Invalid Telegram bot token format" in str(exc_info.value)


def test_invalid_base_url_raises_error():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            bot_token=SecretStr("123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"),
            base_url="ftp://invalid-url.com",
        )
    assert "BASE_URL must be a valid HTTP or HTTPS URL" in str(exc_info.value)
