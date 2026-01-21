"""Main orchestration for the init command - seeds memory from a repository."""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..agents.analyzer import CommitAnalyzer, AnalysisResult
from ..config import get_settings
from ..vcs.operations import CommitInfo
from .embeddings import EmbeddingGenerator, format_commit_for_embedding
from .extractor import (
    AntipatternExtractor,
    DNAExtractor,
    StyleExtractor,
    parse_conventional_commit,
)
from .schemas import (
    AntipatternCreate,
    AntipatternType,
    CollaboratorCreate,
    ExemplarCreate,
    RepositoryCreate,
    SeedingProgress,
)
from .store import MemoryStore


@dataclass
class SeedingResult:
    """Result of seeding memory from a repository."""

    repo_id: int
    repo_name: str
    commit_count: int
    average_score: float
    exemplar_count: int
    collaborator_count: int
    antipattern_count: int
    has_roasts: bool


# Type alias for progress callback
ProgressCallback = Callable[[SeedingProgress], None]


class MemorySeeder:
    """
    Orchestrates the seeding process for the init command.

    The seeding process has 8 phases:
    1. Clone repository (if remote URL)
    2. Extract commits
    3. Analyze codebase DNA
    4. Detect commit style
    5. Analyze commits (score each one)
    6. Extract exemplars (high-scoring commits)
    7. Profile contributors
    8. Market comparison (optional)
    """

    def __init__(
        self,
        store: MemoryStore | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        """
        Initialize the seeder.

        Args:
            store: MemoryStore instance. If None, creates a new one.
            on_progress: Callback for progress updates.
        """
        self.store = store or MemoryStore()
        self.settings = get_settings()
        self.on_progress = on_progress

        # Extractors
        self.style_extractor = StyleExtractor()
        self.dna_extractor = DNAExtractor()
        self.antipattern_extractor = AntipatternExtractor()

        # Analyzer for scoring
        self.analyzer = CommitAnalyzer()

        # Embedding generator
        self.embedding_generator = EmbeddingGenerator()

    def _emit_progress(
        self,
        phase: int,
        phase_name: str,
        status: str,
        message: str,
        detail: str | None = None,
        progress: float | None = None,
    ) -> None:
        """Emit a progress update."""
        if self.on_progress:
            self.on_progress(
                SeedingProgress(
                    phase=phase,
                    phase_name=phase_name,
                    status=status,
                    message=message,
                    detail=detail,
                    progress=progress,
                )
            )

    def seed(
        self,
        commits: list[CommitInfo],
        repo_name: str,
        repo_url: str | None = None,
        repo_path: Path | None = None,
        include_roasts: bool = True,
        include_market_comparison: bool = True,
    ) -> SeedingResult:
        """
        Seed memory from repository commits.

        Args:
            commits: List of commits to analyze.
            repo_name: Name of the repository.
            repo_url: URL of the repository (if remote).
            repo_path: Local path to repository (for deeper analysis).
            include_roasts: Whether to extract antipatterns for roasts.
            include_market_comparison: Whether to do market comparison.

        Returns:
            SeedingResult with summary of what was learned.
        """
        # Check if repo already exists
        existing = self.store.get_repository_by_name(repo_name)
        if existing:
            # Delete existing data and reseed
            self.store.delete_repository(existing.id)

        # Phase 3: Analyze codebase DNA
        self._emit_progress(3, "Analyzing codebase DNA", "started", "Analyzing codebase DNA...")
        dna = self.dna_extractor.extract_dna(commits, repo_path)
        self._emit_progress(
            3,
            "Analyzing codebase DNA",
            "done",
            "Done",
            detail=f"Primary: {dna.primary_language or 'Unknown'} | Type: {dna.project_type.value}",
        )

        # Phase 4: Detect commit style
        self._emit_progress(4, "Detecting commit style", "started", "Detecting commit style...")
        style = self.style_extractor.extract_style(commits)
        style_detail = f"Pattern: {style.pattern.value}"
        if style.uses_scopes:
            style_detail += f" | Scopes: {', '.join(style.common_scopes[:5])}"
        self._emit_progress(4, "Detecting commit style", "done", "Done", detail=style_detail)

        # Create repository record
        repo_data = RepositoryCreate(
            url=repo_url,
            name=repo_name,
            primary_language=dna.primary_language,
            languages=dna.languages,
            frameworks=dna.frameworks,
            project_type=dna.project_type,
            style_pattern=style.pattern,
            uses_scopes=style.uses_scopes,
            common_scopes=style.common_scopes,
            ticket_pattern=style.ticket_pattern,
        )
        repo = self.store.create_repository(repo_data)

        # Phase 5: Analyze commits (score each one)
        self._emit_progress(5, "Analyzing commits", "started", "Analyzing commits...")
        analysis_results = self._analyze_commits(commits, repo.id)
        avg_score = sum(r.score for r in analysis_results) / len(analysis_results) if analysis_results else 0
        self._emit_progress(
            5,
            "Analyzing commits",
            "done",
            "Done",
            detail=f"Average: {avg_score:.1f}/10",
        )

        # Phase 6: Extract exemplars
        self._emit_progress(6, "Extracting exemplars", "started", "Extracting exemplars...")
        exemplar_count = self._extract_exemplars(analysis_results, repo.id)
        self._emit_progress(
            6,
            "Extracting exemplars",
            "done",
            "Done",
            detail=f"Found {exemplar_count} exemplary commits (score >= 8)",
        )

        # Phase 7: Profile contributors
        self._emit_progress(7, "Profiling contributors", "started", "Profiling contributors...")
        collaborator_count, has_roasts = self._profile_contributors(
            commits, analysis_results, repo.id, include_roasts
        )
        self._emit_progress(
            7,
            "Profiling contributors",
            "done",
            "Done",
            detail=f"Profiled {collaborator_count} contributors",
        )

        # Phase 8: Market comparison (optional, placeholder for now)
        antipattern_count = self.store.count_antipatterns(repo.id)
        if include_market_comparison:
            self._emit_progress(8, "Market comparison", "started", "Comparing to similar projects...")
            # TODO: Implement market comparison in comparisons.py
            self._emit_progress(8, "Market comparison", "done", "Done", detail="Coming soon")

        return SeedingResult(
            repo_id=repo.id,
            repo_name=repo_name,
            commit_count=len(commits),
            average_score=avg_score,
            exemplar_count=exemplar_count,
            collaborator_count=collaborator_count,
            antipattern_count=antipattern_count,
            has_roasts=has_roasts,
        )

    def _analyze_commits(
        self,
        commits: list[CommitInfo],
        repo_id: int,
    ) -> list[AnalysisResult]:
        """Analyze and score all commits."""
        results: list[AnalysisResult] = []
        total = len(commits)

        for i, commit in enumerate(commits):
            # Emit progress
            progress = ((i + 1) / total) * 100
            self._emit_progress(
                5,
                "Analyzing commits",
                "progress",
                f"[{i + 1}/{total}] {commit.message[:50]}...",
                progress=progress,
            )

            # Analyze commit
            try:
                result = self.analyzer.analyze_commit(commit)
                results.append(result)
            except Exception:
                # Skip commits that fail to analyze
                continue

        return results

    def _extract_exemplars(
        self,
        results: list[AnalysisResult],
        repo_id: int,
    ) -> int:
        """Extract high-scoring commits as exemplars."""
        threshold = self.settings.exemplar_threshold
        exemplars = [r for r in results if r.score >= threshold]

        if not exemplars:
            return 0

        # Generate embeddings for all exemplars in batch
        messages_to_embed = []
        for result in exemplars:
            commit_type, scope, _ = parse_conventional_commit(result.commit.message)
            text = format_commit_for_embedding(
                message=result.commit.message,
                commit_type=commit_type,
                scope=scope,
                files_changed=result.commit.files_changed,
            )
            messages_to_embed.append(text)

        embeddings = self.embedding_generator.generate_batch(messages_to_embed)

        # Save exemplars
        for result, embedding in zip(exemplars, embeddings):
            commit_type, scope, _ = parse_conventional_commit(result.commit.message)
            exemplar_data = ExemplarCreate(
                repo_id=repo_id,
                commit_hash=result.commit.hash,
                message=result.commit.message,
                score=result.score,
                commit_type=commit_type,
                scope=scope,
                embedding=embedding,
            )
            self.store.create_exemplar(exemplar_data)

        return len(exemplars)

    def _profile_contributors(
        self,
        commits: list[CommitInfo],
        results: list[AnalysisResult],
        repo_id: int,
        include_roasts: bool,
    ) -> tuple[int, bool]:
        """Profile contributors and extract antipatterns."""
        # Group commits and results by author
        commits_by_author: dict[str, list[CommitInfo]] = {}
        scores_by_author: dict[str, list[int]] = {}

        for commit in commits:
            author = commit.author
            if author not in commits_by_author:
                commits_by_author[author] = []
            commits_by_author[author].append(commit)

        # Map commit hashes to scores
        score_map = {r.commit.hash: r.score for r in results}
        for commit in commits:
            author = commit.author
            if author not in scores_by_author:
                scores_by_author[author] = []
            if commit.hash in score_map:
                scores_by_author[author].append(score_map[commit.hash])

        # Extract antipatterns if enabled
        antipatterns_by_author: dict[str, list[tuple[str, str, int]]] = {}
        if include_roasts:
            antipatterns_by_author = self.antipattern_extractor.extract_antipatterns(commits)

        # Create collaborator records
        has_roasts = False
        for author, author_commits in commits_by_author.items():
            scores = scores_by_author.get(author, [])
            avg_score = sum(scores) / len(scores) if scores else None

            # Detect primary areas from file paths
            primary_areas = self._detect_primary_areas(author_commits)

            # Get roast patterns
            roast_patterns = []
            if author in antipatterns_by_author:
                for pattern_type, example, count in antipatterns_by_author[author]:
                    roast_patterns.append(f"{count}x {pattern_type}: '{example}'")
                has_roasts = True

            # Create collaborator
            collab_data = CollaboratorCreate(
                repo_id=repo_id,
                name=author,
                commit_count=len(author_commits),
                avg_score=avg_score,
                primary_areas=primary_areas,
                roast_patterns=roast_patterns,
            )
            collaborator = self.store.create_collaborator(collab_data)

            # Create antipattern records
            if author in antipatterns_by_author:
                for pattern_type, example, count in antipatterns_by_author[author]:
                    ap_data = AntipatternCreate(
                        repo_id=repo_id,
                        collaborator_id=collaborator.id,
                        pattern_type=AntipatternType(pattern_type),
                        example_message=example,
                        frequency=count,
                    )
                    self.store.create_antipattern(ap_data)

        return len(commits_by_author), has_roasts

    def _detect_primary_areas(self, commits: list[CommitInfo]) -> list[str]:
        """Detect primary areas of work from commit file paths."""
        # Count directory occurrences
        dir_counts: Counter = Counter()

        for commit in commits:
            for file_path in commit.files_changed:
                # Get first two directory levels
                parts = Path(file_path).parts
                if len(parts) >= 2:
                    area = f"{parts[0]}/{parts[1]}"
                elif len(parts) == 1:
                    area = parts[0]
                else:
                    continue
                dir_counts[area] += 1

        # Return top 3 areas
        return [area for area, _ in dir_counts.most_common(3)]
