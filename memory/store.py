"""SQLite storage for the memory system."""

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import numpy as np

from ..config import get_settings
from .schemas import (
    Antipattern,
    AntipatternCreate,
    AntipatternType,
    Collaborator,
    CollaboratorCreate,
    Exemplar,
    ExemplarCreate,
    LanguageBreakdown,
    ProjectType,
    Repository,
    RepositoryCreate,
    StylePattern,
)

# SQL schema for creating tables
SCHEMA_SQL = """
-- Repository metadata and learned patterns
CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE,
    name TEXT NOT NULL,
    seeded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Codebase DNA
    primary_language TEXT,
    languages_json TEXT,
    frameworks_json TEXT,
    project_type TEXT DEFAULT 'unknown',

    -- Commit style
    style_pattern TEXT DEFAULT 'freeform',
    uses_scopes INTEGER DEFAULT 0,
    common_scopes_json TEXT,
    ticket_pattern TEXT,

    -- Market position
    comparison_repos_json TEXT,
    industry_percentile REAL
);

-- Contributor profiles
CREATE TABLE IF NOT EXISTS collaborators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT,

    commit_count INTEGER DEFAULT 0,
    avg_score REAL,
    primary_areas_json TEXT,
    area_summary TEXT,

    roast_patterns_json TEXT,

    UNIQUE(repo_id, name)
);

-- High-quality commit exemplars
CREATE TABLE IF NOT EXISTS exemplars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    collaborator_id INTEGER REFERENCES collaborators(id) ON DELETE SET NULL,

    commit_hash TEXT NOT NULL,
    message TEXT NOT NULL,
    score INTEGER CHECK(score >= 8 AND score <= 10),
    commit_type TEXT,
    scope TEXT,

    embedding BLOB,

    UNIQUE(repo_id, commit_hash)
);

-- Bad patterns for roasts
CREATE TABLE IF NOT EXISTS antipatterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    collaborator_id INTEGER REFERENCES collaborators(id) ON DELETE SET NULL,

    pattern_type TEXT NOT NULL,
    example_message TEXT,
    frequency INTEGER DEFAULT 1
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_collaborators_repo ON collaborators(repo_id);
CREATE INDEX IF NOT EXISTS idx_exemplars_repo ON exemplars(repo_id);
CREATE INDEX IF NOT EXISTS idx_antipatterns_repo ON antipatterns(repo_id);
CREATE INDEX IF NOT EXISTS idx_exemplars_score ON exemplars(score DESC);
"""


