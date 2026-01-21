"""Remote repository cloning operations."""

import hashlib
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from git import Repo
from git.exc import GitCommandError

from ..config import get_settings


def get_repo_cache_path(url: str) -> Path:
    """
    Get the cache path for a remote repository URL.

    Args:
        url: Git repository URL.

    Returns:
        Path to the cached clone directory.
    """
    settings = get_settings()
    # Create a hash of the URL for the cache directory name
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
    # Extract repo name from URL for readability
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
    return settings.cache_dir / f"{repo_name}-{url_hash}"


def clone_remote_repo(
    url: str,
    depth: int = 50,
    use_cache: bool = True,
) -> Repo:
    """
    Clone a remote repository with shallow clone for speed.

    Args:
        url: Git repository URL (GitHub, GitLab, Bitbucket, etc.).
        depth: Number of commits to fetch (shallow clone depth).
        use_cache: Whether to use/update cached clone.

    Returns:
        GitPython Repo object.

    Raises:
        GitCommandError: If cloning fails.
    """
    settings = get_settings()
    settings.ensure_dirs()

    cache_path = get_repo_cache_path(url)

    if use_cache and cache_path.exists():
        # Update existing clone
        try:
            repo = Repo(cache_path)
            repo.remotes.origin.fetch(depth=depth)
            return repo
        except (GitCommandError, Exception):
            # Cache is corrupted, remove and re-clone
            shutil.rmtree(cache_path, ignore_errors=True)

    # Fresh clone
    repo = Repo.clone_from(
        url,
        cache_path,
        depth=depth,
        single_branch=True,
    )

    return repo


def cleanup_clone(url: str) -> None:
    """
    Remove a cached clone for a repository URL.

    Args:
        url: Git repository URL.
    """
    cache_path = get_repo_cache_path(url)
    if cache_path.exists():
        shutil.rmtree(cache_path, ignore_errors=True)


def cleanup_all_clones() -> None:
    """Remove all cached clones."""
    settings = get_settings()
    if settings.cache_dir.exists():
        shutil.rmtree(settings.cache_dir, ignore_errors=True)
        settings.cache_dir.mkdir(parents=True, exist_ok=True)


@contextmanager
def temp_clone(url: str, depth: int = 50) -> Generator[Repo, None, None]:
    """
    Context manager for temporary clone that auto-cleans up.

    Args:
        url: Git repository URL.
        depth: Number of commits to fetch.

    Yields:
        GitPython Repo object.
    """
    temp_dir = tempfile.mkdtemp(prefix="commit-critic-")
    try:
        repo = Repo.clone_from(
            url,
            temp_dir,
            depth=depth,
            single_branch=True,
        )
        yield repo
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def is_valid_git_url(url: str) -> bool:
    """
    Check if a string looks like a valid git URL.

    Args:
        url: String to check.

    Returns:
        True if it looks like a git URL.
    """
    valid_prefixes = (
        "https://github.com/",
        "https://gitlab.com/",
        "https://bitbucket.org/",
        "git@github.com:",
        "git@gitlab.com:",
        "git@bitbucket.org:",
        "https://",
        "git://",
    )
    return url.startswith(valid_prefixes)


def get_repo_name_from_url(url: str) -> str:
    """
    Extract the repository name from a git URL.

    Args:
        url: Git repository URL.

    Returns:
        Repository name (e.g., "fastapi" from "https://github.com/tiangolo/fastapi").
    """
    # Handle both HTTPS and SSH URLs
    # https://github.com/owner/repo.git -> repo
    # git@github.com:owner/repo.git -> repo
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name
