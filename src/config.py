"""Application configuration."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql://deckbuilder:deckbuilder@localhost:5432/magic_deck_builder"

    # Scryfall API
    scryfall_user_agent: str = "magic-deck-builder/0.1.0"
    scryfall_rate_limit_ms: int = 75

    # Cache
    cache_dir: Path = Path("./data/cache")
    cache_ttl_hours: int = 24

    # LLM (OpenAI)
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
