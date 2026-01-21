"""Memory system for storing exemplars and conventions."""

from .comparisons import ComparisonResult, MarketComparator
from .embeddings import EmbeddingGenerator, cosine_similarity, format_commit_for_embedding
from .extractor import AntipatternExtractor, DNAExtractor, StyleExtractor
from .profiler import CollaboratorProfiler
from .schemas import (
    Antipattern,
    AntipatternCreate,
    AntipatternType,
    CodebaseDNA,
    Collaborator,
    CollaboratorCreate,
    CollaboratorInsight,
    CommitStyle,
    Exemplar,
    ExemplarCreate,
    LanguageBreakdown,
    MarketPosition,
    MemoryStatus,
    ProjectType,
    Repository,
    RepositoryCreate,
    SeedingProgress,
    StylePattern,
)
from .seeder import MemorySeeder, SeedingResult
from .store import MemoryStore

__all__ = [
    # Store
    "MemoryStore",
    # Seeder
    "MemorySeeder",
    "SeedingResult",
    # Embeddings
    "EmbeddingGenerator",
    "cosine_similarity",
    "format_commit_for_embedding",
    # Extractors
    "StyleExtractor",
    "DNAExtractor",
    "AntipatternExtractor",
    # Profiler
    "CollaboratorProfiler",
    # Comparisons
    "MarketComparator",
    "ComparisonResult",
    # Schemas - Enums
    "StylePattern",
    "ProjectType",
    "AntipatternType",
    # Schemas - Data models
    "LanguageBreakdown",
    "CommitStyle",
    "CodebaseDNA",
    "MarketPosition",
    # Schemas - Entity models
    "Repository",
    "RepositoryCreate",
    "Collaborator",
    "CollaboratorCreate",
    "CollaboratorInsight",
    "Exemplar",
    "ExemplarCreate",
    "Antipattern",
    "AntipatternCreate",
    # Schemas - View models
    "MemoryStatus",
    "SeedingProgress",
]
