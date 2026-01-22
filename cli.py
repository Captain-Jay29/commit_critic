"""Commit Critic CLI using Typer."""

from pathlib import Path
from typing import Annotated

import click
import typer
from git.exc import GitCommandError, InvalidGitRepositoryError
from rich.console import Console

from .agents.analyzer import CommitAnalyzer
from .agents.writer import CommitWriter
from .config import get_settings
from .memory import MemorySeeder, MemoryStore, SeedingProgress
from .output.formatter import OutputFormatter
from .vcs.operations import get_commits, get_repo, get_staged_diff
from .vcs.remote import clone_remote_repo, get_repo_name_from_url, is_valid_git_url

app = typer.Typer(
    name="critic",
    help="AI-powered git commit message analyzer and writer.",
    no_args_is_help=True,
)

# Memory subcommand group
memory_app = typer.Typer(help="Memory management commands.")
app.add_typer(memory_app, name="memory")

console = Console()
formatter = OutputFormatter()


def check_api_key() -> bool:
    """Check if OpenAI API key is configured."""
    settings = get_settings()
    if not settings.validate_api_key():
        formatter.print_error(
            "OpenAI API key not configured.\nSet it via: export OPENAI_API_KEY='sk-...'"
        )
        return False
    return True


@app.command()
def analyze(
    url: Annotated[
        str | None,
        typer.Option("--url", "-u", help="Remote Git repository URL to analyze"),
    ] = None,
    count: Annotated[
        int,
        typer.Option("--count", "-n", help="Number of commits to analyze"),
    ] = 20,
) -> None:
    """Analyze and score commit messages."""
    if not check_api_key():
        raise typer.Exit(1)

    try:
        # Get repository
        if url:
            if not is_valid_git_url(url):
                formatter.print_error(f"Invalid Git URL: {url}")
                raise typer.Exit(1)

            formatter.print_cloning(url)
            repo = clone_remote_repo(url, depth=count + 10)
        else:
            try:
                repo = get_repo()
            except InvalidGitRepositoryError:
                formatter.print_error("Not a git repository. Use --url to analyze a remote repo.")
                raise typer.Exit(1) from None

        # Get commits
        commits = get_commits(repo, count=count)
        if not commits:
            formatter.print_error("No commits found in repository.")
            raise typer.Exit(1)

        formatter.print_analyzing(len(commits))
        console.print()

        # Analyze commits
        analyzer = CommitAnalyzer()
        results = []

        for i, result in enumerate(analyzer.analyze_commits(commits), 1):
            results.append(result)
            formatter.print_analysis_progress(i, len(commits), result)

        # Print results
        formatter.print_poor_commits(results)
        formatter.print_good_commits(results)

        # Print summary
        summary = analyzer.summarize_results(results)
        formatter.print_summary(summary)

    except GitCommandError as e:
        formatter.print_error(f"Git error: {e}")
        raise typer.Exit(1) from None
    except click.exceptions.Exit:
        # Re-raise typer.Exit (which is click.exceptions.Exit) without catching it
        raise
    except Exception as e:
        formatter.print_error(f"Unexpected error: {e}")
        raise typer.Exit(1) from None


