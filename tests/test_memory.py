"""Tests for the memory module."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from commit_critic.memory.embeddings import format_commit_for_embedding, format_diff_for_embedding
from commit_critic.memory.extractor import (
    AntipatternExtractor,
    StyleExtractor,
    parse_conventional_commit,
)
from commit_critic.memory.schemas import (
    AntipatternCreate,
    AntipatternType,
    CollaboratorCreate,
    CommitStyle,
    ExemplarCreate,
    LanguageBreakdown,
    ProjectType,
    RepositoryCreate,
    StylePattern,
)
from commit_critic.memory.store import MemoryStore
from commit_critic.vcs.operations import CommitInfo

# ============================================================================
# Schema Tests
# ============================================================================


class TestSchemas:
    """Test Pydantic schema models."""

    def test_language_breakdown_creation(self):
        """Test LanguageBreakdown creation."""
        lang = LanguageBreakdown(language="Python", percentage=85.5)
        assert lang.language == "Python"
        assert lang.percentage == 85.5

    def test_commit_style_defaults(self):
        """Test CommitStyle default values."""
        style = CommitStyle()
        assert style.pattern == StylePattern.FREEFORM
        assert style.uses_scopes is False
        assert style.common_scopes == []

    def test_repository_create(self):
        """Test RepositoryCreate model."""
        repo = RepositoryCreate(
            name="test-repo",
            url="https://github.com/test/repo",
            primary_language="Python",
            project_type=ProjectType.CLI_TOOL,
            style_pattern=StylePattern.CONVENTIONAL,
        )
        assert repo.name == "test-repo"
        assert repo.project_type == ProjectType.CLI_TOOL


# ============================================================================
# Store Tests
# ============================================================================


class TestMemoryStore:
    """Test MemoryStore SQLite operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_memory.db"
            yield db_path

    @pytest.fixture
    def store(self, temp_db):
        """Create a MemoryStore with temp database."""
        return MemoryStore(db_path=temp_db)

    def test_create_repository(self, store):
        """Test creating a repository."""
        repo_data = RepositoryCreate(
            name="test-repo",
            url="https://github.com/test/repo",
            primary_language="Python",
            languages=[LanguageBreakdown(language="Python", percentage=90.0)],
            frameworks=["FastAPI", "Pydantic"],
            project_type=ProjectType.API_SERVICE,
            style_pattern=StylePattern.CONVENTIONAL,
            uses_scopes=True,
            common_scopes=["api", "auth", "docs"],
        )
        repo = store.create_repository(repo_data)

        assert repo.id is not None
        assert repo.name == "test-repo"
        assert repo.primary_language == "Python"
        assert repo.style_pattern == StylePattern.CONVENTIONAL
        assert len(repo.languages) == 1
        assert "FastAPI" in repo.frameworks

    def test_get_repository_by_name(self, store):
        """Test getting repository by name."""
        store.create_repository(RepositoryCreate(name="my-repo"))
        repo = store.get_repository_by_name("my-repo")
        assert repo is not None
        assert repo.name == "my-repo"

    def test_create_collaborator(self, store):
        """Test creating a collaborator."""
        repo = store.create_repository(RepositoryCreate(name="test-repo"))
        collab_data = CollaboratorCreate(
            repo_id=repo.id,
            name="Alice",
            email="alice@example.com",
            commit_count=50,
            avg_score=8.5,
            primary_areas=["backend/api", "tests/"],
            roast_patterns=["5x WIP commits"],
        )
        collab = store.create_collaborator(collab_data)

        assert collab.id is not None
        assert collab.name == "Alice"
        assert collab.avg_score == 8.5
        assert "backend/api" in collab.primary_areas

    def test_list_collaborators(self, store):
        """Test listing collaborators for a repository."""
        repo = store.create_repository(RepositoryCreate(name="test-repo"))
        store.create_collaborator(CollaboratorCreate(repo_id=repo.id, name="Alice", commit_count=50))
        store.create_collaborator(CollaboratorCreate(repo_id=repo.id, name="Bob", commit_count=30))

        collabs = store.list_collaborators(repo.id)
        assert len(collabs) == 2
        # Should be ordered by commit_count DESC
        assert collabs[0].name == "Alice"
        assert collabs[1].name == "Bob"

    def test_create_exemplar(self, store):
        """Test creating an exemplar."""
        repo = store.create_repository(RepositoryCreate(name="test-repo"))
        exemplar_data = ExemplarCreate(
            repo_id=repo.id,
            commit_hash="abc123",
            message="feat(auth): add OAuth support",
            score=9,
            commit_type="feat",
            scope="auth",
        )
        exemplar = store.create_exemplar(exemplar_data)

        assert exemplar.id is not None
        assert exemplar.message == "feat(auth): add OAuth support"
        assert exemplar.score == 9

    def test_list_exemplars(self, store):
        """Test listing exemplars for a repository."""
        repo = store.create_repository(RepositoryCreate(name="test-repo"))
        store.create_exemplar(ExemplarCreate(
            repo_id=repo.id, commit_hash="abc", message="feat: a", score=9
        ))
        store.create_exemplar(ExemplarCreate(
            repo_id=repo.id, commit_hash="def", message="fix: b", score=8
        ))

        exemplars = store.list_exemplars(repo.id)
        assert len(exemplars) == 2
        # Should be ordered by score DESC
        assert exemplars[0].score == 9

    def test_create_antipattern(self, store):
        """Test creating an antipattern."""
        repo = store.create_repository(RepositoryCreate(name="test-repo"))
        ap_data = AntipatternCreate(
            repo_id=repo.id,
            pattern_type=AntipatternType.WIP_CHAIN,
            example_message="WIP",
            frequency=5,
        )
        ap = store.create_antipattern(ap_data)

        assert ap.id is not None
        assert ap.pattern_type == AntipatternType.WIP_CHAIN
        assert ap.frequency == 5

    def test_clear_all(self, store):
        """Test clearing all data."""
        repo = store.create_repository(RepositoryCreate(name="test-repo"))
        store.create_collaborator(CollaboratorCreate(repo_id=repo.id, name="Alice"))
        store.create_exemplar(ExemplarCreate(
            repo_id=repo.id, commit_hash="abc", message="test", score=8
        ))

        stats = store.get_stats()
        assert stats["repositories"] == 1
        assert stats["collaborators"] == 1
        assert stats["exemplars"] == 1

        store.clear_all()
        stats = store.get_stats()
        assert stats["repositories"] == 0

    def test_delete_repository_cascades(self, store):
        """Test that deleting a repository cascades to related data."""
        repo = store.create_repository(RepositoryCreate(name="test-repo"))
        store.create_collaborator(CollaboratorCreate(repo_id=repo.id, name="Alice"))
        store.create_exemplar(ExemplarCreate(
            repo_id=repo.id, commit_hash="abc", message="test", score=8
        ))

        store.delete_repository(repo.id)

        assert store.get_repository(repo.id) is None
        assert store.list_collaborators(repo.id) == []
        assert store.list_exemplars(repo.id) == []


