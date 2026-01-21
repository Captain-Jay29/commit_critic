# Commit Critic: Project Specification

## Overview

Commit Critic is an AI-powered CLI tool that analyzes git commit messages, learns from your history, and helps write better ones. It uses GPT-5.2 for reasoning and text-embedding-3-small for memory-based personalization.

## Architecture

```
+-----------------------------------------------------------------+
|                      CLI Layer (Typer)                          |
|              init | analyze | write | memory                    |
+-----------------------------------------------------------------+
|                    Agent Layer (OpenAI)                         |
|  +------------------+    +------------------+                   |
|  | Analyzer Agent   |    | Writer Agent     |                   |
|  | (score commits)  |    | (suggest message)|                   |
|  +------------------+    +------------------+                   |
+-----------------------------------------------------------------+
|                    Memory System                                |
|  +-------------+  +--------------+  +-------------------+       |
|  | Repositories|  | Collaborators|  | Exemplars         |       |
|  | (DNA/style) |  | (profiles)   |  | (best commits)    |       |
|  +-------------+  +--------------+  +-------------------+       |
|  +-------------+  +--------------+                              |
|  | Antipatterns|  | Market Data  |                              |
|  | (roasts)    |  | (comparisons)|                              |
|  +-------------+  +--------------+                              |
+-----------------------------------------------------------------+
|                    Git Operations                               |
|  [Local Repo] [Remote URL Clone] [Diffs] [Commits]              |
+-----------------------------------------------------------------+
```

## Core Stack

- **Python 3.11+** with Typer + Rich
- **OpenAI SDK** (GPT-5.2 for reasoning + text-embedding-3-small for memory)
- **GitPython** for git operations
- **SQLite + embeddings** for memory
- **uv** for package management

## CLI Interface

```bash
# INIT MODE (seed memory)
critic init                              # Current repo, 100 commits
critic init --url https://github.com/org/repo  # Remote repo
critic init -n 200                       # More commits
critic init --no-roasts                  # Skip humorous roasts

# ANALYZE MODE (memory-aware)
critic analyze                           # Local repo, last 20 commits
critic analyze -n 50                     # Last 50 commits
critic analyze --url https://github.com/org/repo

# WRITE MODE (few-shot from exemplars)
critic write                             # Suggest for staged changes

# MEMORY MANAGEMENT
critic memory status                     # Show what's learned
critic memory clear                      # Clear memory

# UTILITIES
critic config                            # Show/set config
```

## Project Structure

```
commit_critic/
├── __init__.py
├── cli.py              # Typer CLI entry point
├── config.py           # Settings & API keys
├── exceptions.py       # Custom exceptions
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
│   ├── __init__.py     # Exports MemoryStore, Seeder
│   ├── store.py        # SQLite CRUD + embedding search
│   ├── seeder.py       # Orchestrates init command
│   ├── extractor.py    # Extract style, DNA, antipatterns
│   ├── profiler.py     # Build collaborator profiles
│   ├── embeddings.py   # OpenAI embedding utilities
│   ├── comparisons.py  # Market comparison feature
│   └── schemas.py      # Pydantic models
├── output/
│   ├── __init__.py
│   └── formatter.py    # Rich terminal output
├── docs/
│   ├── project_spec.md
│   └── memory_ingestion.md
├── tests/
│   └── ...
├── pyproject.toml
├── Makefile
├── Dockerfile
└── docker-compose.yml
```

## Implementation Phases

### Phase 1: Core CLI + Git (Completed)
- [x] Typer CLI skeleton with `analyze` and `write` commands
- [x] Git operations: fetch commits, get staged diff
- [x] Remote URL cloning (shallow clone to temp dir)
- [x] Basic GPT-5.2 integration for scoring/writing
- [x] Rich terminal output formatting

### Phase 2: Polish & Testing
- [ ] Comprehensive error handling
- [ ] Unit tests for core modules
- [ ] Integration tests with mock OpenAI
- [ ] CI/CD pipeline setup

### Phase 3: Memory System (Current)

The memory system transforms Commit Critic from a stateless tool into a learning assistant that provides personalized, context-aware commit analysis.

#### What Gets Learned

| Category | Data Extracted | Used For |
|----------|---------------|----------|
| **Commit Style** | Conventional commits, emoji, tickets, scopes | Match project conventions in suggestions |
| **Exemplars** | High-scoring commits (>=8) with embeddings | Few-shot examples for writer |
| **Collaborators** | Who works where, avg scores, patterns | Personalized feedback, roasts |
| **Codebase DNA** | Languages, frameworks, project type | Context-aware analysis |
| **Market Position** | Comparison to similar popular repos | Benchmarking, tips |

#### Implementation Steps

