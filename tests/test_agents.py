"""Tests for the agents module."""

from unittest.mock import MagicMock, patch

from commit_critic.agents.analyzer import (
    AnalysisResult,
    AnalysisSummary,
    CommitAnalyzer,
)
from commit_critic.agents.prompts import (
    ANALYZER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
    format_analyzer_prompt,
    format_writer_prompt,
)
from commit_critic.agents.writer import CommitSuggestion, CommitWriter


class TestAnalyzerPrompts:
    """Tests for analyzer prompts."""

    def test_analyzer_system_prompt_exists(self):
        """Test that system prompt is defined."""
        assert ANALYZER_SYSTEM_PROMPT is not None
        assert "score" in ANALYZER_SYSTEM_PROMPT.lower()

    def test_format_analyzer_prompt(self):
        """Test formatting analyzer prompt."""
        prompt = format_analyzer_prompt(
            message="feat(auth): add login",
            commit_hash="abc123",
            files_changed=5,
        )

        assert "feat(auth): add login" in prompt
        assert "abc123" in prompt
        assert "5" in prompt


class TestWriterPrompts:
    """Tests for writer prompts."""

    def test_writer_system_prompt_exists(self):
        """Test that system prompt is defined."""
        assert WRITER_SYSTEM_PROMPT is not None
        assert "commit" in WRITER_SYSTEM_PROMPT.lower()

    def test_format_writer_prompt(self):
        """Test formatting writer prompt."""
        prompt = format_writer_prompt(
            files=["auth.py", "login.py"],
            additions=10,
            deletions=5,
            diff_text="+ added line\n- removed line",
        )

        assert "auth.py" in prompt
        assert "login.py" in prompt
        assert "10" in prompt
        assert "5" in prompt

    def test_format_writer_prompt_truncates_long_diff(self):
        """Test that long diffs are truncated."""
        long_diff = "x" * 5000
        prompt = format_writer_prompt(
            files=["file.py"],
            additions=1,
            deletions=0,
            diff_text=long_diff,
        )

        assert "truncated" in prompt.lower()
        assert len(prompt) < len(long_diff) + 1000


