"""Custom exceptions for Commit Critic."""


class CommitCriticError(Exception):
    """Base exception for Commit Critic."""

    pass


class ConfigurationError(CommitCriticError):
    """Raised when there's a configuration issue."""

    pass


class APIKeyMissingError(ConfigurationError):
    """Raised when the OpenAI API key is not configured."""

    def __init__(self, message: str = "OpenAI API key not configured") -> None:
        self.message = message
        super().__init__(self.message)


class GitError(CommitCriticError):
    """Raised when there's a git-related error."""

    pass


class NotAGitRepositoryError(GitError):
    """Raised when the current directory is not a git repository."""

    def __init__(self, path: str | None = None) -> None:
        if path:
            self.message = f"Not a git repository: {path}"
        else:
            self.message = "Not a git repository"
        super().__init__(self.message)


class NoCommitsError(GitError):
    """Raised when no commits are found in a repository."""

    def __init__(self, message: str = "No commits found in repository") -> None:
        self.message = message
        super().__init__(self.message)


class NoStagedChangesError(GitError):
    """Raised when there are no staged changes."""

    def __init__(self, message: str = "No staged changes found") -> None:
        self.message = message
        super().__init__(self.message)


class CloneError(GitError):
    """Raised when cloning a remote repository fails."""

    def __init__(self, url: str, reason: str | None = None) -> None:
        self.url = url
        if reason:
            self.message = f"Failed to clone {url}: {reason}"
        else:
            self.message = f"Failed to clone {url}"
        super().__init__(self.message)


class InvalidURLError(GitError):
    """Raised when a git URL is invalid."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.message = f"Invalid git URL: {url}"
        super().__init__(self.message)


class AIError(CommitCriticError):
    """Raised when there's an AI/OpenAI-related error."""

    pass


class AnalysisError(AIError):
    """Raised when commit analysis fails."""

    def __init__(self, commit_hash: str, reason: str | None = None) -> None:
        self.commit_hash = commit_hash
        if reason:
            self.message = f"Failed to analyze commit {commit_hash}: {reason}"
        else:
            self.message = f"Failed to analyze commit {commit_hash}"
        super().__init__(self.message)


class SuggestionError(AIError):
    """Raised when generating a commit suggestion fails."""

    def __init__(self, reason: str | None = None) -> None:
        if reason:
            self.message = f"Failed to generate suggestion: {reason}"
        else:
            self.message = "Failed to generate commit suggestion"
        super().__init__(self.message)


class EmptyResponseError(AIError):
    """Raised when OpenAI returns an empty response."""

    def __init__(self, message: str = "Empty response from OpenAI") -> None:
        self.message = message
        super().__init__(self.message)
