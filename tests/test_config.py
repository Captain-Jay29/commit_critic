"""Tests for the config module."""

from pathlib import Path

from commit_critic.config import Settings, get_settings, reload_settings


class TestSettings:
    """Tests for the Settings class."""

    def test_default_settings(self, monkeypatch):
        """Test default settings values."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_EMBEDDING_MODEL", raising=False)

        settings = Settings()

        assert settings.model == "gpt-5.2"
        assert settings.embedding_model == "text-embedding-3-small"
        assert settings.default_commit_count == 20
        assert settings.max_commit_count == 100
        assert settings.exemplar_threshold == 8

    def test_api_key_from_env(self, monkeypatch):
        """Test API key loading from environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-12345")

        settings = Settings()

        assert settings.openai_api_key == "sk-test-key-12345"

    def test_model_override_from_env(self, monkeypatch):
        """Test model override from environment."""
        monkeypatch.setenv("OPENAI_MODEL", "gpt-5.2-mini")

        settings = Settings()

        assert settings.model == "gpt-5.2-mini"

    def test_data_dir_default(self, monkeypatch):
        """Test default data directory."""
        monkeypatch.delenv("COMMIT_CRITIC_DATA_DIR", raising=False)

        settings = Settings()

        assert settings.data_dir == Path.home() / ".commit-critic"

    def test_data_dir_override(self, monkeypatch):
        """Test data directory override from environment."""
        monkeypatch.setenv("COMMIT_CRITIC_DATA_DIR", "/custom/path")

        settings = Settings()

        assert settings.data_dir == Path("/custom/path")

    def test_db_path_property(self):
        """Test db_path property."""
        settings = Settings()

        assert settings.db_path == settings.data_dir / "memory.db"

    def test_cache_dir_property(self):
        """Test cache_dir property."""
        settings = Settings()

        assert settings.cache_dir == settings.data_dir / "cache" / "repos"

    def test_validate_api_key_valid(self, monkeypatch):
        """Test API key validation with valid key."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-valid-key-12345")

        settings = Settings()

        assert settings.validate_api_key() is True

    def test_validate_api_key_invalid(self, monkeypatch):
        """Test API key validation with invalid key."""
        monkeypatch.setenv("OPENAI_API_KEY", "invalid-key")

        settings = Settings()

        assert settings.validate_api_key() is False

    def test_validate_api_key_empty(self, monkeypatch):
        """Test API key validation with empty key."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        settings = Settings()

        assert settings.validate_api_key() is False

    def test_ensure_dirs(self, tmp_path, monkeypatch):
        """Test directory creation."""
        custom_dir = tmp_path / "test-commit-critic"
        monkeypatch.setenv("COMMIT_CRITIC_DATA_DIR", str(custom_dir))

        settings = Settings()
        settings.ensure_dirs()

        assert settings.data_dir.exists()
        assert settings.cache_dir.exists()


class TestGetSettings:
    """Tests for the get_settings function."""

    def test_get_settings_caching(self, monkeypatch):
        """Test that get_settings returns cached instance."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        reload_settings()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reload_settings(self, monkeypatch):
        """Test that reload_settings clears cache."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        settings1 = reload_settings()

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-456")
        settings2 = reload_settings()

        assert settings1.openai_api_key != settings2.openai_api_key