# ============================================================================
# Extractor Tests
# ============================================================================


class TestStyleExtractor:
    """Test StyleExtractor."""

    @pytest.fixture
    def extractor(self):
        return StyleExtractor()

    @pytest.fixture
    def sample_commits(self):
        """Create sample commits for testing."""
        return [
            CommitInfo(
                hash="abc123",
                short_hash="abc123",
                message="feat(auth): add OAuth support",
                author="Alice",
                date=datetime.now(),
                files_changed=3,
            ),
            CommitInfo(
                hash="def456",
                short_hash="def456",
                message="fix(api): handle rate limiting",
                author="Bob",
                date=datetime.now(),
                files_changed=2,
            ),
            CommitInfo(
                hash="ghi789",
                short_hash="ghi789",
                message="docs: update README",
                author="Alice",
                date=datetime.now(),
                files_changed=1,
            ),
        ]

    def test_detect_conventional_style(self, extractor, sample_commits):
        """Test detecting conventional commit style."""
        style = extractor.extract_style(sample_commits)
        assert style.pattern == StylePattern.CONVENTIONAL

    def test_detect_scopes(self, extractor, sample_commits):
        """Test detecting scopes."""
        style = extractor.extract_style(sample_commits)
        assert style.uses_scopes is True
        assert "auth" in style.common_scopes
        assert "api" in style.common_scopes

    def test_freeform_style(self, extractor):
        """Test detecting freeform style."""
        commits = [
            CommitInfo(
                hash="a", short_hash="a", message="fixed the bug",
                author="A", date=datetime.now(), files_changed=1
            ),
            CommitInfo(
                hash="b", short_hash="b", message="updated tests",
                author="B", date=datetime.now(), files_changed=1
            ),
        ]
        style = extractor.extract_style(commits)
        assert style.pattern == StylePattern.FREEFORM


