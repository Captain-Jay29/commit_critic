"""Pydantic models for the memory system."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class StylePattern(str, Enum):
    """Detected commit style patterns."""

    CONVENTIONAL = "conventional"  # feat(scope): message
    EMOJI = "emoji"  # :emoji: message or emoji message
    TICKET = "ticket"  # JIRA-123: message
    FREEFORM = "freeform"  # No specific pattern


class ProjectType(str, Enum):
    """Detected project types."""

    CLI_TOOL = "cli-tool"
    WEB_APP = "web-app"
    WEB_FRAMEWORK = "web-framework"
    LIBRARY = "library"
    API_SERVICE = "api-service"
    MOBILE_APP = "mobile-app"
    DATA_PIPELINE = "data-pipeline"
    UNKNOWN = "unknown"


class AntipatternType(str, Enum):
    """Types of commit message antipatterns."""

    WIP_CHAIN = "wip-chain"  # Multiple WIP commits in sequence
    ONE_WORD = "one-word"  # Single word messages
    VAGUE = "vague"  # "fixed bug", "update", etc.
    NO_CONTEXT = "no-context"  # Missing what/why
    TOO_LONG = "too-long"  # Overly verbose subject
    CAPS_ABUSE = "caps-abuse"  # ALL CAPS or excessive caps


# ============================================================================
# Core Data Models
# ============================================================================


class LanguageBreakdown(BaseModel):
    """Language distribution in a repository."""

    language: str
    percentage: float = Field(ge=0, le=100)


class CommitStyle(BaseModel):
    """Detected commit style patterns for a repository."""

    pattern: StylePattern = StylePattern.FREEFORM
    uses_scopes: bool = False
    common_scopes: list[str] = Field(default_factory=list)
    uses_emoji: bool = False
    ticket_pattern: str | None = None  # Regex pattern like "JIRA-\\d+"


class CodebaseDNA(BaseModel):
    """Detected characteristics of a codebase."""

    primary_language: str | None = None
    languages: list[LanguageBreakdown] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    project_type: ProjectType = ProjectType.UNKNOWN


class MarketPosition(BaseModel):
    """Comparison data against reference repositories."""

    comparison_repos: list[str] = Field(default_factory=list)  # ["fastapi", "django"]
    industry_percentile: float | None = None  # 0-100
    reference_scores: dict[str, float] = Field(default_factory=dict)  # {"fastapi": 8.4}


# ============================================================================
# Database Entity Models
# ============================================================================


class RepositoryCreate(BaseModel):
    """Data for creating a new repository record."""

    url: str | None = None
    name: str
    primary_language: str | None = None
    languages: list[LanguageBreakdown] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    project_type: ProjectType = ProjectType.UNKNOWN
    style_pattern: StylePattern = StylePattern.FREEFORM
    uses_scopes: bool = False
    common_scopes: list[str] = Field(default_factory=list)
    ticket_pattern: str | None = None


class Repository(RepositoryCreate):
    """Repository record from database."""

    id: int
    seeded_at: datetime
    comparison_repos: list[str] = Field(default_factory=list)
    industry_percentile: float | None = None


class CollaboratorCreate(BaseModel):
    """Data for creating a new collaborator record."""

    repo_id: int
    name: str
    email: str | None = None
    commit_count: int = 0
    avg_score: float | None = None
    primary_areas: list[str] = Field(default_factory=list)
    area_summary: str | None = None
    roast_patterns: list[str] = Field(default_factory=list)


class Collaborator(CollaboratorCreate):
    """Collaborator record from database."""

    id: int


class ExemplarCreate(BaseModel):
    """Data for creating a new exemplar record."""

    repo_id: int
    collaborator_id: int | None = None
    commit_hash: str
    message: str
    score: int = Field(ge=8, le=10)  # Only high-scoring commits
    commit_type: str | None = None  # "feat", "fix", etc.
    scope: str | None = None
    embedding: bytes | None = None  # 1536-dim vector as bytes


class Exemplar(ExemplarCreate):
    """Exemplar record from database."""

    id: int


class AntipatternCreate(BaseModel):
    """Data for creating a new antipattern record."""

    repo_id: int
    collaborator_id: int | None = None
    pattern_type: AntipatternType
    example_message: str
    frequency: int = 1


class Antipattern(AntipatternCreate):
    """Antipattern record from database."""

    id: int


# ============================================================================
# Aggregated View Models (for display/output)
# ============================================================================


class CollaboratorInsight(BaseModel):
    """Aggregated view of a collaborator for display."""

    name: str
    email: str | None = None
    commit_count: int
    avg_score: float | None
    primary_areas: list[str]
    area_summary: str | None
    roast_patterns: list[str]
    trend: str | None = None  # "improving", "declining", "stable"


class MemoryStatus(BaseModel):
    """Summary of what's stored in memory for a repository."""

    repository: Repository | None = None
    dna: CodebaseDNA | None = None
    style: CommitStyle | None = None
    market: MarketPosition | None = None
    collaborator_count: int = 0
    exemplar_count: int = 0
    antipattern_count: int = 0
    top_collaborators: list[CollaboratorInsight] = Field(default_factory=list)


class SeedingProgress(BaseModel):
    """Progress update during seeding operation."""

    phase: int  # 1-8
    phase_name: str
    status: str  # "started", "progress", "done"
    message: str
    detail: str | None = None
    progress: float | None = None  # 0-100 for progress bars
