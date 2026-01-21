"""Commit analyzer agent using GPT-5.2."""

import json
from collections.abc import Generator
from dataclasses import dataclass

from openai import OpenAI

from ..config import get_settings
from ..vcs.operations import CommitInfo
from .prompts import ANALYZER_SYSTEM_PROMPT, format_analyzer_prompt


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
