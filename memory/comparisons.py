"""Market comparison feature - compare against reference repositories."""

from dataclasses import dataclass

from openai import OpenAI

from ..config import get_settings
from .schemas import MarketPosition, ProjectType


# Reference repositories for comparison by project type
REFERENCE_REPOS = {
    ProjectType.WEB_FRAMEWORK: [
        ("fastapi", 8.4),
        ("django", 8.1),
        ("flask", 7.9),
        ("express", 7.5),
    ],
    ProjectType.CLI_TOOL: [
        ("typer", 8.2),
        ("click", 7.8),
        ("rich", 8.5),
        ("httpie", 7.6),
    ],
    ProjectType.LIBRARY: [
        ("requests", 8.0),
        ("numpy", 7.5),
        ("pandas", 7.3),
        ("pydantic", 8.3),
    ],
    ProjectType.API_SERVICE: [
        ("fastapi", 8.4),
        ("strapi", 7.2),
        ("hasura", 7.5),
    ],
    ProjectType.WEB_APP: [
        ("nextjs", 7.8),
        ("remix", 8.0),
        ("nuxt", 7.6),
    ],
    ProjectType.DATA_PIPELINE: [
        ("airflow", 7.4),
        ("prefect", 7.8),
        ("dagster", 7.9),
    ],
    ProjectType.MOBILE_APP: [
        ("expo", 7.5),
        ("react-native", 7.2),
    ],
}

# Default reference repos for unknown project types
DEFAULT_REFERENCE_REPOS = [
    ("linux", 8.0),
    ("git", 8.5),
    ("vscode", 7.8),
]


@dataclass
class ComparisonResult:
    """Result of comparing against reference repositories."""

    reference_scores: dict[str, float]  # {"fastapi": 8.4, "django": 8.1}
    percentile: float  # 0-100
    better_than: list[str]  # Repos you're better than
    worse_than: list[str]  # Repos you're worse than
    tip: str | None  # Improvement tip


class MarketComparator:
    """Compare repository commit quality against reference projects."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)

    def compare(
        self,
        project_type: ProjectType,
        average_score: float,
        primary_language: str | None = None,
    ) -> MarketPosition:
        """
        Compare against reference repositories for the project type.

        Args:
            project_type: Type of project.
            average_score: Your repository's average commit score.
            primary_language: Primary programming language.

        Returns:
            MarketPosition with comparison data.
        """
        # Get reference repos for this project type
        references = REFERENCE_REPOS.get(project_type, DEFAULT_REFERENCE_REPOS)

        # Build reference scores dict
        reference_scores = {name: score for name, score in references}

        # Calculate percentile
        all_scores = [score for _, score in references]
        all_scores.append(average_score)
        all_scores.sort()
        position = all_scores.index(average_score)
        percentile = (position / len(all_scores)) * 100

        # Determine which repos you're better/worse than
        better_than = [name for name, score in references if average_score > score]
        worse_than = [name for name, score in references if average_score < score]

        # Generate tip
        tip = self._generate_tip(
            project_type=project_type,
            average_score=average_score,
            better_than=better_than,
            worse_than=worse_than,
            primary_language=primary_language,
        )

        return MarketPosition(
            comparison_repos=[name for name, _ in references],
            industry_percentile=percentile,
            reference_scores=reference_scores,
        )

    def get_comparison_result(
        self,
        project_type: ProjectType,
        average_score: float,
        primary_language: str | None = None,
    ) -> ComparisonResult:
        """
        Get detailed comparison result with tips.

        Args:
            project_type: Type of project.
            average_score: Your repository's average commit score.
            primary_language: Primary programming language.

        Returns:
            ComparisonResult with detailed comparison.
        """
        references = REFERENCE_REPOS.get(project_type, DEFAULT_REFERENCE_REPOS)
        reference_scores = {name: score for name, score in references}

        # Calculate percentile
        all_scores = [score for _, score in references] + [average_score]
        all_scores.sort()
        position = all_scores.index(average_score)
        percentile = (position / len(all_scores)) * 100

        better_than = [name for name, score in references if average_score > score]
        worse_than = [name for name, score in references if average_score < score]

        tip = self._generate_tip(
            project_type=project_type,
            average_score=average_score,
            better_than=better_than,
            worse_than=worse_than,
            primary_language=primary_language,
        )

        return ComparisonResult(
            reference_scores=reference_scores,
            percentile=percentile,
            better_than=better_than,
            worse_than=worse_than,
            tip=tip,
        )

    def _generate_tip(
        self,
        project_type: ProjectType,
        average_score: float,
        better_than: list[str],
        worse_than: list[str],
        primary_language: str | None,
    ) -> str | None:
        """Generate an improvement tip based on comparison."""
        if not worse_than:
            return "Your commit quality is top-tier! Keep it up."

        # Find the best project you're worse than for inspiration
        best_reference = worse_than[0] if worse_than else None
        if not best_reference:
            return None

        # Generate a contextual tip
        tips = {
            "fastapi": "FastAPI uses scopes like feat(router): - try it!",
            "django": "Django commits are detailed and reference issues.",
            "flask": "Flask commits explain the 'why' clearly.",
            "typer": "Typer commits use conventional format consistently.",
            "rich": "Rich commits are concise but descriptive.",
            "pydantic": "Pydantic commits reference the affected API.",
            "requests": "requests commits are brief but complete.",
        }

        return tips.get(best_reference, f"Study {best_reference}'s commit style for inspiration.")