class TestCommitAnalyzer:
    """Tests for CommitAnalyzer class."""

    def test_analyzer_init(self, mock_openai_api_key):
        """Test analyzer initialization."""
        with patch("commit_critic.agents.analyzer.OpenAI"):
            analyzer = CommitAnalyzer()
            assert analyzer.settings is not None
            assert analyzer.client is not None

    def test_analyze_commit(self, mock_openai_api_key, sample_commit_info):
        """Test analyzing a single commit."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = '{"score": 9, "feedback": "Great commit", "suggestion": null}'

        with patch("commit_critic.agents.analyzer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            analyzer = CommitAnalyzer()
            result = analyzer.analyze_commit(sample_commit_info)

            assert isinstance(result, AnalysisResult)
            assert result.score == 9
            assert result.feedback == "Great commit"
            assert result.suggestion is None
            assert result.commit == sample_commit_info

    def test_analyze_commit_with_suggestion(self, mock_openai_api_key, sample_commit_info):
        """Test analyzing a commit that gets a suggestion."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = '{"score": 3, "feedback": "Too vague", "suggestion": "fix(auth): resolve login timeout"}'

        with patch("commit_critic.agents.analyzer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            analyzer = CommitAnalyzer()
            sample_commit_info.message = "fixed bug"
            result = analyzer.analyze_commit(sample_commit_info)

            assert result.score == 3
            assert result.suggestion is not None

    def test_analyze_commits_generator(self, mock_openai_api_key, sample_commit_info):
        """Test analyzing multiple commits returns generator."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = '{"score": 8, "feedback": "Good", "suggestion": null}'

        with patch("commit_critic.agents.analyzer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            analyzer = CommitAnalyzer()
            commits = [sample_commit_info, sample_commit_info]
            results = list(analyzer.analyze_commits(commits))

            assert len(results) == 2
            assert all(isinstance(r, AnalysisResult) for r in results)

    def test_summarize_results_empty(self, mock_openai_api_key):
        """Test summarizing empty results."""
        with patch("commit_critic.agents.analyzer.OpenAI"):
            analyzer = CommitAnalyzer()
            summary = analyzer.summarize_results([])

            assert summary.total == 0
            assert summary.average_score == 0.0

    def test_summarize_results(self, mock_openai_api_key, sample_commit_info):
        """Test summarizing results."""
        with patch("commit_critic.agents.analyzer.OpenAI"):
            analyzer = CommitAnalyzer()

            results = [
                AnalysisResult(sample_commit_info, 9, "Great", None),
                AnalysisResult(sample_commit_info, 7, "Good", None),
                AnalysisResult(sample_commit_info, 3, "Poor", "Better message"),
            ]

            summary = analyzer.summarize_results(results)

            assert isinstance(summary, AnalysisSummary)
            assert summary.total == 3
            assert summary.average_score == (9 + 7 + 3) / 3
            assert summary.poor_commits == 1
            assert summary.good_commits == 2


class TestCommitWriter:
    """Tests for CommitWriter class."""

    def test_writer_init(self, mock_openai_api_key):
        """Test writer initialization."""
        with patch("commit_critic.agents.writer.OpenAI"):
            writer = CommitWriter()
            assert writer.settings is not None
            assert writer.client is not None

    def test_suggest_message(self, mock_openai_api_key, sample_diff_info):
        """Test suggesting a commit message."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """{
            "subject": "add OAuth2 authentication",
            "body": "Implement OAuth2 flow",
            "type": "feat",
            "scope": "auth",
            "explanation": "Changes add auth functionality"
        }"""

        with patch("commit_critic.agents.writer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            writer = CommitWriter()
            suggestion = writer.suggest_message(sample_diff_info)

            assert isinstance(suggestion, CommitSuggestion)
            assert suggestion.subject == "add OAuth2 authentication"
            assert suggestion.commit_type == "feat"
            assert suggestion.scope == "auth"

    def test_regenerate_message(self, mock_openai_api_key, sample_diff_info):
        """Test regenerating a commit message."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """{
            "subject": "implement secure login",
            "body": null,
            "type": "feat",
            "scope": "auth",
            "explanation": "Alternative suggestion"
        }"""

        with patch("commit_critic.agents.writer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            writer = CommitWriter()
            suggestion = writer.regenerate_message(
                sample_diff_info,
                previous_suggestion="add OAuth",
                feedback="Too short",
            )

            assert suggestion.subject == "implement secure login"


class TestCommitSuggestion:
    """Tests for CommitSuggestion dataclass."""

    def test_full_message_with_body(self):
        """Test full message property with body."""
        suggestion = CommitSuggestion(
            subject="add feature",
            body="Detailed description",
            commit_type="feat",
            scope="auth",
            explanation="test",
        )

        assert "add feature" in suggestion.full_message
        assert "Detailed description" in suggestion.full_message

    def test_full_message_without_body(self):
        """Test full message property without body."""
        suggestion = CommitSuggestion(
            subject="add feature",
            body=None,
            commit_type="feat",
            scope=None,
            explanation="test",
        )

        assert suggestion.full_message == "add feature"

    def test_formatted_subject_with_scope(self):
        """Test formatted subject with scope."""
        suggestion = CommitSuggestion(
            subject="add login",
            body=None,
            commit_type="feat",
            scope="auth",
            explanation="test",
        )

        assert suggestion.formatted_subject == "feat(auth): add login"

    def test_formatted_subject_without_scope(self):
        """Test formatted subject without scope."""
        suggestion = CommitSuggestion(
            subject="fix typo",
            body=None,
            commit_type="fix",
            scope=None,
            explanation="test",
        )

        assert suggestion.formatted_subject == "fix: fix typo"


class TestAnalysisSummary:
    """Tests for AnalysisSummary dataclass."""

    def test_summary_creation(self):
        """Test creating AnalysisSummary."""
        summary = AnalysisSummary(
            total=10,
            average_score=6.5,
            poor_commits=2,
            average_commits=5,
            good_commits=3,
            vague_count=1,
            one_word_count=1,
        )

        assert summary.total == 10
        assert summary.average_score == 6.5
        assert summary.poor_commits == 2
