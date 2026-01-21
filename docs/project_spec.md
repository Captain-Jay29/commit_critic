# Commit Critic: Project Specification

## Overview

Commit Critic is an AI-powered CLI tool that analyzes git commit messages and helps write better ones. It uses GPT-5.2 for reasoning and text-embedding-3-small for memory-based personalization.

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

## Core Stack

- **Python 3.11+** with Typer + Rich
- **OpenAI SDK** (GPT-5.2 for reasoning + text-embedding-3-small for memory)
- **GitPython** for git operations
- **SQLite + embeddings** for memory
- **uv** for package management

## CLI Interface

```bash
# ANALYZE MODE
critic analyze                      # Local repo, last 20 commits
critic analyze -n 50                # Last 50 commits
critic analyze --url https://github.com/org/repo

# WRITE MODE
critic write                        # Suggest for staged changes

# INIT MODE (seed memory)
critic --init                       # Scan current repo
critic --init --url https://github.com/org/repo
critic --init -n 100                # Scan last 100 commits

# UTILITIES
critic config                       # Show/set config
critic memory show                  # Show stored exemplars
critic memory clear                 # Clear memory
```

## Project Structure

```
commit_critic/
├── __init__.py
├── cli.py              # Typer CLI entry point
├── config.py           # Settings & API keys
├── agents/
│   ├── __init__.py
│   ├── analyzer.py     # Commit scoring agent
│   ├── writer.py       # Message suggestion agent
│   └── prompts.py      # Prompt templates
├── vcs/
│   ├── __init__.py
│   ├── operations.py   # GitPython: commits, diff
│   └── remote.py       # URL cloning logic
├── memory/
│   ├── __init__.py
│   ├── store.py        # SQLite + embeddings
│   └── conventions.py  # Project style detection
├── output/
│   ├── __init__.py
│   └── formatter.py    # Rich terminal output
├── docs/
│   ├── README.md
│   ├── project_spec.md
│   └── memory_ingestion.md
├── pyproject.toml
├── Makefile
├── Dockerfile
└── docker-compose.yml
```

## Implementation Phases

> **Note:** Build core functionality first, then add memory features.

### Phase 1: Core CLI + Git ✅
- [x] Typer CLI skeleton with `--analyze` and `--write` flags
- [x] Git operations: fetch commits, get staged diff
- [x] Remote URL cloning (shallow clone to temp dir)
- [x] Basic GPT-5.2 integration for scoring/writing
- [x] Rich terminal output formatting

### Phase 2: Polish & Testing
- [ ] Comprehensive error handling
- [ ] Unit tests for core modules
- [ ] Integration tests with mock OpenAI
- [ ] CI/CD pipeline setup

### Phase 3: Memory System (Innovative Features)
- [ ] SQLite store for exemplars
- [ ] OpenAI embeddings for semantic search
- [ ] Convention detection from history
- [ ] `--init` command to seed memory
- [ ] Few-shot prompt injection

## Innovative Features

### 1. Commit Style Memory
Learn from user's OWN best commits:
- Store high-scoring commits as exemplars (score >= 8)
- Embed commits with text-embedding-3-small
- Inject similar exemplars as few-shot examples
- "Based on YOUR best commits, here's how to improve..."

### 2. Project Convention Detection
Auto-detect project's commit style from recent history:
- Conventional commits? (feat/fix/chore)
- Ticket references? (JIRA-123, #issue)
- Emoji usage?
- Adapt suggestions to match project style

### 3. Diff Intelligence
For `--write` mode, understand the CODE:
- Detect change type: refactor, bugfix, feature, test
- Identify affected modules/files
- Estimate complexity
- Generate message FROM the actual diff

### 4. Remote URL Support
Clone and analyze any accessible Git URL:
- GitHub, GitLab, Bitbucket URLs
- Shallow clone for speed (--depth 50)
- Temp directory cleanup
- Works with public repos

### 5. Real-time Streaming
Progress feedback during analysis:
```
Analyzing 50 commits...
├─ [1/50] "fixed bug" → 2/10 💩
├─ [2/50] "feat(auth): add OAuth" → 8/10 ✨
└─ Complete!
```

## Sample Output

### Analyze Mode
```
$ critic analyze --url https://github.com/steel-dev/steel-browser

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
💾 Saved as exemplar

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 STATS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Average: 6.2/10
Vague commits: 4 (20%)
One-word commits: 1 (5%)
```

### Write Mode
```
$ critic write

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

## Dependencies

```toml
dependencies = [
    "typer>=0.9.0,<1.0.0",
    "rich>=13.0.0,<14.0.0",
    "gitpython>=3.1.0,<4.0.0",
    "openai>=1.0.0,<2.0.0",
    "pydantic>=2.0.0,<3.0.0",
    "numpy>=1.24.0,<3.0.0",
]
```

## Environment Variables

```bash
OPENAI_API_KEY          # Required: OpenAI API key
OPENAI_MODEL            # Optional: Override model (default: gpt-5.2)
OPENAI_EMBEDDING_MODEL  # Optional: Override embedding model
COMMIT_CRITIC_DATA_DIR  # Optional: Custom data directory
```

## Verification Checklist

1. `critic analyze` on a local test repo
2. `critic analyze --url https://github.com/steel-dev/steel-browser`
3. `critic write` with staged changes
4. Verify exemplars saved and recalled (Phase 3)
5. Test on repos with different conventions (Phase 3)

## Related Documentation

- [Memory Ingestion Architecture](memory_ingestion.md) - Detailed memory system design
