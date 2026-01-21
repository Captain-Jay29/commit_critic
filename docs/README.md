# Commit Critic

An AI-powered CLI tool that analyzes git commit messages and helps write better ones.

## Overview

Commit Critic uses GPT-5.2 to score existing commits and suggest improvements, while learning from your best commits to provide personalized feedback. It supports both local repositories and remote URLs.

## Core Features

### Two Modes

**`--analyze`** - Score and critique existing commits
- Works on local repo (default) or any remote Git URL
- Scores each commit 1-10 with actionable feedback
- Shows aggregate statistics and patterns

**`--write`** - Help write new commit messages
- Analyzes your staged changes (`git diff --staged`)
- Understands the actual code diff
- Suggests conventional commit messages
- Interactive accept/edit/regenerate flow

### Memory System

Commit Critic learns from your best commits:

1. **Commit Exemplars** - Stores high-scoring commits (8+) as examples
2. **Project Conventions** - Auto-detects your project's commit style
3. **Style Memory** - Embeds commits for semantic similarity search

When suggesting new commits, it retrieves your own best commits as few-shot examples.

### Intelligent Analysis

- **Convention Detection** - Recognizes conventional commits, ticket references, emoji usage
- **Diff Intelligence** - Understands code changes to generate accurate messages
- **Streaming Output** - Real-time progress with Rich terminal formatting

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Layer (Typer)                      │
│                  --analyze  |  --write                      │
├─────────────────────────────────────────────────────────────┤
│                    Agent Layer (OpenAI)                     │
│  ┌──────────────────┐    ┌──────────────────┐              │
│  │ Analyzer Agent   │    │ Writer Agent     │              │
│  │ (score commits)  │    │ (suggest message)│              │
│  └──────────────────┘    └──────────────────┘              │
├─────────────────────────────────────────────────────────────┤
│                    Memory System                            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │ Style Memory│  │ Project Facts│  │ Commit Exemplars│    │
│  │ (user prefs)│  │ (conventions)│  │ (best examples) │    │
│  └─────────────┘  └──────────────┘  └─────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                    Git Operations                           │
│  [Local Repo] [Remote URL Clone] [Diffs] [Commits]         │
└─────────────────────────────────────────────────────────────┘
```

## Usage

```bash
# Initialize memory by scanning a repo
critic --init                           # Scan current repo
critic --init --url https://github.com/org/repo  # Learn from remote
critic --init -n 100                    # Scan last 100 commits

# Analyze commits
critic --analyze                        # Local repo, last 20 commits
critic --analyze -n 50                  # Last 50 commits
critic --analyze --url https://github.com/steel-dev/steel-browser

# Write commit messages
critic --write                          # Suggest for staged changes

# Utilities
critic config                           # Show/set config
critic memory show                      # Show stored exemplars
critic memory clear                     # Clear memory
```

## Example Output

### Analyze Mode
```
$ critic --analyze --url https://github.com/steel-dev/steel-browser

🔍 Cloning repository...
📊 Analyzing last 20 commits...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💩 COMMITS THAT NEED WORK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Commit: "fixed bug" (abc123)
Score: 2/10
Issue: Too vague - which bug? What was the fix?
Better: "fix(auth): resolve token expiration handling"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ WELL-WRITTEN COMMITS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Commit: "feat(browser): add stealth mode for automation" (def456)
Score: 9/10
Why: Clear scope, specific action, states purpose

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 STATS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Average: 6.2/10
Vague commits: 4 (20%)
```

### Write Mode
```
$ critic --write

📝 Analyzing staged changes...
   3 files changed (+47 -12 lines)

🧠 Understanding changes...
   • auth/token.py: Added error handling
   • auth/refresh.py: New retry logic
   • tests/test_auth.py: Edge case coverage

💡 Suggested commit:
┌──────────────────────────────────────────────
│ fix(auth): handle token expiration gracefully
│
│ - Add specific error handling for expired tokens
│ - Implement retry logic for refresh failures
│ - Add test coverage for edge cases
└──────────────────────────────────────────────

[Enter] Accept  [e] Edit  [r] Regenerate  [q] Quit
```

## Tech Stack

- **Python 3.11+** with Typer + Rich
- **OpenAI SDK** - GPT-5.2 for reasoning, text-embedding-3-small for memory
- **GitPython** - Git operations
- **SQLite** - Local memory storage with embeddings

## Project Structure

```
commit_critic/
├── cli.py              # Typer CLI entry point
├── config.py           # Settings & API keys
├── agents/
│   ├── analyzer.py     # Commit scoring agent
│   ├── writer.py       # Message suggestion agent
│   └── prompts.py      # Prompt templates
├── git/
│   ├── operations.py   # GitPython: commits, diff
│   └── remote.py       # URL cloning logic
├── memory/
│   ├── store.py        # SQLite + embeddings
│   └── conventions.py  # Project style detection
└── output/
    └── formatter.py    # Rich terminal output
```

## Implementation Order

> **Note:** Build core functionality first, then add memory features.

### Phase 1: Core CLI + Git (No Memory)
- Typer CLI skeleton with `--analyze` and `--write` flags
- Git operations: fetch commits, get staged diff
- Remote URL cloning (shallow clone to temp dir)
- Basic GPT-5.2 integration for scoring/writing

### Phase 2: Rich Output
- Beautiful terminal formatting with Rich
- Progress indicators and streaming output
- Color-coded scores and stats

### Phase 3: Memory System (Innovative Features)
- SQLite store for exemplars
- OpenAI embeddings for semantic search
- Convention detection from history
- `--init` command to seed memory
- Few-shot prompt injection

## Installation

### Using uv (Recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/jay/commit-critic
cd commit-critic
uv sync
source .venv/bin/activate

# Or install directly
uv pip install commit-critic
```

### Using pip

```bash
pip install commit-critic
```

### Using Docker

```bash
# Build
docker build -t commit-critic .

# Run
docker run --rm -it \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -v $(pwd):/workspace:ro \
  commit-critic analyze
```

### From Source (Development)

```bash
git clone https://github.com/jay/commit-critic
cd commit-critic

# Using uv (recommended)
make dev
source .venv/bin/activate

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="sk-..."
```

Verify configuration:

```bash
critic config
```

## Deployment

### PyPI Distribution

```bash
# Build package
make build
# or: uv build

# Upload to PyPI
uv publish
# or: twine upload dist/*
```

### Docker Deployment

```bash
# Build production image
make docker-build

# Run analysis on a remote repo
docker run --rm -e OPENAI_API_KEY=$OPENAI_API_KEY \
  commit-critic analyze --url https://github.com/org/repo

# Using docker-compose
docker-compose run critic analyze
```

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Analyze commits
  run: |
    pip install commit-critic
    critic analyze -n 10
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## Development

```bash
# Install dev dependencies
make dev

# Run tests
make test

# Run linting
make lint

# Format code
make format

# Build package
make build
```
