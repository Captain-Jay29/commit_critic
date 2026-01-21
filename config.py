"""Configuration and settings for Commit Critic."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # OpenAI settings
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-5.2"))
    embedding_model: str = Field(
        default_factory=lambda: os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    )

    # Default behavior
    default_commit_count: int = 20
    max_commit_count: int = 100
    exemplar_threshold: int = 8  # Minimum score to save as exemplar

    # Paths
    data_dir: Path = Field(
        default_factory=lambda: Path(
            os.getenv("COMMIT_CRITIC_DATA_DIR", str(Path.home() / ".commit-critic"))
        )
    )

    model_config = {"extra": "ignore"}

    @property
    def db_path(self) -> Path:
        """Path to SQLite database."""
        return self.data_dir / "memory.db"

    @property
    def cache_dir(self) -> Path:
        """Path to cache directory for cloned repos."""
        return self.data_dir / "cache" / "repos"

    def ensure_dirs(self) -> None:
        """Create necessary directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def validate_api_key(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.openai_api_key and self.openai_api_key.startswith("sk-"))


@lru_cache
def get_settings() -> Settings:
    """
    Get the global settings instance (cached).

    Settings are loaded from environment variables:
    - OPENAI_API_KEY: Required for API access
    - OPENAI_MODEL: Override default model (gpt-5.2)
    - OPENAI_EMBEDDING_MODEL: Override embedding model
    - COMMIT_CRITIC_DATA_DIR: Override data directory
    """
    return Settings()


def reload_settings() -> Settings:
    """Force reload settings (clears cache)."""
    get_settings.cache_clear()
    return get_settings()
