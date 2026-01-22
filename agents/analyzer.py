"""Commit analyzer agent using GPT-5.2."""

from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openai import OpenAI

from ..config import get_settings
from ..vcs.operations import CommitInfo
from .prompts import (
    ANALYZER_SYSTEM_PROMPT,
    format_analyzer_prompt,
    format_memory_analyzer_prompt,
)

if TYPE_CHECKING:
    from ..memory import MemoryStore
    from ..memory.schemas import Repository


@dataclass
class AnalysisResult:
    """Result of analyzing a single commit."""

    commit: CommitInfo
    score: int
    feedback: str
    suggestion: str | None


@dataclass
class AnalysisSummary:
    """Summary statistics for analyzed commits."""

    total: int
    average_score: float
    poor_commits: int  # score 1-3
    average_commits: int  # score 4-6
    good_commits: int  # score 7-10
    vague_count: int
    one_word_count: int


class CommitAnalyzer:
    """Agent for analyzing and scoring commit messages."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)

    def analyze_commit(self, commit: CommitInfo) -> AnalysisResult:
        """
        Analyze a single commit message.

        Args:
            commit: CommitInfo object to analyze.

        Returns:
            AnalysisResult with score and feedback.
        """
        user_prompt = format_analyzer_prompt(
            message=commit.message,
            commit_hash=commit.short_hash,
            files_changed=commit.files_changed,
        )

        response = self.client.chat.completions.create(
            model=self.settings.model,
            messages=[
                {"role": "system", "content": ANALYZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("No response content from OpenAI")
        result = json.loads(content)

        return AnalysisResult(
            commit=commit,
            score=result["score"],
            feedback=result["feedback"],
            suggestion=result.get("suggestion"),
        )

    def analyze_commits(
        self,
        commits: list[CommitInfo],
    ) -> Generator[AnalysisResult, None, None]:
        """
        Analyze multiple commits, yielding results as they complete.

        Args:
            commits: List of CommitInfo objects to analyze.

        Yields:
            AnalysisResult for each commit.
        """
        for commit in commits:
            yield self.analyze_commit(commit)

    def summarize_results(self, results: list[AnalysisResult]) -> AnalysisSummary:
        """
        Generate summary statistics for analysis results.

        Args:
            results: List of AnalysisResult objects.

        Returns:
            AnalysisSummary with statistics.
        """
        if not results:
            return AnalysisSummary(
                total=0,
                average_score=0.0,
                poor_commits=0,
                average_commits=0,
                good_commits=0,
                vague_count=0,
                one_word_count=0,
            )

        scores = [r.score for r in results]
        messages = [r.commit.message for r in results]

        # Count vague and one-word commits
        vague_keywords = {"fix", "update", "change", "stuff", "wip", "misc", "changes"}
        vague_count = sum(
            1
            for m in messages
            if m.lower().strip() in vague_keywords
            or m.lower().startswith("fixed ")
            or m.lower() == "fixed bug"
        )
        one_word_count = sum(1 for m in messages if len(m.split()) == 1)

        return AnalysisSummary(
            total=len(results),
            average_score=sum(scores) / len(scores),
            poor_commits=sum(1 for s in scores if s <= 3),
            average_commits=sum(1 for s in scores if 4 <= s <= 6),
            good_commits=sum(1 for s in scores if s >= 7),
            vague_count=vague_count,
            one_word_count=one_word_count,
        )

    def analyze_commit_with_memory(
        self,
        commit: CommitInfo,
        style_pattern: str,
        uses_scopes: bool = False,
        common_scopes: list[str] | None = None,
        ticket_pattern: str | None = None,
        author_commit_count: int | None = None,
        author_avg_score: float | None = None,
        author_trend: str | None = None,
    ) -> AnalysisResult:
        """
        Analyze a commit with repository and author context.

        Args:
            commit: CommitInfo object to analyze.
            style_pattern: Repository's commit style pattern.
            uses_scopes: Whether the repo uses scopes.
            common_scopes: Common scopes used in the repo.
            ticket_pattern: Ticket reference pattern.
            author_commit_count: Author's total commit count.
            author_avg_score: Author's average score.
            author_trend: Author's trend (improving/declining/stable).

        Returns:
            AnalysisResult with personalized feedback.
        """
        user_prompt = format_memory_analyzer_prompt(
            message=commit.message,
            commit_hash=commit.short_hash,
            files_changed=commit.files_changed,
            author_name=commit.author,
            style_pattern=style_pattern,
            uses_scopes=uses_scopes,
            common_scopes=common_scopes,
            ticket_pattern=ticket_pattern,
            commit_count=author_commit_count,
            avg_score=author_avg_score,
            trend=author_trend,
        )

        response = self.client.chat.completions.create(
            model=self.settings.model,
            messages=[
                {"role": "system", "content": ANALYZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("No response content from OpenAI")
        result = json.loads(content)

        return AnalysisResult(
            commit=commit,
            score=result["score"],
            feedback=result["feedback"],
            suggestion=result.get("suggestion"),
        )

    def analyze_commits_with_memory(
        self,
        commits: list[CommitInfo],
        repository: Repository,
        store: MemoryStore,
    ) -> Generator[AnalysisResult, None, None]:
        """
        Analyze multiple commits with repository and author context from memory.

        Args:
            commits: List of CommitInfo objects to analyze.
            repository: Repository object with style context.
            store: MemoryStore for looking up collaborator info.

        Yields:
            AnalysisResult for each commit with personalized feedback.
        """
        for commit in commits:
            # Look up author in memory
            collaborator = store.get_collaborator_by_name(repository.id, commit.author)

            # Extract author context if found
            author_commit_count = None
            author_avg_score = None
            if collaborator:
                author_commit_count = collaborator.commit_count
                author_avg_score = collaborator.avg_score

            # Use memory-aware analysis
            yield self.analyze_commit_with_memory(
                commit=commit,
                style_pattern=repository.style_pattern.value,
                uses_scopes=repository.uses_scopes,
                common_scopes=repository.common_scopes,
                ticket_pattern=repository.ticket_pattern,
                author_commit_count=author_commit_count,
                author_avg_score=author_avg_score,
            )
