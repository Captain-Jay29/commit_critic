"""Extract style patterns, DNA, and antipatterns from commits."""

import json
import re
from collections import Counter
from pathlib import Path

from openai import OpenAI

from ..config import get_settings
from ..vcs.operations import CommitInfo
from .schemas import (
    AntipatternType,
    CodebaseDNA,
    CommitStyle,
    LanguageBreakdown,
    ProjectType,
    StylePattern,
)

# Common conventional commit types
CONVENTIONAL_TYPES = {"feat", "fix", "docs", "style", "refactor", "test", "chore", "perf", "ci", "build", "revert"}

# Emoji patterns (both :emoji: and unicode)
EMOJI_PATTERN = re.compile(
    r"^(?:"
    r":[a-z_]+:|"  # :emoji: style
    r"[\U0001F300-\U0001F9FF]|"  # Unicode emoji ranges
    r"[\u2600-\u26FF]|"
    r"[\u2700-\u27BF]"
    r")\s*"
)

# Common ticket patterns
TICKET_PATTERNS = [
    (r"^([A-Z]{2,10}-\d+)", "JIRA-style"),  # JIRA-123, PROJ-456
    (r"^#(\d+)", "GitHub issue"),  # #123
    (r"^\[([A-Z]{2,10}-\d+)\]", "Bracketed JIRA"),  # [JIRA-123]
]

# Language extensions mapping
LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++",
    ".cs": "C#",
    ".scala": "Scala",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".clj": "Clojure",
    ".hs": "Haskell",
    ".lua": "Lua",
    ".r": "R",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".xml": "XML",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".md": "Markdown",
    ".dockerfile": "Docker",
}

# Framework detection patterns (file patterns -> framework name)
FRAMEWORK_PATTERNS = {
    "pyproject.toml": ["typer", "fastapi", "django", "flask", "pydantic", "openai", "rich"],
    "requirements.txt": ["typer", "fastapi", "django", "flask", "pydantic", "openai", "rich"],
    "package.json": ["react", "vue", "angular", "next", "express", "nest"],
    "Cargo.toml": ["tokio", "actix", "rocket", "axum"],
    "go.mod": ["gin", "echo", "fiber", "chi"],
    "Gemfile": ["rails", "sinatra", "hanami"],
}


class StyleExtractor:
    """Extract commit style patterns from a repository."""

    def extract_style(self, commits: list[CommitInfo]) -> CommitStyle:
        """
        Analyze commits to detect the repository's commit style.

        Args:
            commits: List of commits to analyze.

        Returns:
            CommitStyle with detected patterns.
        """
        if not commits:
            return CommitStyle()

        messages = [c.message for c in commits]

        # Detect pattern type
        pattern = self._detect_pattern(messages)

        # Detect scopes
        uses_scopes, common_scopes = self._detect_scopes(messages)

        # Detect emoji usage
        uses_emoji = self._detect_emoji(messages)

        # Detect ticket pattern
        ticket_pattern = self._detect_ticket_pattern(messages)

        return CommitStyle(
            pattern=pattern,
            uses_scopes=uses_scopes,
            common_scopes=common_scopes,
            uses_emoji=uses_emoji,
            ticket_pattern=ticket_pattern,
        )

    def _detect_pattern(self, messages: list[str]) -> StylePattern:
        """Detect the predominant commit message pattern."""
        conventional_count = 0
        emoji_count = 0
        ticket_count = 0

        for msg in messages:
            msg_lower = msg.lower().strip()

            # Check for conventional commits: type(scope): or type:
            if any(msg_lower.startswith(f"{t}(") or msg_lower.startswith(f"{t}:") for t in CONVENTIONAL_TYPES):
                conventional_count += 1

            # Check for emoji
            if EMOJI_PATTERN.match(msg):
                emoji_count += 1

            # Check for tickets
            for pattern, _ in TICKET_PATTERNS:
                if re.match(pattern, msg, re.IGNORECASE):
                    ticket_count += 1
                    break

        total = len(messages)
        threshold = 0.3  # 30% of commits should follow a pattern

        if conventional_count / total >= threshold:
            return StylePattern.CONVENTIONAL
        elif emoji_count / total >= threshold:
            return StylePattern.EMOJI
        elif ticket_count / total >= threshold:
            return StylePattern.TICKET
        else:
            return StylePattern.FREEFORM

    def _detect_scopes(self, messages: list[str]) -> tuple[bool, list[str]]:
        """Detect if scopes are used and extract common ones."""
        scope_pattern = re.compile(r"^\w+\(([^)]+)\):")
        scopes: list[str] = []

        for msg in messages:
            match = scope_pattern.match(msg)
            if match:
                scopes.append(match.group(1).lower())

        if not scopes:
            return False, []

        # Count scopes and return most common
        scope_counts = Counter(scopes)
        uses_scopes = len(scopes) / len(messages) >= 0.2  # At least 20% use scopes
        common = [scope for scope, _ in scope_counts.most_common(10)]

        return uses_scopes, common

    def _detect_emoji(self, messages: list[str]) -> bool:
        """Detect if emoji are commonly used in commits."""
        emoji_count = sum(1 for msg in messages if EMOJI_PATTERN.match(msg))
        return emoji_count / len(messages) >= 0.2

    def _detect_ticket_pattern(self, messages: list[str]) -> str | None:
        """Detect the ticket reference pattern used."""
        for pattern, name in TICKET_PATTERNS:
            matches = sum(1 for msg in messages if re.match(pattern, msg, re.IGNORECASE))
            if matches / len(messages) >= 0.2:
                return pattern
        return None


