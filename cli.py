"""Commit Critic CLI using Typer."""

from typing import Annotated

import typer
from git.exc import GitCommandError, InvalidGitRepositoryError
from rich.console import Console

from .agents.analyzer import CommitAnalyzer
from .agents.writer import CommitWriter
from .config import get_settings
from .output.formatter import OutputFormatter
from .vcs.operations import get_commits, get_repo, get_staged_diff
from .vcs.remote import clone_remote_repo, is_valid_git_url

app = typer.Typer(
    name="critic",
    help="AI-powered git commit message analyzer and writer.",
    no_args_is_help=True,
)
console = Console()
formatter = OutputFormatter()


def check_api_key() -> bool:
    """Check if OpenAI API key is configured."""
    settings = get_settings()
    if not settings.validate_api_key():
        formatter.print_error(
            "OpenAI API key not configured.\n"
            "Set it via: export OPENAI_API_KEY='sk-...'"
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
                formatter.print_error(
                    "Not a git repository. Use --url to analyze a remote repo."
                )
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

            if choice in ("", "y", "yes"):
                # Accept - copy to clipboard or print for manual use
                full_message = suggestion.full_message
                if suggestion.scope:
                    full_message = f"{suggestion.commit_type}({suggestion.scope}): {suggestion.subject}"
                else:
                    full_message = f"{suggestion.commit_type}: {suggestion.subject}"
                if suggestion.body:
                    full_message += f"\n\n{suggestion.body}"

                console.print()
                formatter.print_success("Commit message:")
                console.print(f"\n[bold]{full_message}[/bold]\n")
                console.print("[dim]Copy the message above and use:[/dim]")
                console.print("[dim]  git commit -m \"<message>\"[/dim]")
                break

            elif choice == "e":
                # Edit - let user modify
                console.print()
                console.print("[dim]Enter your edited commit message (single line):[/dim]")
                console.print("> ", end="")
                edited = input().strip()
                if edited:
                    console.print()
                    formatter.print_success("Your commit message:")
                    console.print(f"\n[bold]{edited}[/bold]\n")
                break

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
                console.print("[dim]Invalid choice. Use Enter, e, r, or q.[/dim]")

    except GitCommandError as e:
        formatter.print_error(f"Git error: {e}")
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0) from None
    except Exception as e:
        formatter.print_error(f"Unexpected error: {e}")
        raise typer.Exit(1) from None


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
