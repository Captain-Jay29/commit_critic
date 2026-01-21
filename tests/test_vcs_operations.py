"""Tests for the vcs/operations module."""

from pathlib import Path

import pytest
from git.exc import InvalidGitRepositoryError

from commit_critic.vcs.operations import (
    CommitInfo,
    DiffInfo,
    get_commits,
    get_current_branch,
    get_repo,
    get_staged_diff,
    has_staged_changes,
)


class TestGetRepo:
    """Tests for get_repo function."""

    def test_get_repo_current_dir(self, temp_git_repo):
        """Test getting repo from current directory."""
        import os

        original_dir = os.getcwd()
        try:
            os.chdir(temp_git_repo.working_dir)
            repo = get_repo()
            assert repo is not None
            # Use realpath to resolve symlinks (macOS /var -> /private/var)
            assert os.path.realpath(repo.working_dir) == os.path.realpath(temp_git_repo.working_dir)
        finally:
            os.chdir(original_dir)

    def test_get_repo_with_path(self, temp_git_repo):
        """Test getting repo with explicit path."""
        import os

        repo = get_repo(temp_git_repo.working_dir)

        assert repo is not None
        # Use realpath to resolve symlinks (macOS /var -> /private/var)
        assert os.path.realpath(repo.working_dir) == os.path.realpath(temp_git_repo.working_dir)

    def test_get_repo_invalid_path(self, tmp_path):
        """Test getting repo from non-git directory."""
        with pytest.raises(InvalidGitRepositoryError):
            get_repo(tmp_path)


class TestGetCommits:
    """Tests for get_commits function."""

    def test_get_commits_returns_list(self, temp_git_repo):
        """Test that get_commits returns a list."""
        commits = get_commits(temp_git_repo)

        assert isinstance(commits, list)
        assert len(commits) >= 1

    def test_get_commits_returns_commit_info(self, temp_git_repo):
        """Test that get_commits returns CommitInfo objects."""
        commits = get_commits(temp_git_repo)

        assert all(isinstance(c, CommitInfo) for c in commits)

    def test_get_commits_info_fields(self, temp_git_repo):
        """Test CommitInfo fields are populated."""
        commits = get_commits(temp_git_repo)
        commit = commits[0]

        assert commit.hash is not None
        assert len(commit.hash) == 40  # Full SHA
        assert commit.short_hash is not None
        assert len(commit.short_hash) == 7
        assert commit.message is not None
        assert commit.author is not None
        assert commit.date is not None

    def test_get_commits_with_count(self, temp_repo_with_commits):
        """Test limiting commit count."""
        commits = get_commits(temp_repo_with_commits, count=3)

        assert len(commits) == 3

    def test_get_commits_order(self, temp_repo_with_commits):
        """Test commits are in reverse chronological order."""
        commits = get_commits(temp_repo_with_commits, count=10)

        # Most recent commit should be first
        assert commits[0].date >= commits[-1].date


class TestGetStagedDiff:
    """Tests for get_staged_diff function."""

    def test_no_staged_changes(self, temp_git_repo):
        """Test when there are no staged changes."""
        diff = get_staged_diff(temp_git_repo)

        assert diff is None

    def test_with_staged_changes(self, temp_git_repo):
        """Test with staged changes."""
        repo_path = Path(temp_git_repo.working_dir)

        # Create and stage a new file
        new_file = repo_path / "new_feature.py"
        new_file.write_text("def hello():\n    return 'world'\n")
        temp_git_repo.index.add(["new_feature.py"])

        diff = get_staged_diff(temp_git_repo)

        assert diff is not None
        assert isinstance(diff, DiffInfo)
        assert "new_feature.py" in diff.files
        assert diff.additions > 0

    def test_staged_diff_fields(self, temp_git_repo):
        """Test DiffInfo fields are populated."""
        repo_path = Path(temp_git_repo.working_dir)

        # Modify existing file
        test_file = repo_path / "test.py"
        test_file.write_text("# Modified\nprint('hello')\n")
        temp_git_repo.index.add(["test.py"])

        diff = get_staged_diff(temp_git_repo)

        assert diff is not None
        assert isinstance(diff.files, list)
        assert isinstance(diff.additions, int)
        assert isinstance(diff.deletions, int)
        assert isinstance(diff.diff_text, str)


class TestHasStagedChanges:
    """Tests for has_staged_changes function."""

    def test_no_staged_changes(self, temp_git_repo):
        """Test when there are no staged changes."""
        assert has_staged_changes(temp_git_repo) is False

    def test_with_staged_changes(self, temp_git_repo):
        """Test when there are staged changes."""
        repo_path = Path(temp_git_repo.working_dir)

        new_file = repo_path / "staged.py"
        new_file.write_text("# Staged file\n")
        temp_git_repo.index.add(["staged.py"])

        assert has_staged_changes(temp_git_repo) is True


class TestGetCurrentBranch:
    """Tests for get_current_branch function."""

    def test_get_current_branch(self, temp_git_repo):
        """Test getting current branch name."""
        branch = get_current_branch(temp_git_repo)

        # Default branch is usually 'master' or 'main'
        assert branch in ["master", "main"]

    def test_get_current_branch_new_branch(self, temp_git_repo):
        """Test getting current branch after checkout."""
        temp_git_repo.create_head("feature-branch")
        temp_git_repo.heads["feature-branch"].checkout()

        branch = get_current_branch(temp_git_repo)

        assert branch == "feature-branch"


class TestCommitInfo:
    """Tests for CommitInfo dataclass."""

    def test_commit_info_creation(self, sample_commit_info):
        """Test creating CommitInfo."""
        assert sample_commit_info.hash == "abc123def456"
        assert sample_commit_info.short_hash == "abc123d"
        assert "OAuth2" in sample_commit_info.message
        assert sample_commit_info.files_changed == 3


class TestDiffInfo:
    """Tests for DiffInfo dataclass."""

    def test_diff_info_creation(self, sample_diff_info):
        """Test creating DiffInfo."""
        assert len(sample_diff_info.files) == 3
        assert sample_diff_info.additions == 47
        assert sample_diff_info.deletions == 12
        assert "oauth" in sample_diff_info.diff_text.lower()