@app.command()
def write() -> None:
    """Suggest a commit message for staged changes."""
    if not check_api_key():
        raise typer.Exit(1)

    try:
        # Get local repository
        try:
            repo = get_repo()
        except InvalidGitRepositoryError:
            formatter.print_error("Not a git repository.")
            raise typer.Exit(1) from None

        # Get staged diff
        diff = get_staged_diff(repo)
        if not diff:
            formatter.print_no_staged_changes()
            raise typer.Exit(0)

        # Show diff info
        formatter.print_diff_info(diff)

        # Get suggestion
        writer = CommitWriter()
        suggestion = writer.suggest_message(diff)

        # Display suggestion
        formatter.print_suggestion(suggestion)
        formatter.print_write_prompt()

        # Interactive loop
        while True:
            console.print("> ", end="")
            choice = input().strip().lower()

            if choice == "c":
                # Commit directly
                full_message = suggestion.full_message
                if suggestion.scope:
                    full_message = (
                        f"{suggestion.commit_type}({suggestion.scope}): {suggestion.subject}"
                    )
                else:
                    full_message = f"{suggestion.commit_type}: {suggestion.subject}"
                if suggestion.body:
                    full_message += f"\n\n{suggestion.body}"

                console.print()
                console.print("[dim]Committing...[/dim]")
                repo.index.commit(full_message)
                formatter.print_success(f"Committed: {full_message.split(chr(10))[0]}")
                break

            elif choice in ("", "y", "yes"):
                # Copy - print for manual use
                full_message = suggestion.full_message
                if suggestion.scope:
                    full_message = (
                        f"{suggestion.commit_type}({suggestion.scope}): {suggestion.subject}"
                    )
                else:
                    full_message = f"{suggestion.commit_type}: {suggestion.subject}"
                if suggestion.body:
                    full_message += f"\n\n{suggestion.body}"

                console.print()
                formatter.print_success("Commit message:")
                console.print(f"\n[bold]{full_message}[/bold]\n")
                console.print("[dim]Copy the message above and use:[/dim]")
                console.print('[dim]  git commit -m "<message>"[/dim]')
                break

            elif choice == "f":
                # Feedback - give feedback to regenerate
                console.print()
                console.print("[dim]Enter feedback for improvement:[/dim]")
                console.print("> ", end="")
                feedback = input().strip()
                if feedback:
                    console.print()
                    console.print("[dim]Regenerating with feedback...[/dim]")
                    previous = suggestion.full_message
                    suggestion = writer.regenerate_message(diff, previous, feedback)
                    formatter.print_suggestion(suggestion)
                    formatter.print_write_prompt()

            elif choice == "r":
                # Regenerate
                console.print()
                console.print("[dim]Regenerating...[/dim]")
                previous = suggestion.full_message
                suggestion = writer.regenerate_message(diff, previous)
                formatter.print_suggestion(suggestion)
                formatter.print_write_prompt()

            elif choice == "q":
                # Quit
                console.print()
                console.print("[dim]Cancelled.[/dim]")
                break

            else:
                console.print("[dim]Invalid choice. Use c, Enter, f, r, or q.[/dim]")

    except GitCommandError as e:
        formatter.print_error(f"Git error: {e}")
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0) from None
    except click.exceptions.Exit:
        # Re-raise typer.Exit (which is click.exceptions.Exit) without catching it
        raise
    except Exception as e:
        formatter.print_error(f"Unexpected error: {e}")
        raise typer.Exit(1) from None


@app.command()
def init(
    url: Annotated[
        str | None,
        typer.Option("--url", "-u", help="Remote Git repository URL to seed from"),
    ] = None,
    count: Annotated[
        int,
        typer.Option("--count", "-n", help="Number of commits to analyze"),
    ] = 100,
    no_roasts: Annotated[
        bool,
        typer.Option("--no-roasts", help="Skip extracting roast material"),
    ] = False,
) -> None:
    """Seed memory from repository commits (learn your style)."""
    if not check_api_key():
        raise typer.Exit(1)

    try:
        repo_path: Path | None = None

        # Get repository
        if url:
            if not is_valid_git_url(url):
                formatter.print_error(f"Invalid Git URL: {url}")
                raise typer.Exit(1)

            formatter.print_seeding_header()
            formatter.print_seeding_phase(1, "Cloning repository", "started", f"Cloning {url}...")
            repo = clone_remote_repo(url, depth=count + 10)
            repo_name = get_repo_name_from_url(url)
            repo_path = Path(repo.working_dir) if repo.working_dir else None
            formatter.print_seeding_phase(1, "Cloning repository", "done", f"Done - Cloned {repo_name}")
        else:
            try:
                repo = get_repo()
                repo_name = Path(repo.working_dir).name if repo.working_dir else "unknown"
                repo_path = Path(repo.working_dir) if repo.working_dir else None
                formatter.print_seeding_header()
                formatter.print_seeding_phase(1, "Repository", "done", f"Using local repo: {repo_name}")
            except InvalidGitRepositoryError:
                formatter.print_error("Not a git repository. Use --url to seed from a remote repo.")
                raise typer.Exit(1) from None

        # Extract commits
        formatter.print_seeding_phase(2, "Extracting commits", "started", "Extracting commits...")
        commits = get_commits(repo, count=count)
        if not commits:
            formatter.print_error("No commits found in repository.")
            raise typer.Exit(1)

        # Count unique authors
        authors = {c.author for c in commits}
        formatter.print_seeding_phase(
            2, "Extracting commits", "done",
            f"Done - Extracted {len(commits)} commits from {len(authors)} contributors"
        )

        # Create progress callback
        def on_progress(progress: SeedingProgress) -> None:
            formatter.print_seeding_phase(
                progress.phase,
                progress.phase_name,
                progress.status,
                progress.message,
                progress.detail,
                progress.progress,
            )

        # Seed memory
        seeder = MemorySeeder(on_progress=on_progress)
        result = seeder.seed(
            commits=commits,
            repo_name=repo_name,
            repo_url=url,
            repo_path=repo_path,
            include_roasts=not no_roasts,
        )

        # Print summary
        formatter.print_seeding_summary(result)

    except GitCommandError as e:
        formatter.print_error(f"Git error: {e}")
        raise typer.Exit(1) from None
    except click.exceptions.Exit:
        raise
    except Exception as e:
        formatter.print_error(f"Unexpected error: {e}")
        raise typer.Exit(1) from None