class DNAExtractor:
    """Extract codebase DNA (languages, frameworks, project type)."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)

    def extract_dna(
        self,
        commits: list[CommitInfo],
        repo_path: Path | None = None,
    ) -> CodebaseDNA:
        """
        Analyze commits and optionally the repository to detect codebase DNA.

        Args:
            commits: List of commits to analyze.
            repo_path: Optional path to repository for deeper analysis.

        Returns:
            CodebaseDNA with detected characteristics.
        """
        # Extract languages from file changes
        languages = self._detect_languages(commits)

        # Extract frameworks from file content if repo_path provided
        frameworks = self._detect_frameworks(repo_path) if repo_path else []

        # Determine project type using AI
        primary_language = languages[0].language if languages else None
        project_type = self._detect_project_type(
            languages=languages,
            frameworks=frameworks,
            commit_messages=[c.message for c in commits[:20]],
        )

        return CodebaseDNA(
            primary_language=primary_language,
            languages=languages,
            frameworks=frameworks,
            project_type=project_type,
        )

    def _detect_languages(self, commits: list[CommitInfo]) -> list[LanguageBreakdown]:
        """Detect languages from file changes in commits."""
        extension_counts: Counter = Counter()

        for commit in commits:
            # Handle both list and int for files_changed
            if isinstance(commit.files_changed, list):
                for file_path in commit.files_changed:
                    ext = Path(file_path).suffix.lower()
                    if ext in LANGUAGE_EXTENSIONS:
                        extension_counts[ext] += 1

        if not extension_counts:
            return []

        # Convert to language counts
        language_counts: Counter = Counter()
        for ext, count in extension_counts.items():
            lang = LANGUAGE_EXTENSIONS.get(ext, "Unknown")
            language_counts[lang] += count

        # Calculate percentages
        total = sum(language_counts.values())
        languages = []
        for lang, count in language_counts.most_common(10):
            percentage = (count / total) * 100
            if percentage >= 1:  # Only include languages with >= 1%
                languages.append(LanguageBreakdown(language=lang, percentage=round(percentage, 1)))

        return languages

    def _detect_frameworks(self, repo_path: Path | None) -> list[str]:
        """Detect frameworks from project files."""
        if not repo_path or not repo_path.exists():
            return []

        detected = set()

        for filename, frameworks in FRAMEWORK_PATTERNS.items():
            file_path = repo_path / filename
            if file_path.exists():
                try:
                    content = file_path.read_text().lower()
                    for framework in frameworks:
                        if framework in content:
                            detected.add(framework.title())
                except Exception:
                    continue

        return sorted(detected)

    def _detect_project_type(
        self,
        languages: list[LanguageBreakdown],
        frameworks: list[str],
        commit_messages: list[str],
    ) -> ProjectType:
        """Use AI to detect project type from available signals."""
        if not languages:
            return ProjectType.UNKNOWN

        # Build context for AI
        lang_str = ", ".join(f"{l.language} ({l.percentage}%)" for l in languages[:5])
        framework_str = ", ".join(frameworks) if frameworks else "none detected"
        messages_str = "\n".join(f"- {m}" for m in commit_messages[:10])

        prompt = f"""Analyze this project and determine its type.

Languages: {lang_str}
Frameworks: {framework_str}

Recent commit messages:
{messages_str}