class MemoryStore:
    """SQLite-based storage for the memory system."""

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize the memory store.

        Args:
            db_path: Path to SQLite database. If None, uses settings.db_path.
        """
        if db_path is None:
            settings = get_settings()
            settings.ensure_dirs()
            db_path = settings.db_path
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA_SQL)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ========================================================================
    # Repository Operations
    # ========================================================================

    def create_repository(self, data: RepositoryCreate) -> Repository:
        """Create a new repository record."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO repositories (
                    url, name, primary_language, languages_json, frameworks_json,
                    project_type, style_pattern, uses_scopes, common_scopes_json,
                    ticket_pattern
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.url,
                    data.name,
                    data.primary_language,
                    json.dumps([lang.model_dump() for lang in data.languages]),
                    json.dumps(data.frameworks),
                    data.project_type.value,
                    data.style_pattern.value,
                    1 if data.uses_scopes else 0,
                    json.dumps(data.common_scopes),
                    data.ticket_pattern,
                ),
            )
            repo_id = cursor.lastrowid
            if repo_id is None:
                raise RuntimeError("Failed to get repository ID")

            # Fetch the created row within the same connection
            row = conn.execute(
                "SELECT * FROM repositories WHERE id = ?", (repo_id,)
            ).fetchone()
            if row is None:
                raise RuntimeError("Failed to fetch created repository")
            return self._row_to_repository(row)

    def get_repository(self, repo_id: int) -> Repository | None:
        """Get a repository by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM repositories WHERE id = ?", (repo_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_repository(row)

    def get_repository_by_url(self, url: str) -> Repository | None:
        """Get a repository by URL."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM repositories WHERE url = ?", (url,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_repository(row)

    def get_repository_by_name(self, name: str) -> Repository | None:
        """Get a repository by name."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM repositories WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_repository(row)

    def update_repository_market(
        self,
        repo_id: int,
        comparison_repos: list[str],
        industry_percentile: float | None,
    ) -> None:
        """Update market comparison data for a repository."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE repositories
                SET comparison_repos_json = ?, industry_percentile = ?
                WHERE id = ?
                """,
                (json.dumps(comparison_repos), industry_percentile, repo_id),
            )

    def delete_repository(self, repo_id: int) -> None:
        """Delete a repository and all related data."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))

    def list_repositories(self) -> list[Repository]:
        """List all repositories."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM repositories ORDER BY seeded_at DESC"
            ).fetchall()
            return [self._row_to_repository(row) for row in rows]

    def _row_to_repository(self, row: sqlite3.Row) -> Repository:
        """Convert a database row to a Repository model."""
        languages_json = row["languages_json"]
        languages = []
        if languages_json:
            languages = [LanguageBreakdown(**lang) for lang in json.loads(languages_json)]

        frameworks_json = row["frameworks_json"]
        frameworks = json.loads(frameworks_json) if frameworks_json else []

        common_scopes_json = row["common_scopes_json"]
        common_scopes = json.loads(common_scopes_json) if common_scopes_json else []

        comparison_repos_json = row["comparison_repos_json"]
        comparison_repos = (
            json.loads(comparison_repos_json) if comparison_repos_json else []
        )

        return Repository(
            id=row["id"],
            url=row["url"],
            name=row["name"],
            seeded_at=datetime.fromisoformat(row["seeded_at"]),
            primary_language=row["primary_language"],
            languages=languages,
            frameworks=frameworks,
            project_type=ProjectType(row["project_type"]),
            style_pattern=StylePattern(row["style_pattern"]),
            uses_scopes=bool(row["uses_scopes"]),
            common_scopes=common_scopes,
            ticket_pattern=row["ticket_pattern"],
            comparison_repos=comparison_repos,
            industry_percentile=row["industry_percentile"],
        )

    # ========================================================================
    # Collaborator Operations
    # ========================================================================

    def create_collaborator(self, data: CollaboratorCreate) -> Collaborator:
        """Create a new collaborator record."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO collaborators (
                    repo_id, name, email, commit_count, avg_score,
                    primary_areas_json, area_summary, roast_patterns_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.repo_id,
                    data.name,
                    data.email,
                    data.commit_count,
                    data.avg_score,
                    json.dumps(data.primary_areas),
                    data.area_summary,
                    json.dumps(data.roast_patterns),
                ),
            )
            collab_id = cursor.lastrowid
            if collab_id is None:
                raise RuntimeError("Failed to get collaborator ID")

            # Fetch the created row within the same connection
            row = conn.execute(
                "SELECT * FROM collaborators WHERE id = ?", (collab_id,)
            ).fetchone()
            if row is None:
                raise RuntimeError("Failed to fetch created collaborator")
            return self._row_to_collaborator(row)

    def get_collaborator(self, collab_id: int) -> Collaborator | None:
        """Get a collaborator by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM collaborators WHERE id = ?", (collab_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_collaborator(row)

    def get_collaborator_by_name(self, repo_id: int, name: str) -> Collaborator | None:
        """Get a collaborator by repo and name."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM collaborators WHERE repo_id = ? AND name = ?",
                (repo_id, name),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_collaborator(row)

    def update_collaborator(
        self,
        collab_id: int,
        commit_count: int | None = None,
        avg_score: float | None = None,
        primary_areas: list[str] | None = None,
        area_summary: str | None = None,
        roast_patterns: list[str] | None = None,
    ) -> None:
        """Update collaborator fields."""
        updates: list[str] = []
        params: list[str | int | float] = []

        if commit_count is not None:
            updates.append("commit_count = ?")
            params.append(commit_count)
        if avg_score is not None:
            updates.append("avg_score = ?")
            params.append(avg_score)
        if primary_areas is not None:
            updates.append("primary_areas_json = ?")
            params.append(json.dumps(primary_areas))
        if area_summary is not None:
            updates.append("area_summary = ?")
            params.append(area_summary)
        if roast_patterns is not None:
            updates.append("roast_patterns_json = ?")
            params.append(json.dumps(roast_patterns))

        if not updates:
            return

        params.append(collab_id)
        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE collaborators SET {', '.join(updates)} WHERE id = ?",
                params,
            )

    def list_collaborators(self, repo_id: int) -> list[Collaborator]:
        """List all collaborators for a repository."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM collaborators
                WHERE repo_id = ?
                ORDER BY commit_count DESC
                """,
                (repo_id,),
            ).fetchall()
            return [self._row_to_collaborator(row) for row in rows]

    def _row_to_collaborator(self, row: sqlite3.Row) -> Collaborator:
        """Convert a database row to a Collaborator model."""
        primary_areas_json = row["primary_areas_json"]
        primary_areas = json.loads(primary_areas_json) if primary_areas_json else []

        roast_patterns_json = row["roast_patterns_json"]
        roast_patterns = json.loads(roast_patterns_json) if roast_patterns_json else []

        return Collaborator(
            id=row["id"],
            repo_id=row["repo_id"],
            name=row["name"],
            email=row["email"],
            commit_count=row["commit_count"],
            avg_score=row["avg_score"],
            primary_areas=primary_areas,
            area_summary=row["area_summary"],
            roast_patterns=roast_patterns,
        )

    # ========================================================================
    # Exemplar Operations
    # ========================================================================

    def create_exemplar(self, data: ExemplarCreate) -> Exemplar:
        """Create a new exemplar record."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO exemplars (
                    repo_id, collaborator_id, commit_hash, message, score,
                    commit_type, scope, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.repo_id,
                    data.collaborator_id,
                    data.commit_hash,
                    data.message,
                    data.score,
                    data.commit_type,
                    data.scope,
                    data.embedding,
                ),
            )
            exemplar_id = cursor.lastrowid
            if exemplar_id is None:
                raise RuntimeError("Failed to get exemplar ID")

            # Fetch the created row within the same connection
            row = conn.execute(
                "SELECT * FROM exemplars WHERE id = ?", (exemplar_id,)
            ).fetchone()
            if row is None:
                raise RuntimeError("Failed to fetch created exemplar")
            return self._row_to_exemplar(row)

    def get_exemplar(self, exemplar_id: int) -> Exemplar | None:
        """Get an exemplar by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM exemplars WHERE id = ?", (exemplar_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_exemplar(row)

    def list_exemplars(
        self,
        repo_id: int,
        limit: int | None = None,
        commit_type: str | None = None,
    ) -> list[Exemplar]:
        """List exemplars for a repository."""
        query = "SELECT * FROM exemplars WHERE repo_id = ?"
        params: list[int | str] = [repo_id]

        if commit_type:
            query += " AND commit_type = ?"
            params.append(commit_type)

        query += " ORDER BY score DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_exemplar(row) for row in rows]

    def find_similar_exemplars(
        self,
        repo_id: int,
        query_embedding: bytes,
        limit: int = 3,
    ) -> list[tuple[Exemplar, float]]:
        """
        Find exemplars similar to the query embedding using cosine similarity.

        Args:
            repo_id: Repository ID to search in.
            query_embedding: Query embedding as bytes (1536-dim float32).
            limit: Maximum number of results.

        Returns:
            List of (Exemplar, similarity_score) tuples, sorted by similarity.
        """
        exemplars = self.list_exemplars(repo_id)
        if not exemplars:
            return []

        # Convert query to numpy array
        query_vec = np.frombuffer(query_embedding, dtype=np.float32)

        # Calculate similarities
        results: list[tuple[Exemplar, float]] = []
        for exemplar in exemplars:
            if exemplar.embedding is None:
                continue
            exemplar_vec = np.frombuffer(exemplar.embedding, dtype=np.float32)
            similarity = self._cosine_similarity(query_vec, exemplar_vec)
            results.append((exemplar, similarity))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot_product / (norm_a * norm_b))

    def count_exemplars(self, repo_id: int) -> int:
        """Count exemplars for a repository."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM exemplars WHERE repo_id = ?", (repo_id,)
            ).fetchone()
            return row["count"] if row else 0

    def _row_to_exemplar(self, row: sqlite3.Row) -> Exemplar:
        """Convert a database row to an Exemplar model."""
        return Exemplar(
            id=row["id"],
            repo_id=row["repo_id"],
            collaborator_id=row["collaborator_id"],
            commit_hash=row["commit_hash"],
            message=row["message"],
            score=row["score"],
            commit_type=row["commit_type"],
            scope=row["scope"],
            embedding=row["embedding"],
        )

    # ========================================================================
    # Antipattern Operations
    # ========================================================================

    def create_antipattern(self, data: AntipatternCreate) -> Antipattern:
        """Create a new antipattern record."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO antipatterns (
                    repo_id, collaborator_id, pattern_type, example_message, frequency
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    data.repo_id,
                    data.collaborator_id,
                    data.pattern_type.value,
                    data.example_message,
                    data.frequency,
                ),
            )
            ap_id = cursor.lastrowid
            if ap_id is None:
                raise RuntimeError("Failed to get antipattern ID")

            # Fetch the created row within the same connection
            row = conn.execute(
                "SELECT * FROM antipatterns WHERE id = ?", (ap_id,)
            ).fetchone()
            if row is None:
                raise RuntimeError("Failed to fetch created antipattern")
            return self._row_to_antipattern(row)

    def get_antipattern(self, ap_id: int) -> Antipattern | None:
        """Get an antipattern by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM antipatterns WHERE id = ?", (ap_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_antipattern(row)

    def list_antipatterns(
        self,
        repo_id: int,
        collaborator_id: int | None = None,
    ) -> list[Antipattern]:
        """List antipatterns for a repository."""
        query = "SELECT * FROM antipatterns WHERE repo_id = ?"
        params: list[int] = [repo_id]

        if collaborator_id is not None:
            query += " AND collaborator_id = ?"
            params.append(collaborator_id)

        query += " ORDER BY frequency DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_antipattern(row) for row in rows]

    def count_antipatterns(self, repo_id: int) -> int:
        """Count antipatterns for a repository."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM antipatterns WHERE repo_id = ?",
                (repo_id,),
            ).fetchone()
            return row["count"] if row else 0

    def _row_to_antipattern(self, row: sqlite3.Row) -> Antipattern:
        """Convert a database row to an Antipattern model."""
        return Antipattern(
            id=row["id"],
            repo_id=row["repo_id"],
            collaborator_id=row["collaborator_id"],
            pattern_type=AntipatternType(row["pattern_type"]),
            example_message=row["example_message"],
            frequency=row["frequency"],
        )

    # ========================================================================
    # Utility Operations
    # ========================================================================

    def clear_all(self) -> None:
        """Clear all data from the database."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM antipatterns")
            conn.execute("DELETE FROM exemplars")
            conn.execute("DELETE FROM collaborators")
            conn.execute("DELETE FROM repositories")

    def get_stats(self) -> dict[str, int]:
        """Get overall statistics."""
        with self._get_connection() as conn:
            repos = conn.execute("SELECT COUNT(*) FROM repositories").fetchone()[0]
            collabs = conn.execute("SELECT COUNT(*) FROM collaborators").fetchone()[0]
            exemplars = conn.execute("SELECT COUNT(*) FROM exemplars").fetchone()[0]
            antipatterns = conn.execute(
                "SELECT COUNT(*) FROM antipatterns"
            ).fetchone()[0]
            return {
                "repositories": repos,
                "collaborators": collabs,
                "exemplars": exemplars,
                "antipatterns": antipatterns,
            }
