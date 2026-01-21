"""Pytest fixtures for Commit Critic tests."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from git import Repo

from commit_critic.config import reload_settings
from commit_critic.vcs.operations import CommitInfo, DiffInfo


@pytest.fixture
def mock_openai_api_key(monkeypatch):
    """Set a fake OpenAI API key for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-for-testing-only")
    reload_settings()
    yield
    reload_settings()


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Repo.init(tmpdir)

        # Configure git user for commits
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()

        # Create initial commit
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("# Initial file\n")
        repo.index.add(["test.py"])
        repo.index.commit("Initial commit")

        yield repo


@pytest.fixture
def temp_repo_with_commits(temp_git_repo):
    """Create a temp repo with multiple commits for testing."""
    repo = temp_git_repo
    repo_path = Path(repo.working_dir)

    # Add more commits with various message styles
    commits_data = [
        ("feat(auth): add user authentication", "auth.py", "# Auth module\n"),
        ("fix: resolve login bug", "auth.py", "# Auth module\n# Fixed\n"),
        ("wip", "temp.py", "# WIP\n"),
        ("update", "utils.py", "# Utils\n"),
        ("docs: update README", "README.md", "# Project\n"),
        ("refactor(api): extract validation logic", "api.py", "# API\n"),
    ]

    for msg, filename, content in commits_data:
        file_path = repo_path / filename
        file_path.write_text(content)
        repo.index.add([filename])
        repo.index.commit(msg)

    yield repo


@pytest.fixture
def sample_commit_info():
    """Create a sample CommitInfo for testing."""
    return CommitInfo(
        hash="abc123def456",
        short_hash="abc123d",
        message="feat(auth): add OAuth2 authentication flow",
        author="Test User",
        date=datetime.now(),
        files_changed=3,
    )


@pytest.fixture
def sample_diff_info():
    """Create a sample DiffInfo for testing."""
    return DiffInfo(
        files=["auth/login.py", "auth/oauth.py", "tests/test_auth.py"],
        additions=47,
        deletions=12,
        diff_text="""diff --git a/auth/login.py b/auth/login.py
--- a/auth/login.py
+++ b/auth/login.py
@@ -10,6 +10,15 @@ def login(username, password):
+    # Add OAuth support
+    if oauth_enabled:
+        return oauth_login(username)
     return basic_login(username, password)
""",
    )


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI API response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[
        0
    ].message.content = '{"score": 8, "feedback": "Good commit message", "suggestion": null}'
    return mock_response


@pytest.fixture
def mock_openai_writer_response():
    """Create a mock OpenAI API response for writer."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "subject": "add OAuth2 authentication",
        "body": "Implement OAuth2 flow with token refresh",
        "type": "feat",
        "scope": "auth",
        "explanation": "The changes add authentication functionality"
    }"""
    return mock_response


@pytest.fixture
def mock_openai_client(mock_openai_response):
    """Create a mock OpenAI client."""
    with patch("commit_critic.agents.analyzer.OpenAI") as mock_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_class.return_value = mock_client
        yield mock_client
