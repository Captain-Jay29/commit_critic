"""Git operations using GitPython."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from git import Repo
from git.exc import GitCommandError


@dataclass
class CommitInfo:
    """Information about a git commit."""

    hash: str
    short_hash: str
    message: str
    author: str
    date: datetime
    files_changed: int | list[str]  # Can be int (count) or list of file paths


@dataclass
class DiffInfo:
    """Information about staged changes."""

    files: list[str]
    additions: int
    deletions: int
    diff_text: str


def get_repo(path: str | Path | None = None) -> Repo:
    """
    Get a Git repository object.

    Args:
        path: Path to the repository. If None, uses current directory.

    Returns:
        GitPython Repo object.

    Raises:
        InvalidGitRepositoryError: If the path is not a valid git repository.
    """
    repo_path = Path(path) if path else Path.cwd()
    return Repo(repo_path, search_parent_directories=True)


def get_commits(repo: Repo, count: int = 20) -> list[CommitInfo]:
    """
    Get the last N commits from a repository.

    Args:
        repo: GitPython Repo object.
        count: Number of commits to retrieve.

    Returns:
        List of CommitInfo objects.
    """
    commits = []

    for commit in repo.iter_commits(max_count=count):
        # Get list of files changed
        try:
            files_changed: list[str] = [str(f) for f in commit.stats.files]
        except (GitCommandError, KeyError):
            files_changed = []

        # Handle message that could be bytes or str
        msg = commit.message
        if isinstance(msg, bytes):
            msg = msg.decode("utf-8", errors="replace")

        commits.append(
            CommitInfo(
                hash=commit.hexsha,
                short_hash=commit.hexsha[:7],
                message=msg.strip(),
                author=str(commit.author),
                date=datetime.fromtimestamp(commit.committed_date),
                files_changed=files_changed,
            )
        )

    return commits


def get_staged_diff(repo: Repo) -> DiffInfo | None:
    """
    Get the staged changes (diff --staged).

    Args:
        repo: GitPython Repo object.

    Returns:
        DiffInfo object if there are staged changes, None otherwise.
    """
    # Check if there are staged changes
    staged = repo.index.diff("HEAD")

    if not staged:
        return None

    # Get file names
    files = []
    for diff in staged:
        if diff.a_path:
            files.append(diff.a_path)
        elif diff.b_path:
            files.append(diff.b_path)

    # Get the actual diff text
    try:
        diff_text = repo.git.diff("--staged")
    except GitCommandError:
        diff_text = ""

    # Count additions and deletions
    additions = 0
    deletions = 0
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1

    return DiffInfo(
        files=files,
        additions=additions,
        deletions=deletions,
        diff_text=diff_text,
    )


def has_staged_changes(repo: Repo) -> bool:
    """Check if there are any staged changes."""
    return bool(repo.index.diff("HEAD"))


def get_current_branch(repo: Repo) -> str:
    """Get the name of the current branch."""
    try:
        return repo.active_branch.name
    except TypeError:
        # Detached HEAD state
        return repo.head.commit.hexsha[:7]
