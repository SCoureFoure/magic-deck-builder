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
    council_config_path: Path = Path("./council.yaml")
    openai_max_retries: int = 3
    openai_backoff_base_s: float = 0.5
    openai_backoff_max_s: float = 8.0

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:5173"

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def cors_allows_credentials(self) -> bool:
        origins = self.cors_origin_list()
        return "*" not in origins

    # Scryfall fallback search
    enable_scryfall_fallback: bool = True
    scryfall_fallback_limit: int = 50

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
