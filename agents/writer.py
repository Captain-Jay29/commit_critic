"""Commit message writer agent using GPT-5.2."""

import json
from dataclasses import dataclass

from openai import OpenAI

from ..config import get_settings
from ..vcs.operations import DiffInfo
from .prompts import (
    WRITER_SYSTEM_PROMPT,
    format_writer_prompt,
    format_memory_writer_prompt,
)


@dataclass
class CommitSuggestion:
    """Suggested commit message from the writer agent."""

    subject: str
    body: str | None
    commit_type: str
    scope: str | None
    explanation: str

    @property
    def full_message(self) -> str:
        """Get the full commit message (subject + body)."""
        if self.body:
            return f"{self.subject}\n\n{self.body}"
        return self.subject

    @property
    def formatted_subject(self) -> str:
        """Get subject with type and scope prefix."""
        if self.scope:
            return f"{self.commit_type}({self.scope}): {self.subject}"
        return f"{self.commit_type}: {self.subject}"


class CommitWriter:
    """Agent for suggesting commit messages based on staged changes."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)

    def suggest_message(self, diff: DiffInfo) -> CommitSuggestion:
        """
        Suggest a commit message for the given diff.

        Args:
            diff: DiffInfo object with staged changes.

        Returns:
            CommitSuggestion with suggested message.
        """
        user_prompt = format_writer_prompt(
            files=diff.files,
            additions=diff.additions,
            deletions=diff.deletions,
            diff_text=diff.diff_text,
        )

        response = self.client.chat.completions.create(
            model=self.settings.model,
            messages=[
                {"role": "system", "content": WRITER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("No response content from OpenAI")
        result = json.loads(content)

        return CommitSuggestion(
            subject=result["subject"],
            body=result.get("body"),
            commit_type=result["type"],
            scope=result.get("scope"),
            explanation=result["explanation"],
        )

    def regenerate_message(
        self,
        diff: DiffInfo,
        previous_suggestion: str,
        feedback: str | None = None,
    ) -> CommitSuggestion:
        """
        Regenerate a commit message with optional feedback.

        Args:
            diff: DiffInfo object with staged changes.
            previous_suggestion: The previously suggested message.
            feedback: Optional feedback on why it was rejected.

        Returns:
            New CommitSuggestion.
        """
        user_prompt = format_writer_prompt(
            files=diff.files,
            additions=diff.additions,
            deletions=diff.deletions,
            diff_text=diff.diff_text,
        )

        # Add context about previous suggestion
        if feedback:
            user_prompt += f'\n\nPrevious suggestion was: "{previous_suggestion}"\n\nUser feedback (prioritize this): {feedback}\n\nGenerate a new message that addresses this feedback.'
        else:
            user_prompt += f'\n\nPrevious suggestion was: "{previous_suggestion}"\nPlease suggest a different message.'

        response = self.client.chat.completions.create(
            model=self.settings.model,
            messages=[
                {"role": "system", "content": WRITER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.9,  # Higher temperature for variety
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("No response content from OpenAI")
        result = json.loads(content)

        return CommitSuggestion(
            subject=result["subject"],
            body=result.get("body"),
            commit_type=result["type"],
            scope=result.get("scope"),
            explanation=result["explanation"],
        )

    def suggest_message_with_memory(
        self,
        diff: DiffInfo,
        style_pattern: str,
        uses_scopes: bool = False,
        common_scopes: list[str] | None = None,
        ticket_pattern: str | None = None,
        exemplars: list[tuple[str, int]] | None = None,
    ) -> CommitSuggestion:
        """
        Suggest a commit message using repository context and exemplars.

        Args:
            diff: DiffInfo object with staged changes.
            style_pattern: Repository's commit style pattern.
            uses_scopes: Whether the repo uses scopes.
            common_scopes: Common scopes used in the repo.
            ticket_pattern: Ticket reference pattern.
            exemplars: List of (message, score) tuples for few-shot examples.

        Returns:
            CommitSuggestion with suggested message.
        """
        user_prompt = format_memory_writer_prompt(
            files=diff.files,
            additions=diff.additions,
            deletions=diff.deletions,
            diff_text=diff.diff_text,
            style_pattern=style_pattern,
            uses_scopes=uses_scopes,
            common_scopes=common_scopes,
            ticket_pattern=ticket_pattern,
            exemplars=exemplars,
        )

        response = self.client.chat.completions.create(
            model=self.settings.model,
            messages=[
                {"role": "system", "content": WRITER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("No response content from OpenAI")
        result = json.loads(content)

        return CommitSuggestion(
            subject=result["subject"],
            body=result.get("body"),
            commit_type=result["type"],
            scope=result.get("scope"),
            explanation=result["explanation"],
        )
