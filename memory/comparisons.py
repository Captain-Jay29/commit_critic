"""Market comparison feature - find similar projects via GitHub search."""

from dataclasses import dataclass

import httpx

from .schemas import MarketPosition, ProjectType

# Map project types to GitHub search terms
PROJECT_TYPE_KEYWORDS = {
    ProjectType.WEB_FRAMEWORK: "web framework",
    ProjectType.CLI_TOOL: "cli tool command-line",
    ProjectType.LIBRARY: "library",
    ProjectType.API_SERVICE: "api rest",
    ProjectType.WEB_APP: "web app",
    ProjectType.DATA_PIPELINE: "data pipeline etl",
    ProjectType.MOBILE_APP: "mobile app",
    ProjectType.UNKNOWN: "",
}

# Baseline scores for percentile calculation (based on general industry)
# Most repos score 5-7, good ones 7-8, excellent 8+
SCORE_PERCENTILES = {
    10: 99,
    9: 95,
    8: 85,
    7: 70,
    6: 50,
    5: 35,
    4: 20,
    3: 10,
    2: 5,
    1: 1,
}


@dataclass
class SimilarRepo:
    """A similar repository found via GitHub search."""

    name: str
    full_name: str  # owner/repo
    description: str | None
    stars: int
    url: str


@dataclass
class ComparisonResult:
    """Result of market comparison."""

    similar_repos: list[SimilarRepo]
    percentile: float  # 0-100 based on score
    search_query: str  # What we searched for
    tip: str | None


class MarketComparator:
    """Compare repository against similar projects via GitHub search."""

    GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"

    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=10.0,
            headers={"Accept": "application/vnd.github.v3+json"},
        )

    def search_similar(
        self,
        project_type: ProjectType,
        primary_language: str | None = None,
        limit: int = 5,
    ) -> tuple[list[SimilarRepo], str]:
        """
        Search GitHub for similar popular repositories.

        Args:
            project_type: Type of project.
            primary_language: Primary programming language.
            limit: Max results to return.

        Returns:
            Tuple of (list of similar repos, search query used).
        """
        # Build search query
        keywords = PROJECT_TYPE_KEYWORDS.get(project_type, "")
        query_parts = []

        if keywords:
            query_parts.append(keywords)

        if primary_language:
            query_parts.append(f"language:{primary_language}")

        # Sort by stars to get popular repos
        query = " ".join(query_parts) if query_parts else "stars:>1000"

        try:
            response = self.client.get(
                self.GITHUB_SEARCH_URL,
                params={
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": limit,
                },
            )
            response.raise_for_status()
            data = response.json()

            repos = []
            for item in data.get("items", [])[:limit]:
                repos.append(
                    SimilarRepo(
                        name=item["name"],
                        full_name=item["full_name"],
                        description=item.get("description"),
                        stars=item["stargazers_count"],
                        url=item["html_url"],
                    )
                )

            return repos, query

        except Exception:
            # On any error, return empty results
            return [], query

    def get_comparison_result(
        self,
        project_type: ProjectType,
        average_score: float,
        primary_language: str | None = None,
    ) -> ComparisonResult:
        """
        Get comparison result with similar repos and percentile.

        Args:
            project_type: Type of project.
            average_score: Your repository's average commit score.
            primary_language: Primary programming language.

        Returns:
            ComparisonResult with similar repos and analysis.
        """
        # Search for similar repos
        similar_repos, search_query = self.search_similar(
            project_type=project_type,
            primary_language=primary_language,
            limit=5,
        )

        # Calculate percentile based on score
        rounded_score = max(1, min(10, round(average_score)))
        percentile = SCORE_PERCENTILES.get(rounded_score, 50)

        # Generate tip based on score
        tip = self._generate_tip(average_score, similar_repos)

        return ComparisonResult(
            similar_repos=similar_repos,
            percentile=percentile,
            search_query=search_query,
            tip=tip,
        )

    def compare(
        self,
        project_type: ProjectType,
        average_score: float,
        primary_language: str | None = None,
    ) -> MarketPosition:
        """
        Compare and return MarketPosition for storage.

        Args:
            project_type: Type of project.
            average_score: Your repository's average commit score.
            primary_language: Primary programming language.

        Returns:
            MarketPosition with comparison data.
        """
        result = self.get_comparison_result(
            project_type=project_type,
            average_score=average_score,
            primary_language=primary_language,
        )

        return MarketPosition(
            comparison_repos=[r.full_name for r in result.similar_repos],
            industry_percentile=result.percentile,
            reference_scores={},  # No fake scores anymore
        )

    def _generate_tip(
        self,
        average_score: float,
        similar_repos: list[SimilarRepo],
    ) -> str | None:
        """Generate tip based on score."""
        if average_score >= 8:
            return "Excellent commit quality! You're in the top tier."
        elif average_score >= 7:
            return "Good commit messages. Add more context about 'why' to reach excellence."
        elif average_score >= 6:
            return "Decent commits. Try conventional format: feat(scope): description"
        elif average_score >= 5:
            return "Room for improvement. Be specific about what changed and why."
        else:
            if similar_repos:
                top_repo = similar_repos[0].full_name
                return f"Study commit history of {top_repo} for inspiration."
            return "Focus on clarity: what changed, where, and why."