**Step 1: Database Foundation**
- [ ] `memory/schemas.py` - Pydantic models for all data types
- [ ] `memory/store.py` - SQLite operations (init, CRUD, queries)
- [ ] `memory/embeddings.py` - OpenAI embedding generation + cosine similarity

**Step 2: Seeding Core**
- [ ] `memory/extractor.py` - Extract style patterns, DNA, antipatterns
- [ ] `memory/seeder.py` - Main orchestration with progress callbacks
- [ ] `cli.py` - Add `init` command with real-time Rich output

**Step 3: Wow Features**
- [ ] `memory/profiler.py` - Build collaborator profiles with area detection
- [ ] `memory/comparisons.py` - Fetch and compare to reference repos
- [ ] `output/formatter.py` - New display methods for all wow features

**Step 4: Integration**
- [ ] `agents/analyzer.py` - Memory-aware personalized feedback
- [ ] `agents/writer.py` - Few-shot examples from exemplars
- [ ] `agents/prompts.py` - Context-aware prompt templates

**Step 5: Polish**
- [ ] `cli.py` - Add `memory status` and `memory clear` commands
- [ ] Tests for memory module
- [ ] Handle edge cases (empty repos, no exemplars, API failures)

#### Database Schema

```sql
-- Repository metadata and learned patterns
CREATE TABLE repositories (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE,
    name TEXT NOT NULL,
    seeded_at TIMESTAMP,

    -- Codebase DNA
    primary_language TEXT,
    languages_json TEXT,          -- {"Python": 0.85, "YAML": 0.10}
    frameworks_json TEXT,         -- ["Typer", "OpenAI", "Rich"]
    project_type TEXT,            -- "cli-tool", "web-app", "library"

    -- Commit style
    style_pattern TEXT,           -- "conventional", "emoji", "freeform"
    uses_scopes BOOLEAN,
    common_scopes_json TEXT,      -- ["auth", "api", "docs"]
    ticket_pattern TEXT,          -- "JIRA-\d+" or null

    -- Market position
    comparison_repos_json TEXT,
    industry_percentile REAL
);

-- Contributor profiles
CREATE TABLE collaborators (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repositories(id),
    name TEXT NOT NULL,
    email TEXT,

    commit_count INTEGER,
    avg_score REAL,
    primary_areas_json TEXT,      -- ["backend/auth", "api/"]
    area_summary TEXT,            -- AI-generated description

    -- Roast material
    roast_patterns_json TEXT,     -- ["12 WIP commits", "loves 'fix'"]

    UNIQUE(repo_id, name)
);

-- High-quality commit exemplars
CREATE TABLE exemplars (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repositories(id),
    collaborator_id INTEGER REFERENCES collaborators(id),

    commit_hash TEXT NOT NULL,
    message TEXT NOT NULL,
    score INTEGER CHECK(score >= 8),
    commit_type TEXT,
    scope TEXT,

    -- For similarity search
    embedding BLOB,               -- 1536-dim vector as bytes

    UNIQUE(repo_id, commit_hash)
);

-- Bad patterns for roasts
CREATE TABLE antipatterns (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repositories(id),
    collaborator_id INTEGER REFERENCES collaborators(id),

    pattern_type TEXT,            -- "wip-chain", "one-word", "vague"
    example_message TEXT,
    frequency INTEGER
);
```

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
For `write` mode, understand the CODE:
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
├─ [1/50] "fixed bug" -> 2/10
├─ [2/50] "feat(auth): add OAuth" -> 8/10
└─ Complete!
```

### 6. Collaborator Insights
```
TEAM INSIGHTS
+----------------------------------------------------------------+
| Alice Chen (47 commits)                                        |
|   Primary: backend/auth, api/users                             |
|   Style: 8.2 avg | Consistent                                  |
|   "Owns authentication and user management"                    |
|                                                                |
| Bob Smith (32 commits)                                         |
|   Primary: frontend/components                                 |
|   Style: 6.1 avg | Inconsistent                                |
|   "Frontend work, needs better messages"                       |
+----------------------------------------------------------------+
```

### 7. Subtle Roasts
```
HALL OF SHAME (All in Good Fun)
+----------------------------------------------------------------+
| Bob Smith:                                                     |
|   - 12 'WIP' commits in a row on Dec 15th                      |
|   - Champion of one-word commits (23 total)                    |
|   - Once wrote: "fixed the thing with the stuff"               |
|                                                                |
| Charlie Dev:                                                   |
|   - 8 commits called just "fix" - debugging Olympics gold      |
+----------------------------------------------------------------+
```

### 8. Market Comparison
```
MARKET COMPARISON
+----------------------------------------------------------------+
| Your repo vs. similar Python projects:                         |
|                                                                |
| Your average: 6.8/10                                           |
| [============--------] Better than 62%                         |
|                                                                |
| References:                                                    |
|   fastapi:  8.4/10 | django: 8.1/10 | flask: 7.9/10            |
|                                                                |
| Tip: FastAPI uses scopes like feat(router): - try it!          |
+----------------------------------------------------------------+
```

### 9. Codebase DNA
```
CODEBASE DNA
+----------------------------------------------------------------+
| Project: commit-critic                                         |
| Type: CLI Tool                                                 |
|                                                                |
| Languages:                                                     |
|   Python [====================----] 85%                        |
|   YAML   [==----------------------] 10%                        |
|                                                                |
| Stack: Python 3.11+ | Typer | OpenAI | GitPython               |
|                                                                |
| Summary: "CLI with AI agents for git commit analysis"          |
+----------------------------------------------------------------+
```

## Sample Output

### Init Mode
```
$ critic init --url https://github.com/tiangolo/fastapi -n 100

