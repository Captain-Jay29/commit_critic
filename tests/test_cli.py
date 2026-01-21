"""Integration tests for the CLI module."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from commit_critic.cli import app

runner = CliRunner()


class TestCliVersion:
    """Tests for version command."""

    def test_version_command(self):
        """Test version command output."""
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "Commit Critic" in result.stdout
        assert "0.1.0" in result.stdout


class TestCliConfig:
    """Tests for config command."""

    def test_config_command(self, mock_openai_api_key):
        """Test config command shows settings."""
        result = runner.invoke(app, ["config"])

        assert result.exit_code == 0
        assert "Configuration" in result.stdout
        assert "Model" in result.stdout
        assert "gpt-5.2" in result.stdout

    def test_config_shows_api_key_status(self, mock_openai_api_key):
        """Test config shows API key status."""
        result = runner.invoke(app, ["config"])

        assert result.exit_code == 0
        # Should show masked key
        assert "sk-test" in result.stdout or "API Key" in result.stdout


class TestCliAnalyze:
    """Tests for analyze command."""

    def test_analyze_no_api_key(self, monkeypatch):
        """Test analyze fails without API key."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from commit_critic.config import reload_settings

        reload_settings()

        result = runner.invoke(app, ["analyze"])

        assert result.exit_code == 1
        assert "API key" in result.stdout.lower() or "not configured" in result.stdout.lower()

    def test_analyze_not_git_repo(self, mock_openai_api_key, tmp_path, monkeypatch):
        """Test analyze fails in non-git directory."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["analyze"])

        assert result.exit_code == 1
        assert "git" in result.stdout.lower() or "repository" in result.stdout.lower()

    def test_analyze_with_mock_repo(self, mock_openai_api_key, temp_repo_with_commits, monkeypatch):
        """Test analyze command with mock repo."""
        monkeypatch.chdir(temp_repo_with_commits.working_dir)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = '{"score": 7, "feedback": "Good commit", "suggestion": null}'

        with patch("commit_critic.agents.analyzer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            result = runner.invoke(app, ["analyze", "-n", "3"])

            assert result.exit_code == 0
            assert "Analyzing" in result.stdout or "STATS" in result.stdout

    def test_analyze_invalid_url(self, mock_openai_api_key):
        """Test analyze with invalid URL."""
        result = runner.invoke(app, ["analyze", "--url", "not-a-valid-url"])

        assert result.exit_code == 1
        assert "invalid" in result.stdout.lower() or "url" in result.stdout.lower()


class TestCliWrite:
    """Tests for write command."""

    def test_write_no_api_key(self, monkeypatch):
        """Test write fails without API key."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from commit_critic.config import reload_settings

        reload_settings()

        result = runner.invoke(app, ["write"])

        assert result.exit_code == 1

    def test_write_not_git_repo(self, mock_openai_api_key, tmp_path, monkeypatch):
        """Test write fails in non-git directory."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["write"])

        assert result.exit_code == 1

    def test_write_no_staged_changes(self, mock_openai_api_key, temp_git_repo, monkeypatch):
        """Test write with no staged changes."""
        monkeypatch.chdir(temp_git_repo.working_dir)

        result = runner.invoke(app, ["write"])

        assert result.exit_code == 0
        assert "staged" in result.stdout.lower() or "nothing" in result.stdout.lower()


class TestCliHelp:
    """Tests for help output."""

    def test_help_output(self):
        """Test main help output."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "analyze" in result.stdout
        assert "write" in result.stdout
        assert "config" in result.stdout

    def test_analyze_help(self):
        """Test analyze help output."""
        result = runner.invoke(app, ["analyze", "--help"])

        assert result.exit_code == 0
        # Check for option names without leading dashes due to ANSI color codes
        assert "url" in result.stdout.lower()
        assert "count" in result.stdout.lower()

    def test_write_help(self):
        """Test write help output."""
        result = runner.invoke(app, ["write", "--help"])

        assert result.exit_code == 0