class TestAntipatternExtractor:
    """Test AntipatternExtractor."""

    @pytest.fixture
    def extractor(self):
        return AntipatternExtractor()

    def test_detect_wip_chain(self, extractor):
        """Test detecting WIP chains."""
        commits = [
            CommitInfo(
                hash=f"h{i}", short_hash=f"h{i}", message="WIP",
                author="Bob", date=datetime.now(), files_changed=1
            )
            for i in range(5)
        ]
        results = extractor.extract_antipatterns(commits)
        assert "Bob" in results
        assert any("wip-chain" in p[0] for p in results["Bob"])

    def test_detect_one_word(self, extractor):
        """Test detecting one-word commits."""
        commits = [
            CommitInfo(
                hash=f"h{i}", short_hash=f"h{i}", message="fix",
                author="Charlie", date=datetime.now(), files_changed=1
            )
            for i in range(5)
        ]
        results = extractor.extract_antipatterns(commits)
        assert "Charlie" in results

    def test_no_antipatterns_for_good_commits(self, extractor):
        """Test that good commits don't generate antipatterns."""
        commits = [
            CommitInfo(
                hash="a", short_hash="a", message="feat(auth): add login",
                author="Alice", date=datetime.now(), files_changed=1
            ),
            CommitInfo(
                hash="b", short_hash="b", message="fix(api): handle errors",
                author="Alice", date=datetime.now(), files_changed=1
            ),
        ]
        results = extractor.extract_antipatterns(commits)
        assert "Alice" not in results


class TestParseConventionalCommit:
    """Test conventional commit parsing."""

    def test_parse_with_scope(self):
        """Test parsing commit with scope."""
        commit_type, scope, desc = parse_conventional_commit("feat(auth): add OAuth")
        assert commit_type == "feat"
        assert scope == "auth"
        assert desc == "add OAuth"

    def test_parse_without_scope(self):
        """Test parsing commit without scope."""
        commit_type, scope, desc = parse_conventional_commit("fix: handle edge case")
        assert commit_type == "fix"
        assert scope is None
        assert desc == "handle edge case"

    def test_parse_non_conventional(self):
        """Test parsing non-conventional commit."""
        commit_type, scope, desc = parse_conventional_commit("fixed the bug")
        assert commit_type is None
        assert scope is None
        assert desc == "fixed the bug"


# ============================================================================
# Embedding Tests
# ============================================================================


class TestEmbeddingFormatters:
    """Test embedding formatting functions."""

    def test_format_commit_for_embedding(self):
        """Test formatting commit for embedding."""
        text = format_commit_for_embedding(
            message="add OAuth support",
            commit_type="feat",
            scope="auth",
            files_changed=["src/auth/oauth.py", "tests/test_oauth.py"],
        )
        assert "feat" in text
        assert "auth" in text
        assert "add OAuth support" in text
        assert "oauth.py" in text

    def test_format_diff_for_embedding(self):
        """Test formatting diff for embedding."""
        diff_text = """
+def new_function():
+    pass
-def old_function():
-    pass
"""
        text = format_diff_for_embedding(
            diff_text=diff_text,
            files_changed=["src/main.py"],
            additions=2,
            deletions=2,
        )
        assert "main.py" in text
        assert "+2" in text
        assert "-2" in text
