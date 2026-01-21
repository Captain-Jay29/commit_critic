"""Build detailed collaborator profiles with area detection."""

from collections import Counter
from pathlib import Path

from openai import OpenAI

from ..config import get_settings
from ..vcs.operations import CommitInfo
from .schemas import CollaboratorInsight


class CollaboratorProfiler:
    """Build detailed profiles for repository collaborators."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)

    def build_profile(
        self,
        name: str,
        commits: list[CommitInfo],
        scores: list[int],
        email: str | None = None,
    ) -> CollaboratorInsight:
        """
        Build a detailed profile for a collaborator.

        Args:
            name: Collaborator name.
            commits: List of their commits.
            scores: List of scores for their commits.
            email: Optional email address.

        Returns:
            CollaboratorInsight with detailed profile.
        """
        # Calculate basic stats
        commit_count = len(commits)
        avg_score = sum(scores) / len(scores) if scores else None

        # Detect primary areas from file paths
        primary_areas = self._detect_areas(commits)

        # Generate area summary using AI
        area_summary = self._generate_area_summary(name, primary_areas, commits)

        # Detect roast patterns
        roast_patterns = self._detect_roast_patterns(commits)

        # Determine trend
        trend = self._calculate_trend(scores)

        return CollaboratorInsight(
            name=name,
            email=email,
            commit_count=commit_count,
            avg_score=avg_score,
            primary_areas=primary_areas,
            area_summary=area_summary,
            roast_patterns=roast_patterns,
            trend=trend,
        )

    def _detect_areas(self, commits: list[CommitInfo]) -> list[str]:
        """Detect primary areas of work from commit file paths."""
        dir_counts: Counter = Counter()

        for commit in commits:
            for file_path in commit.files_changed:
                parts = Path(file_path).parts
                if len(parts) >= 2:
                    # Use first two directory levels
                    area = f"{parts[0]}/{parts[1]}"
                elif len(parts) == 1:
                    area = parts[0]
                else:
                    continue
                dir_counts[area] += 1

        # Return top 5 areas
        return [area for area, _ in dir_counts.most_common(5)]

    def _generate_area_summary(
        self,
        name: str,
        areas: list[str],
        commits: list[CommitInfo],
    ) -> str | None:
        """Generate a human-readable summary of the contributor's work areas."""
        if not areas:
            return None

        # Get recent commit messages for context
        recent_messages = [c.message for c in commits[:10]]

        prompt = f"""Based on this contributor's work, write a one-sentence description of what they work on.

Contributor: {name}
Primary areas: {', '.join(areas[:5])}
Recent commits:
{chr(10).join(f'- {m}' for m in recent_messages[:5])}

Write a brief, professional description like:
- "Owns authentication and user management"
- "Frontend specialist, focuses on React components"
- "DevOps and CI/CD infrastructure"

Keep it under 50 characters. Just the description, no quotes."""

        try:
            response = self.client.chat.completions.create(
                model=self.settings.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=50,
            )
            result = response.choices[0].message.content
            return result.strip() if result else None
        except Exception:
            return None

    def _detect_roast_patterns(self, commits: list[CommitInfo]) -> list[str]:
        """Detect patterns worth roasting."""
        patterns = []

        # Count WIP commits
        wip_count = sum(
            1 for c in commits if "wip" in c.message.lower()
        )
        if wip_count >= 5:
            patterns.append(f"{wip_count} WIP commits")

        # Count one-word commits
        one_word_count = sum(
            1 for c in commits if len(c.message.strip().split()) == 1
        )
        if one_word_count >= 5:
            patterns.append(f"Champion of one-word commits ({one_word_count} total)")

        # Count "fix" only commits
        fix_only_count = sum(
            1 for c in commits
            if c.message.lower().strip() in ("fix", "fixed", "fixes")
        )
        if fix_only_count >= 3:
            patterns.append(f'{fix_only_count} commits called just "fix"')

        # Find worst commit
        vague_keywords = {"fix", "update", "change", "stuff", "misc", "wip"}
        for commit in commits:
            msg = commit.message.lower().strip()
            if msg in vague_keywords or len(msg) <= 3:
                patterns.append(f'Once wrote: "{commit.message}"')
                break

        return patterns[:3]  # Limit to 3 roast patterns

    def _calculate_trend(self, scores: list[int]) -> str | None:
        """Calculate if contributor is improving, declining, or stable."""
        if len(scores) < 5:
            return None

        # Compare recent half to older half
        mid = len(scores) // 2
        recent_avg = sum(scores[:mid]) / mid
        older_avg = sum(scores[mid:]) / (len(scores) - mid)

        diff = recent_avg - older_avg
        if diff >= 1.0:
            return "improving"
        elif diff <= -1.0:
            return "declining"
        else:
            return "stable"