+------------------------------------------------------------------+
|  COMMIT CRITIC - LEARNING MODE                                   |
+------------------------------------------------------------------+

[1/8] Cloning repository...
      Done - Cloned tiangolo/fastapi

[2/8] Extracting commits...
      Done - Extracted 100 commits from 15 contributors

[3/8] Analyzing codebase DNA...
      - Primary: Python (94%)
      - Stack: FastAPI, Pydantic, Starlette
      - Type: Web Framework
      Done

[4/8] Detecting commit style...
      - Pattern: Conventional Commits
      - Scopes: docs, internal, feat, fix
      - No emoji
      Done - Style: conventional + scopes

[5/8] Analyzing commits...
      [================----------] 67/100
      Done - Average: 8.4/10

[6/8] Extracting exemplars...
      Done - Found 67 exemplary commits (score >= 8)

[7/8] Profiling contributors...
      - @tiangolo: 45 commits, 8.9 avg
      - @Kludex: 23 commits, 8.1 avg
      - @euri10: 12 commits, 7.8 avg
      Done - Profiled 15 contributors

[8/8] Market comparison...
      - vs flask: +0.5 better
      - vs django: -0.3 behind
      Done - Percentile: Top 15%

+------------------------------------------------------------------+
|  MEMORY SEEDED                                                   |
+------------------------------------------------------------------+

DNA: Python CLI | FastAPI + Pydantic | Conventional commits
Quality: 8.4/10 avg | 67 exemplars saved
Team: 15 contributors profiled
Market: Top 15% of Python web projects

HALL OF SHAME
   No roast material - this team is too good!

Ready! Try: critic analyze
```

### Analyze Mode
```
$ critic analyze --url https://github.com/steel-dev/steel-browser

Cloning repository...
Analyzing last 20 commits...

COMMITS THAT NEED WORK

Commit: "fixed bug" (abc123) - Bob Smith
Score: 2/10
Bob, this is your 15th vague commit.
Issue: Too vague - which bug? What was the fix?
Better: "fix(auth): resolve token expiration handling"

WELL-WRITTEN COMMITS

Commit: "feat(browser): add stealth mode for automation" (def456)
Score: 9/10
Why: Clear scope, specific action, states purpose
Saved as exemplar

STATS
Average: 6.2/10
Vague commits: 4 (20%)
One-word commits: 1 (5%)
```

### Write Mode
```
$ critic write

Analyzing staged changes...
   3 files changed (+47 -12 lines)

Understanding changes...
   • auth/token.py: Added error handling
   • auth/refresh.py: New retry logic
   • tests/test_auth.py: Edge case coverage

Using 3 similar exemplars from your history...

Suggested commit:
fix(auth): handle token expiration gracefully

- Add specific error handling for expired tokens
- Implement retry logic for refresh failures
- Add test coverage for edge cases

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

1. `critic init` on local repo - verify all phases complete
2. `critic init --url https://github.com/tiangolo/fastapi` - verify remote works
3. `critic memory status` - verify data was saved
4. `critic analyze` - verify personalized feedback appears
5. `critic write` - verify exemplars influence suggestions
6. `critic init --no-roasts` - verify flag works
7. Test on repo with bad commits - verify roasts appear

## Critical Files to Modify

1. **`memory/store.py`** - Core SQLite database operations with embedding storage
2. **`memory/seeder.py`** - Main orchestration for `init` command
3. **`cli.py`** - Add `init`, `memory` commands; integrate with analyze/write
4. **`agents/prompts.py`** - Context-aware and few-shot prompts
5. **`output/formatter.py`** - Display methods for seeding progress and wow features

## Related Documentation

- [Memory Ingestion Architecture](memory_ingestion.md) - Detailed memory system design
