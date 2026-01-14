"""Tests for configuration module."""
from pathlib import Path

from src.config import Settings


def test_settings_defaults():
    """Test default settings values."""
    settings = Settings()
    # Database URL can be SQLite or PostgreSQL
    assert settings.database_url.startswith(("sqlite://", "postgresql://"))
    assert settings.scryfall_rate_limit_ms == 75
    assert settings.cache_ttl_hours == 24


def test_settings_override():
    """Test settings can be overridden."""
    settings = Settings(scryfall_rate_limit_ms=100, cache_ttl_hours=48)
    assert settings.scryfall_rate_limit_ms == 100
    assert settings.cache_ttl_hours == 48


def test_cache_dir_created():
    """Test cache directory is created on init."""
    settings = Settings()
    assert settings.cache_dir.exists()
    assert settings.cache_dir.is_dir()