@memory_app.command("status")
def memory_status() -> None:
    """Show what's been learned."""
    store = MemoryStore()
    repos = store.list_repositories()

    if not repos:
        console.print()
        console.print("[yellow]No repositories in memory.[/yellow]")
        console.print("[dim]Run 'critic init' to seed memory from a repository.[/dim]")
        return

    for repo in repos:
        collaborators = store.list_collaborators(repo.id)
        exemplar_count = store.count_exemplars(repo.id)
        antipattern_count = store.count_antipatterns(repo.id)

        formatter.print_memory_status(
            repo=repo,
            collaborators=collaborators,
            exemplar_count=exemplar_count,
            antipattern_count=antipattern_count,
        )


@memory_app.command("clear")
def memory_clear(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Clear all memory data."""
    store = MemoryStore()
    stats = store.get_stats()

    if stats["repositories"] == 0:
        console.print("[yellow]Memory is already empty.[/yellow]")
        return

    if not force:
        console.print()
        console.print("[bold]Current memory contents:[/bold]")
        console.print(f"  Repositories: {stats['repositories']}")
        console.print(f"  Collaborators: {stats['collaborators']}")
        console.print(f"  Exemplars: {stats['exemplars']}")
        console.print(f"  Antipatterns: {stats['antipatterns']}")
        console.print()

        confirm = typer.confirm("Are you sure you want to clear all memory?")
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            return

    store.clear_all()
    formatter.print_success("Memory cleared.")


@app.command()
def config(
    show: Annotated[
        bool,
        typer.Option("--show", "-s", help="Show current configuration"),
    ] = True,
) -> None:
    """Show or set configuration."""
    settings = get_settings()

    console.print()
    console.print("[bold]Commit Critic Configuration[/bold]")
    console.print()
    console.print(f"  Model: [cyan]{settings.model}[/cyan]")
    console.print(f"  Embedding Model: [cyan]{settings.embedding_model}[/cyan]")
    console.print(f"  Default Commit Count: [cyan]{settings.default_commit_count}[/cyan]")
    console.print(f"  Data Directory: [cyan]{settings.data_dir}[/cyan]")
    console.print()

    if settings.validate_api_key():
        key_preview = settings.openai_api_key[:8] + "..." + settings.openai_api_key[-4:]
        console.print(f"  API Key: [green]{key_preview}[/green] ✓")
    else:
        console.print("  API Key: [red]Not configured[/red] ✗")
        console.print()
        console.print("[dim]Set via: export OPENAI_API_KEY='sk-...'[/dim]")


@app.command()
def version() -> None:
    """Show version information."""
    from . import __version__

    console.print(f"Commit Critic v{__version__}")


if __name__ == "__main__":
    app()
