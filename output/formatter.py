"""Rich terminal output formatting."""

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from ..agents.analyzer import AnalysisResult, AnalysisSummary
from ..agents.writer import CommitSuggestion
from ..vcs.operations import DiffInfo


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
        if suggestion.scope:
            header = f"{suggestion.commit_type}({suggestion.scope}): {suggestion.subject}"
        else:
            header = f"{suggestion.commit_type}: {suggestion.subject}"

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
            "[bold][[Enter]][/bold] Accept  "
            "[bold][[e]][/bold] Edit  "
            "[bold][[r]][/bold] Regenerate  "
            "[bold][[q]][/bold] Quit"
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
