"""Prompt templates for the analyzer and writer agents."""

ANALYZER_SYSTEM_PROMPT = """You are an expert at evaluating git commit messages. Your job is to score commit messages on a scale of 1-10 and provide constructive feedback.

## Scoring Criteria

**1-3 (Poor):**
- Single word commits: "fix", "update", "wip"
- Completely vague: "fixed bug", "changes", "stuff"
- No context about what or why

**4-5 (Below Average):**
- Some context but too vague: "fixed login bug"
- Missing scope or type information
- No explanation of the change

**6-7 (Average):**
- Describes what changed but not why
- Has some structure but inconsistent
- Could be more specific

**8-9 (Good):**
- Follows conventional commits or clear structure
- Specific about what changed and where
- Includes context about why when relevant
- Clear scope: feat(auth), fix(api), etc.

**10 (Excellent):**
- Perfect conventional commit format
- Crystal clear about what, where, and why
- Could be understood by anyone on the team
- Would be useful in a changelog

## Response Format

You must respond with valid JSON in this exact format:
{
    "score": <1-10>,
    "feedback": "<brief explanation of the score>",
    "suggestion": "<improved version of the commit message if score < 8, otherwise null>"
}"""

ANALYZER_USER_PROMPT = """Score this commit message:

Commit: {commit_hash}
Message: "{message}"
Files changed: {files_changed}

Respond with JSON only."""


WRITER_SYSTEM_PROMPT = """You are an expert at writing clear, informative git commit messages. Your job is to analyze code changes and suggest well-structured commit messages.

## Guidelines

1. **Use Conventional Commits format when appropriate:**
   - feat: A new feature
   - fix: A bug fix
   - docs: Documentation only changes
   - style: Formatting, missing semi colons, etc.
   - refactor: Code change that neither fixes a bug nor adds a feature
   - test: Adding missing tests
   - chore: Maintenance tasks

2. **Include scope when clear:**
   - feat(auth): add OAuth support
   - fix(api): handle rate limiting

3. **First line should be:**
   - Under 72 characters
   - Imperative mood ("add" not "added")
   - No period at the end

4. **Body (if needed):**
   - Explain what and why, not how
   - Wrap at 72 characters
   - Separate from subject with blank line

## Response Format

You must respond with valid JSON in this exact format:
{
    "subject": "<the commit subject line>",
    "body": "<optional commit body, or null>",
    "type": "<feat|fix|docs|style|refactor|test|chore>",
    "scope": "<scope or null>",
    "explanation": "<brief explanation of why you chose this message>"
}"""

WRITER_USER_PROMPT = """Analyze these staged changes and suggest a commit message:

Files changed:
{files}

Diff summary:
- {additions} additions
- {deletions} deletions

Diff content:
```
{diff_text}
```

Respond with JSON only."""


def format_analyzer_prompt(
    message: str,
    commit_hash: str,
    files_changed: int | list[str],
) -> str:
    """Format the analyzer user prompt with commit details."""
    # Handle both int and list for files_changed
    if isinstance(files_changed, list):
        files_str = f"{len(files_changed)} ({', '.join(files_changed[:5])}{'...' if len(files_changed) > 5 else ''})"
    else:
        files_str = str(files_changed)

    return ANALYZER_USER_PROMPT.format(
        message=message,
        commit_hash=commit_hash,
        files_changed=files_str,
    )


def format_writer_prompt(
    files: list[str],
    additions: int,
    deletions: int,
    diff_text: str,
) -> str:
    """Format the writer user prompt with diff details."""
    # Truncate diff if too long
    max_diff_length = 4000
    if len(diff_text) > max_diff_length:
        diff_text = diff_text[:max_diff_length] + "\n... (truncated)"

    return WRITER_USER_PROMPT.format(
        files="\n".join(f"- {f}" for f in files),
        additions=additions,
        deletions=deletions,
        diff_text=diff_text,
    )


# ============================================================================
# Memory-Aware Prompts
# ============================================================================


MEMORY_ANALYZER_CONTEXT = """
## Repository Context

This repository uses the following commit style:
- Pattern: {style_pattern}
{scope_info}
{ticket_info}

## Author Context

Author: {author_name}
- Commits analyzed: {commit_count}
- Average score: {avg_score}/10
{trend_info}

When providing feedback, reference the repository's style conventions and the author's history.
If they have patterns of poor commits, mention it constructively.
"""