Respond with ONLY one of these exact values:
- cli-tool
- web-app
- web-framework
- library
- api-service
- mobile-app
- data-pipeline
- unknown"""

        try:
            response = self.client.chat.completions.create(
                model=self.settings.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=20,
            )
            result = response.choices[0].message.content
            if result:
                result = result.strip().lower()
                for pt in ProjectType:
                    if pt.value == result:
                        return pt
        except Exception:
            pass

        return ProjectType.UNKNOWN


class AntipatternExtractor:
    """Extract commit message antipatterns for roasts."""

    # Vague message patterns
    VAGUE_PATTERNS = [
        r"^fix$",
        r"^fixed$",
        r"^update$",
        r"^updates?$",
        r"^change$",
        r"^changes?$",
        r"^stuff$",
        r"^misc$",
        r"^wip$",
        r"^work in progress$",
        r"^fixed bug$",
        r"^bug fix$",
        r"^minor$",
        r"^minor changes?$",
        r"^cleanup$",
        r"^clean up$",
        r"^refactor$",
        r"^test$",
        r"^testing$",
        r"^tmp$",
        r"^temp$",
        r"^asdf+$",
        r"^\.+$",
    ]

    def extract_antipatterns(
        self,
        commits: list[CommitInfo],
    ) -> dict[str, list[tuple[str, str, int]]]:
        """
        Extract antipatterns from commits grouped by author.

        Args:
            commits: List of commits to analyze.

        Returns:
            Dict mapping author name to list of (pattern_type, example, count) tuples.
        """
        # Group commits by author
        by_author: dict[str, list[CommitInfo]] = {}
        for commit in commits:
            author = commit.author
            if author not in by_author:
                by_author[author] = []
            by_author[author].append(commit)

        # Extract antipatterns per author
        results: dict[str, list[tuple[str, str, int]]] = {}
        for author, author_commits in by_author.items():
            patterns = self._analyze_author_commits(author_commits)
            if patterns:
                results[author] = patterns

        return results

    def _analyze_author_commits(
        self,
        commits: list[CommitInfo],
    ) -> list[tuple[str, str, int]]:
        """Analyze a single author's commits for antipatterns."""
        patterns: list[tuple[str, str, int]] = []

        # Check for WIP chains
        wip_chain = self._find_wip_chain(commits)
        if wip_chain:
            patterns.append((AntipatternType.WIP_CHAIN.value, wip_chain[0], wip_chain[1]))

        # Check for one-word commits
        one_word = self._count_one_word(commits)
        if one_word[1] >= 3:  # At least 3 one-word commits
            patterns.append((AntipatternType.ONE_WORD.value, one_word[0], one_word[1]))

        # Check for vague commits
        vague = self._count_vague(commits)
        if vague[1] >= 3:  # At least 3 vague commits
            patterns.append((AntipatternType.VAGUE.value, vague[0], vague[1]))

        return patterns

    def _find_wip_chain(self, commits: list[CommitInfo]) -> tuple[str, int] | None:
        """Find chains of WIP commits."""
        max_chain = 0
        current_chain = 0
        example = ""

        for commit in commits:
            msg_lower = commit.message.lower().strip()
            if "wip" in msg_lower or msg_lower == "work in progress":
                current_chain += 1
                if current_chain > max_chain:
                    max_chain = current_chain
                    example = commit.message
            else:
                current_chain = 0

        if max_chain >= 3:  # At least 3 WIP commits in a row
            return (example, max_chain)
        return None

    def _count_one_word(self, commits: list[CommitInfo]) -> tuple[str, int]:
        """Count one-word commit messages."""
        count = 0
        example = ""

        for commit in commits:
            words = commit.message.strip().split()
            if len(words) == 1:
                count += 1
                if not example:
                    example = commit.message

        return (example, count)

    def _count_vague(self, commits: list[CommitInfo]) -> tuple[str, int]:
        """Count vague commit messages."""
        count = 0
        example = ""

        for commit in commits:
            msg_lower = commit.message.lower().strip()
            for pattern in self.VAGUE_PATTERNS:
                if re.match(pattern, msg_lower):
                    count += 1
                    if not example:
                        example = commit.message
                    break

        return (example, count)


def parse_conventional_commit(message: str) -> tuple[str | None, str | None, str]:
    """
    Parse a conventional commit message.

    Args:
        message: Commit message to parse.

    Returns:
        Tuple of (type, scope, description).
    """
    # Pattern: type(scope): description or type: description
    pattern = re.compile(r"^(\w+)(?:\(([^)]+)\))?:\s*(.+)$", re.DOTALL)
    match = pattern.match(message)

    if match:
        commit_type = match.group(1).lower()
        scope = match.group(2)
        description = match.group(3).strip()

        # Validate type
        if commit_type in CONVENTIONAL_TYPES:
            return (commit_type, scope.lower() if scope else None, description)

    # No match - return full message as description
    return (None, None, message)
