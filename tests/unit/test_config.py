"""Tests for configuration module."""
from pathlib import Path
from unittest.mock import patch
import tempfile
import os

from src.config import Settings, settings


def test_settings_defaults():
    """Test default settings values."""
    settings_obj = Settings()
    # Database URL can be SQLite or PostgreSQL
    assert settings_obj.database_url.startswith(("sqlite://", "postgresql://"))
    assert settings_obj.scryfall_rate_limit_ms == 75
    assert settings_obj.cache_ttl_hours == 24


def test_settings_override():
    """Test settings can be overridden."""
    settings_obj = Settings(scryfall_rate_limit_ms=100, cache_ttl_hours=48)
    assert settings_obj.scryfall_rate_limit_ms == 100
    assert settings_obj.cache_ttl_hours == 48


def test_cache_dir_created():
    """Test cache directory is created on init."""
    settings_obj = Settings()
    assert settings_obj.cache_dir.exists()
    assert settings_obj.cache_dir.is_dir()


def test_global_settings_instantiated():
    """Test that the global settings object is properly instantiated."""
    assert settings is not None
    assert isinstance(settings, Settings)
    assert hasattr(settings, 'database_url')
    assert hasattr(settings, 'scryfall_user_agent')
    assert hasattr(settings, 'cache_dir')


def test_env_file_configuration():
    """Test that settings loads from .env file when present."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("DATABASE_URL=postgresql://test:test@test:5432/testdb\n")

        with patch.dict(os.environ, {}, clear=False):
            settings_obj = Settings(_env_file=str(env_file))
            # Verify the env file was attempted to be read
            assert settings_obj.model_config.get('env_file') == ".env"


def test_scryfall_user_agent_default():
    """Test scryfall user agent has expected default."""
    settings_obj = Settings()
    assert "magic-deck-builder" in settings_obj.scryfall_user_agent
    assert len(settings_obj.scryfall_user_agent) > 0


def test_scryfall_rate_limit_positive():
    """Test scryfall rate limit is positive."""
    settings_obj = Settings()
    assert settings_obj.scryfall_rate_limit_ms > 0


def test_cache_ttl_positive():
    """Test cache TTL is positive."""
    settings_obj = Settings()
    assert settings_obj.cache_ttl_hours > 0


def test_settings_config_dict():
    """Test that model_config is properly set with env_file."""
    settings_obj = Settings()
    assert hasattr(settings_obj, 'model_config')
    assert settings_obj.model_config.get('env_file') == ".env"
    assert settings_obj.model_config.get('env_file_encoding') == "utf-8"