MEMORY_ANALYZER_USER_PROMPT = """Score this commit message:

Commit: {commit_hash}
Author: {author_name}
Message: "{message}"
Files changed: {files_changed}

{context}

Respond with JSON only."""


MEMORY_WRITER_CONTEXT = """
## Repository Style Conventions

This repository uses:
- Style: {style_pattern}
{scope_info}
{ticket_info}

## Similar High-Quality Examples from This Repository

{exemplars}

Use these examples as inspiration for style and format.
"""


MEMORY_WRITER_USER_PROMPT = """Analyze these staged changes and suggest a commit message:

{context}

Files changed:
{files}

Diff summary:
- {additions} additions
- {deletions} deletions

Diff content:
```
{diff_text}
```

Follow the repository's conventions shown above. Respond with JSON only."""


def format_memory_analyzer_prompt(
    message: str,
    commit_hash: str,
    files_changed: int | list[str],
    author_name: str,
    style_pattern: str,
    uses_scopes: bool = False,
    common_scopes: list[str] | None = None,
    ticket_pattern: str | None = None,
    commit_count: int | None = None,
    avg_score: float | None = None,
    trend: str | None = None,
) -> str:
    """Format the memory-aware analyzer prompt."""
    # Handle both int and list for files_changed
    if isinstance(files_changed, list):
        files_str = f"{len(files_changed)} ({', '.join(files_changed[:5])}{'...' if len(files_changed) > 5 else ''})"
    else:
        files_str = str(files_changed)

    # Build scope info
    scope_info = ""
    if uses_scopes and common_scopes:
        scope_info = f"- Uses scopes: {', '.join(common_scopes[:5])}"

    # Build ticket info
    ticket_info = ""
    if ticket_pattern:
        ticket_info = f"- Ticket pattern: {ticket_pattern}"

    # Build trend info
    trend_info = ""
    if trend:
        trend_info = f"- Trend: {trend}"

    # Build context
    context = ""
    if commit_count is not None or avg_score is not None:
        context = MEMORY_ANALYZER_CONTEXT.format(
            style_pattern=style_pattern,
            scope_info=scope_info,
            ticket_info=ticket_info,
            author_name=author_name,
            commit_count=commit_count or "unknown",
            avg_score=f"{avg_score:.1f}" if avg_score else "N/A",
            trend_info=trend_info,
        )

    return MEMORY_ANALYZER_USER_PROMPT.format(
        commit_hash=commit_hash,
        author_name=author_name,
        message=message,
        files_changed=files_str,
        context=context,
    )


def format_memory_writer_prompt(
    files: list[str],
    additions: int,
    deletions: int,
    diff_text: str,
    style_pattern: str,
    uses_scopes: bool = False,
    common_scopes: list[str] | None = None,
    ticket_pattern: str | None = None,
    exemplars: list[tuple[str, int]] | None = None,  # [(message, score), ...]
) -> str:
    """Format the memory-aware writer prompt with exemplars."""
    # Truncate diff if too long
    max_diff_length = 4000
    if len(diff_text) > max_diff_length:
        diff_text = diff_text[:max_diff_length] + "\n... (truncated)"

    # Build scope info
    scope_info = ""
    if uses_scopes and common_scopes:
        scope_info = f"- Uses scopes: {', '.join(common_scopes[:5])}"

    # Build ticket info
    ticket_info = ""
    if ticket_pattern:
        ticket_info = f"- Ticket references: {ticket_pattern}"

    # Build exemplars section
    exemplars_text = ""
    if exemplars:
        exemplar_lines = []
        for msg, score in exemplars[:3]:
            exemplar_lines.append(f'- "{msg}" (score: {score}/10)')
        exemplars_text = "\n".join(exemplar_lines)
    else:
        exemplars_text = "No exemplars available yet."

    context = MEMORY_WRITER_CONTEXT.format(
        style_pattern=style_pattern,
        scope_info=scope_info,
        ticket_info=ticket_info,
        exemplars=exemplars_text,
    )

    return MEMORY_WRITER_USER_PROMPT.format(
        context=context,
        files="\n".join(f"- {f}" for f in files),
        additions=additions,
        deletions=deletions,
        diff_text=diff_text,
    )
