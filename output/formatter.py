"""Rich terminal output formatting."""

# Import memory types only when needed to avoid circular imports
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from ..agents.analyzer import AnalysisResult, AnalysisSummary
from ..agents.writer import CommitSuggestion
from ..vcs.operations import DiffInfo

if TYPE_CHECKING:
    from ..memory import Collaborator, Repository
    from ..memory.seeder import SeedingResult


class OutputFormatter:
    """Format output using Rich for beautiful terminal display."""

    def __init__(self) -> None:
        self.console = Console()

    def print_header(self, text: str) -> None:
        """Print a section header."""
        self.console.print()
        self.console.print(f"[bold cyan]{text}[/bold cyan]")

    def print_cloning(self, url: str) -> None:
        """Print cloning message."""
        self.console.print(f"[dim]Cloning[/dim] {url}...")

    def print_analyzing(self, count: int) -> None:
        """Print analyzing message."""
        self.console.print(f"[dim]Analyzing[/dim] {count} commits...")

    def get_score_style(self, score: int) -> tuple[str, str]:
        """Get color and emoji for a score."""
        if score <= 3:
            return "red", "💩"
        elif score <= 5:
            return "yellow", "😐"
        elif score <= 7:
            return "blue", "👍"
        else:
            return "green", "✨"

    def print_analysis_progress(
        self,
        current: int,
        total: int,
        result: AnalysisResult,
    ) -> None:
        """Print progress for a single commit analysis."""
        color, emoji = self.get_score_style(result.score)

        # Truncate message if too long
        message = result.commit.message.split("\n")[0]
        if len(message) > 50:
            message = message[:47] + "..."

        self.console.print(
            f"[dim][{current}/{total}][/dim] "
            f'"{message}" → '
            f"[{color}]{result.score}/10[/{color}] {emoji}"
        )

    def print_poor_commits(self, results: list[AnalysisResult]) -> None:
        """Print section for commits that need work."""
        poor = [r for r in results if r.score <= 5]

        if not poor:
            return

        self.console.print()
        self.console.rule("[bold red]💩 COMMITS THAT NEED WORK[/bold red]", style="red")
        self.console.print()

        for result in poor:
            message = result.commit.message.split("\n")[0]
            color, _ = self.get_score_style(result.score)

            self.console.print(
                Panel(
                    f'[bold]"{message}"[/bold] [dim]({result.commit.short_hash})[/dim]\n'
                    f"[{color}]Score: {result.score}/10[/{color}]\n"
                    f"[dim]Issue:[/dim] {result.feedback}\n"
                    + (
                        f'[green]Better:[/green] "{result.suggestion}"' if result.suggestion else ""
                    ),
                    box=box.ROUNDED,
                    padding=(0, 1),
                )
            )

    def print_good_commits(self, results: list[AnalysisResult]) -> None:
        """Print section for well-written commits."""
        good = [r for r in results if r.score >= 8]

        if not good:
            return

        self.console.print()
        self.console.rule("[bold green]✨ WELL-WRITTEN COMMITS[/bold green]", style="green")
        self.console.print()

        for result in good:
            message = result.commit.message.split("\n")[0]

            self.console.print(
                Panel(
                    f'[bold]"{message}"[/bold] [dim]({result.commit.short_hash})[/dim]\n'
                    f"[green]Score: {result.score}/10[/green]\n"
                    f"[dim]Why:[/dim] {result.feedback}",
                    box=box.ROUNDED,
                    padding=(0, 1),
                )
            )

    def print_summary(self, summary: AnalysisSummary) -> None:
        """Print summary statistics."""
        self.console.print()
        self.console.rule("[bold blue]📈 STATS[/bold blue]", style="blue")
        self.console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")

        # Color code the average
        avg = summary.average_score
        if avg <= 4:
            avg_style = "red"
        elif avg <= 6:
            avg_style = "yellow"
        else:
            avg_style = "green"

        table.add_row("Total commits", str(summary.total))
        table.add_row("Average score", f"[{avg_style}]{avg:.1f}/10[/{avg_style}]")
        table.add_row("Poor commits (1-3)", f"[red]{summary.poor_commits}[/red]")
        table.add_row("Average commits (4-6)", f"[yellow]{summary.average_commits}[/yellow]")
        table.add_row("Good commits (7-10)", f"[green]{summary.good_commits}[/green]")

        if summary.vague_count > 0:
            pct = (summary.vague_count / summary.total) * 100
            table.add_row("Vague commits", f"[red]{summary.vague_count} ({pct:.0f}%)[/red]")

        if summary.one_word_count > 0:
            pct = (summary.one_word_count / summary.total) * 100
            table.add_row("One-word commits", f"[red]{summary.one_word_count} ({pct:.0f}%)[/red]")

        self.console.print(table)

    def print_diff_info(self, diff: DiffInfo) -> None:
        """Print information about staged changes."""
        self.console.print()
        self.console.print("[bold]📝 Analyzing staged changes...[/bold]")
        self.console.print(
            f"   {len(diff.files)} files changed "
            f"([green]+{diff.additions}[/green] [red]-{diff.deletions}[/red] lines)"
        )
        self.console.print()
        self.console.print("[bold]🧠 Understanding changes...[/bold]")
        for file in diff.files[:5]:  # Show first 5 files
            self.console.print(f"   • {file}")
        if len(diff.files) > 5:
            self.console.print(f"   [dim]... and {len(diff.files) - 5} more[/dim]")

    def print_suggestion(self, suggestion: CommitSuggestion) -> None:
        """Print a commit message suggestion."""
        self.console.print()
        self.console.print("[bold]💡 Suggested commit:[/bold]")

        # Build the full message display
        # Check if subject already has the type prefix to avoid duplication
        subject = suggestion.subject
        if suggestion.scope:
            prefix = f"{suggestion.commit_type}({suggestion.scope}):"
        else:
            prefix = f"{suggestion.commit_type}:"

        if subject.lower().startswith(prefix.lower()):
            header = subject  # Already has prefix
        elif subject.lower().startswith(suggestion.commit_type.lower()):
            header = subject  # Has type but maybe different format
        else:
            header = f"{prefix} {subject}"

        message_lines = [header]
        if suggestion.body:
            message_lines.append("")
            message_lines.extend(suggestion.body.split("\n"))

        message_text = "\n".join(message_lines)

        self.console.print(
            Panel(
                message_text,
                box=box.ROUNDED,
                border_style="green",
                padding=(0, 1),
            )
        )

        self.console.print()
        self.console.print(f"[dim]Why: {suggestion.explanation}[/dim]")

    def print_write_prompt(self) -> None:
        """Print the interactive prompt for write mode."""
        self.console.print()
        self.console.print(
            "[bold]\\[c][/bold] Commit  "
            "[bold]\\[Enter][/bold] Copy  "
            "[bold]\\[f][/bold] Feedback  "
            "[bold]\\[r][/bold] Regenerate  "
            "[bold]\\[q][/bold] Quit"
        )

    def print_no_staged_changes(self) -> None:
        """Print message when there are no staged changes."""
        self.console.print()
        self.console.print(
            Panel(
                "[yellow]No staged changes found.[/yellow]\n\n"
                "Stage your changes first:\n"
                "  [dim]git add <files>[/dim]\n"
                "  [dim]git add -p[/dim] (interactive)",
                title="⚠️  Nothing to commit",
                box=box.ROUNDED,
            )
        )

    def print_error(self, message: str) -> None:
        """Print an error message."""
        self.console.print(f"[bold red]Error:[/bold red] {message}")

    def print_success(self, message: str) -> None:
        """Print a success message."""
        self.console.print(f"[bold green]✓[/bold green] {message}")

    def create_progress(self) -> Progress:
        """Create a progress bar for long operations."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        )

    # ========================================================================
    # Memory/Init Mode Methods
    # ========================================================================

    def print_seeding_header(self) -> None:
        """Print the header for seeding mode."""
        self.console.print()
        self.console.print(
            Panel(
                "[bold cyan]COMMIT CRITIC - LEARNING MODE[/bold cyan]",
                box=box.DOUBLE,
                padding=(0, 2),
            )
        )
        self.console.print()

    def print_seeding_phase(
        self,
        phase: int,
        phase_name: str,
        status: str,
        message: str,
        detail: str | None = None,
        progress: float | None = None,
    ) -> None:
        """Print progress for a seeding phase."""
        if status == "started":
            self.console.print(f"[bold][{phase}/8][/bold] {message}")
        elif status == "progress":
            # Overwrite line for progress updates
            if progress is not None:
                bar_width = 20
                filled = int((progress / 100) * bar_width)
                bar = "=" * filled + "-" * (bar_width - filled)
                self.console.print(f"      [{bar}] {progress:.0f}%", end="\r")
            else:
                self.console.print(f"      {message}")
        elif status == "done":
            if detail:
                self.console.print(f"      [green]Done[/green] - {detail}")
            else:
                self.console.print("      [green]Done[/green]")
            self.console.print()

    def print_seeding_summary(self, result: "SeedingResult") -> None:
        """Print the summary after seeding completes."""

        self.console.print()
        self.console.print(
            Panel(
                "[bold green]MEMORY SEEDED[/bold green]",
                box=box.DOUBLE,
                padding=(0, 2),
            )
        )
        self.console.print()

        # Summary table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")

        table.add_row("Repository", result.repo_name)
        table.add_row("Commits analyzed", str(result.commit_count))

        # Color code average
        avg = result.average_score
        if avg <= 4:
            avg_style = "red"
        elif avg <= 6:
            avg_style = "yellow"
        else:
            avg_style = "green"
        table.add_row("Average score", f"[{avg_style}]{avg:.1f}/10[/{avg_style}]")

        table.add_row("Exemplars saved", f"[green]{result.exemplar_count}[/green]")
        table.add_row("Contributors profiled", str(result.collaborator_count))

        if result.antipattern_count > 0:
            table.add_row("Roast material", f"[yellow]{result.antipattern_count} patterns[/yellow]")

        self.console.print(table)
        self.console.print()

        if result.has_roasts:
            self.console.print("[dim]HALL OF SHAME material collected![/dim]")
        else:
            self.console.print("[dim]No roast material - this team is too good![/dim]")

        self.console.print()
        self.console.print("[bold]Ready![/bold] Try: [cyan]critic analyze[/cyan]")

    def print_memory_status(
        self,
        repo: "Repository",
        collaborators: list["Collaborator"],
        exemplar_count: int,
        antipattern_count: int,
    ) -> None:
        """Print memory status for a repository."""

        self.console.print()
        self.console.rule(f"[bold cyan]{repo.name}[/bold cyan]", style="cyan")
        self.console.print()

        # Codebase DNA section
        self.console.print("[bold]CODEBASE DNA[/bold]")
        self.console.print(f"  Type: [cyan]{repo.project_type.value}[/cyan]")
        if repo.primary_language:
            self.console.print(f"  Primary Language: [cyan]{repo.primary_language}[/cyan]")

        # Language breakdown
        if repo.languages:
            self.console.print("  Languages:")
            for lang in repo.languages[:5]:
                bar_width = 20
                filled = int((lang.percentage / 100) * bar_width)
                bar = "=" * filled + "-" * (bar_width - filled)
                self.console.print(f"    {lang.language:12} [{bar}] {lang.percentage:.0f}%")

        if repo.frameworks:
            self.console.print(f"  Stack: [cyan]{', '.join(repo.frameworks)}[/cyan]")

        self.console.print()

        # Commit style section
        self.console.print("[bold]COMMIT STYLE[/bold]")
        self.console.print(f"  Pattern: [cyan]{repo.style_pattern.value}[/cyan]")
        if repo.uses_scopes and repo.common_scopes:
            self.console.print(f"  Scopes: [cyan]{', '.join(repo.common_scopes[:5])}[/cyan]")
        if repo.ticket_pattern:
            self.console.print(f"  Ticket Pattern: [cyan]{repo.ticket_pattern}[/cyan]")

        self.console.print()

        # Stats section
        self.console.print("[bold]STATS[/bold]")
        self.console.print(f"  Exemplars: [green]{exemplar_count}[/green]")
        self.console.print(f"  Contributors: [cyan]{len(collaborators)}[/cyan]")
        if antipattern_count > 0:
            self.console.print(f"  Antipatterns: [yellow]{antipattern_count}[/yellow]")

        self.console.print()

        # Top contributors
        if collaborators:
            self.console.print("[bold]TOP CONTRIBUTORS[/bold]")
            for collab in collaborators[:5]:
                avg = collab.avg_score
                if avg is not None:
                    if avg <= 4:
                        score_style = "red"
                    elif avg <= 6:
                        score_style = "yellow"
                    else:
                        score_style = "green"
                    score_str = f"[{score_style}]{avg:.1f}/10[/{score_style}]"
                else:
                    score_str = "[dim]N/A[/dim]"

                self.console.print(f"  {collab.name}: {collab.commit_count} commits, {score_str}")
                if collab.primary_areas:
                    self.console.print(
                        f"    [dim]Areas: {', '.join(collab.primary_areas[:3])}[/dim]"
                    )

        self.console.print()
        self.console.print(f"[dim]Seeded: {repo.seeded_at.strftime('%Y-%m-%d %H:%M')}[/dim]")
