# Memory Ingestion Architecture

This document outlines how Commit Critic ingests, stores, and retrieves memory to provide personalized, context-aware commit analysis and suggestions.

## Overview

The memory system transforms Commit Critic from a stateless tool into a learning assistant that:
- Learns your project's commit conventions and codebase DNA
- Remembers your best commits as exemplars for few-shot learning
- Profiles contributors for personalized feedback (and roasts)
- Compares your repo to similar projects in the market
- Provides increasingly personalized suggestions over time

## What Gets Learned

| Category | Data Extracted | Used For |
|----------|---------------|----------|
| **Commit Style** | Conventional commits, emoji, tickets, scopes | Match project conventions in suggestions |
| **Exemplars** | High-scoring commits (>=8) with embeddings | Few-shot examples for writer |
| **Collaborators** | Who works where, avg scores, patterns | Personalized feedback, roasts |
| **Codebase DNA** | Languages, frameworks, project type | Context-aware analysis |
| **Market Position** | Comparison to similar popular repos | Benchmarking, tips |

## Memory Ingestion Pipeline

### `critic init` Command Flow

```
+-----------------------------------------------------------------+
|                    INGESTION PIPELINE                            |
+-----------------------------------------------------------------+

[1/8] Clone Repository
      ├─ Local: Use existing repo path
      └─ Remote: Shallow clone to temp directory

[2/8] Extract Commits
      ├─ Fetch last N commits (default: 100)
      └─ Extract: hash, message, author, date, files changed

[3/8] Analyze Codebase DNA
      ├─ Detect primary language from file extensions
      ├─ Identify frameworks from imports/configs
      └─ Classify project type (cli, web-app, library, etc.)

[4/8] Detect Commit Style
      ├─ Check for conventional commits pattern
      ├─ Extract common scopes
      ├─ Detect ticket patterns (JIRA, GitHub issues)
      └─ Check emoji usage

[5/8] Score Commits
      ├─ GPT-5.2 rates each commit 1-10
      ├─ Batch processing with progress bar
      └─ Calculate repository average

[6/8] Extract Exemplars
      ├─ Filter commits with score >= 8
      ├─ Generate embeddings with text-embedding-3-small
      └─ Store for few-shot retrieval

[7/8] Profile Contributors
      ├─ Aggregate commits per author
      ├─ Calculate average scores
      ├─ Detect primary areas (file paths)
      └─ Extract roast-worthy antipatterns

[8/8] Market Comparison
      ├─ Identify similar reference repos
      ├─ Fetch/compare commit quality
      └─ Calculate industry percentile
```

### Continuous Learning

Memory grows organically during normal usage:

| Mode | Learning Action |
|------|----------------|
| `analyze` | High-scoring commits (>=8) auto-saved as exemplars |
| `write` | User-accepted commits saved with implicit score 8+ |
| Feedback | Regenerated commits learn from rejection patterns |

## Database Schema

### SQLite Tables

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
    comparison_repos_json TEXT,   -- ["flask", "django", "fastapi"]
    industry_percentile REAL      -- 0.0 to 1.0
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
    area_summary TEXT,            -- AI-generated: "Owns authentication"

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
    commit_type TEXT,             -- "feat", "fix", "refactor", etc.
    scope TEXT,                   -- "auth", "api", etc.

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
    example_message TEXT,         -- "fixed the thing with the stuff"
    frequency INTEGER             -- How many times this pattern occurred
);
```

### File Location

```
~/.commit-critic/
├── memory.db           # SQLite database
├── config.json         # User preferences
└── cache/
    └── repos/          # Cached shallow clones
```

## Pydantic Models

```python
from pydantic import BaseModel
from datetime import datetime

class Repository(BaseModel):
    id: int | None = None
    url: str
    name: str
    seeded_at: datetime | None = None

    # Codebase DNA
    primary_language: str | None = None
    languages: dict[str, float] = {}      # {"Python": 0.85}
    frameworks: list[str] = []            # ["Typer", "OpenAI"]
    project_type: str | None = None       # "cli-tool"

    # Commit style
    style_pattern: str = "freeform"       # "conventional", "emoji"
    uses_scopes: bool = False
    common_scopes: list[str] = []         # ["auth", "api"]
    ticket_pattern: str | None = None     # "JIRA-\d+"

    # Market position
    comparison_repos: list[str] = []
    industry_percentile: float | None = None

class Collaborator(BaseModel):
    id: int | None = None
    repo_id: int
    name: str
    email: str | None = None

    commit_count: int = 0
    avg_score: float = 0.0
    primary_areas: list[str] = []         # ["backend/auth"]
    area_summary: str | None = None       # "Owns authentication"

    roast_patterns: list[str] = []        # ["12 WIP commits"]

class Exemplar(BaseModel):
    id: int | None = None
    repo_id: int
    collaborator_id: int | None = None

    commit_hash: str
    message: str
    score: int                            # 8-10
    commit_type: str | None = None        # "feat", "fix"
    scope: str | None = None              # "auth"

    embedding: list[float] | None = None  # 1536-dim vector

class Antipattern(BaseModel):
    id: int | None = None
    repo_id: int
    collaborator_id: int | None = None

    pattern_type: str                     # "wip-chain", "one-word"
    example_message: str
    frequency: int = 1
```

## Extraction Logic

### Style Detection

```python
def detect_commit_style(commits: list[str]) -> dict:
    """Analyze commit messages to detect project conventions."""

    # Check for conventional commits: type(scope): message
    conventional_pattern = r'^(feat|fix|docs|style|refactor|test|chore)(\(.+\))?:'
    conventional_count = sum(1 for c in commits if re.match(conventional_pattern, c))

    # Check for scopes
    scope_pattern = r'^\w+\(([^)]+)\):'
    scopes = [m.group(1) for c in commits if (m := re.match(scope_pattern, c))]

    # Detect ticket patterns
    ticket_patterns = [
        (r'[A-Z]+-\d+', 'jira'),       # JIRA-123
        (r'#\d+', 'github'),            # #123
        (r'\[\w+-\d+\]', 'bracketed'),  # [PROJ-123]
    ]
    ticket_pattern = None
    for pattern, name in ticket_patterns:
        if sum(1 for c in commits if re.search(pattern, c)) > len(commits) * 0.1:
            ticket_pattern = pattern
            break

    # Check emoji usage
    emoji_count = sum(1 for c in commits if has_emoji(c))

    return {
        "style_pattern": "conventional" if conventional_count > len(commits) * 0.5 else "freeform",
        "uses_scopes": len(scopes) > len(commits) * 0.3,
        "common_scopes": list(set(scopes))[:10],
        "ticket_pattern": ticket_pattern,
        "uses_emoji": emoji_count > len(commits) * 0.2,
    }
```

### DNA Detection

```python
def detect_codebase_dna(repo_path: str) -> dict:
    """Analyze repository to determine codebase characteristics."""

    # Count files by extension
    extensions = Counter()
    for root, dirs, files in os.walk(repo_path):
        # Skip hidden and vendor directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '.venv']]
        for f in files:
            ext = Path(f).suffix.lower()
            if ext:
                extensions[ext] += 1

    # Map extensions to languages
    ext_to_lang = {'.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', ...}
    total = sum(extensions.values())
    languages = {ext_to_lang.get(ext, ext): count/total for ext, count in extensions.most_common(5)}

    # Detect frameworks from config files and imports
    frameworks = detect_frameworks(repo_path)

    # Classify project type
    project_type = classify_project_type(repo_path, languages, frameworks)

    return {
        "primary_language": max(languages, key=languages.get) if languages else None,
        "languages": languages,
        "frameworks": frameworks,
        "project_type": project_type,
    }
```

### Antipattern Detection

```python
def detect_antipatterns(commits: list[dict], collaborators: dict) -> list[Antipattern]:
    """Find roast-worthy commit patterns for each collaborator."""

    antipatterns = []

    for name, author_commits in collaborators.items():
        messages = [c["message"] for c in author_commits]

        # WIP chains: multiple WIP commits in a row
        wip_chain = find_wip_chains(author_commits)
        if wip_chain:
            antipatterns.append(Antipattern(
                pattern_type="wip-chain",
                example_message=f"{wip_chain['count']} 'WIP' commits in a row on {wip_chain['date']}",
                frequency=wip_chain['count']
            ))

        # One-word commits
        one_word = [m for m in messages if len(m.split()) == 1]
        if len(one_word) >= 3:
            antipatterns.append(Antipattern(
                pattern_type="one-word",
                example_message=f"Champion of one-word commits ({len(one_word)} total)",
                frequency=len(one_word)
            ))

        # Vague commits
        vague_patterns = ["fix", "update", "change", "stuff", "thing", "misc"]
        vague = [m for m in messages if any(v in m.lower() for v in vague_patterns) and len(m) < 20]
        if vague:
            worst = max(vague, key=lambda m: sum(v in m.lower() for v in vague_patterns))
            antipatterns.append(Antipattern(
                pattern_type="vague",
                example_message=f'Once wrote: "{worst}"',
                frequency=len(vague)
            ))

    return antipatterns
```

## Embedding Strategy

### Model Choice: text-embedding-3-small

- **Dimensions:** 1536
- **Cost:** $0.00002 / 1K tokens
- **Quality:** Sufficient for commit message similarity
- **Speed:** Fast enough for real-time retrieval

### What Gets Embedded

| Content | Purpose |
|---------|---------|
| Commit message | Find similar exemplars |
| Diff summary | Match by change type |

### Embedding Generation

```python
async def generate_embedding(text: str) -> list[float]:
    """Generate embedding using OpenAI's text-embedding-3-small."""
    response = await openai.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding
```

### Similarity Search

```python
def find_similar_exemplars(
    query_embedding: list[float],
    exemplars: list[Exemplar],
    top_k: int = 3,
    min_similarity: float = 0.7
) -> list[Exemplar]:
    """Find most similar exemplars using cosine similarity."""

    def cosine_similarity(a: list[float], b: list[float]) -> float:
        a, b = np.array(a), np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    scored = [
        (e, cosine_similarity(query_embedding, e.embedding))
        for e in exemplars
        if e.embedding
    ]

    filtered = [(e, s) for e, s in scored if s >= min_similarity]
    filtered.sort(key=lambda x: x[1], reverse=True)

    return [e for e, _ in filtered[:top_k]]
```

## Integration with Commands

### Enhanced `analyze`

When memory exists, the analyzer provides personalized feedback:

```python
def analyze_with_memory(commit: Commit, repo: Repository, author: Collaborator) -> Analysis:
    # Include repo's commit style conventions
    conventions = f"This project uses {repo.style_pattern} commits"
    if repo.uses_scopes:
        conventions += f" with scopes: {', '.join(repo.common_scopes)}"

    # Reference author's history
    history = f"{author.name}'s average: {author.avg_score:.1f}/10 over {author.commit_count} commits"

    # Check for repeat offenses
    if author.roast_patterns:
        roast = random.choice(author.roast_patterns)
    else:
        roast = None

    # Generate personalized feedback
    return generate_analysis(commit, conventions, history, roast)
```

**Example personalized feedback:**
```
Bob, we've talked about this. This is your 15th "stuff" commit.
Your team uses conventional commits like "fix(auth): description"
Your average: 5.2 -> This commit: 2/10 (trending down)
```

### Enhanced `write`

When memory exists, the writer uses few-shot examples:

```python
async def write_with_memory(diff: str, repo: Repository) -> str:
    # Embed the diff summary
    diff_summary = summarize_diff(diff)
    query_embedding = await generate_embedding(diff_summary)

    # Find similar exemplars
    exemplars = find_similar_exemplars(query_embedding, repo.exemplars, top_k=3)

    # Build few-shot prompt
    examples = "\n".join([
        f"Example {i+1}: {e.message} (Score: {e.score}/10)"
        for i, e in enumerate(exemplars)
    ])

    # Include conventions
    conventions = f"Project style: {repo.style_pattern}"
    if repo.uses_scopes:
        conventions += f" with scopes like: {', '.join(repo.common_scopes[:3])}"

    # Generate with context
    return await generate_commit_message(diff, examples, conventions)
```

## Market Comparison

### Reference Repository Selection

For each primary language, we maintain a list of well-known repos to compare against:

```python
REFERENCE_REPOS = {
    "Python": ["tiangolo/fastapi", "pallets/flask", "django/django"],
    "JavaScript": ["facebook/react", "vuejs/vue", "angular/angular"],
    "TypeScript": ["microsoft/vscode", "microsoft/TypeScript"],
    "Go": ["kubernetes/kubernetes", "golang/go"],
    "Rust": ["rust-lang/rust", "tauri-apps/tauri"],
}
```

### Comparison Process

```python
async def compare_to_market(repo: Repository, avg_score: float) -> dict:
    """Compare repository to similar well-known projects."""

    # Get reference repos for this language
    refs = REFERENCE_REPOS.get(repo.primary_language, [])[:3]

    # Fetch cached scores or analyze samples
    ref_scores = {}
    for ref in refs:
        ref_scores[ref] = await get_or_fetch_repo_score(ref)

    # Calculate percentile
    all_scores = list(ref_scores.values()) + [avg_score]
    percentile = sum(1 for s in all_scores if s <= avg_score) / len(all_scores)

    return {
        "comparison_repos": refs,
        "reference_scores": ref_scores,
        "industry_percentile": percentile,
    }
```

## CLI Output Examples

### Init Command Progress

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

### Memory Status

```
$ critic memory status

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
+----------------------------------------------------------------+

COMMIT STYLE
+----------------------------------------------------------------+
| Pattern: Conventional Commits                                  |
| Scopes: auth, api, docs, tests                                 |
| Tickets: None detected                                         |
+----------------------------------------------------------------+

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

HALL OF SHAME (All in Good Fun)
+----------------------------------------------------------------+
| Bob Smith:                                                     |
|   - 12 'WIP' commits in a row on Dec 15th                      |
|   - Champion of one-word commits (23 total)                    |
|   - Once wrote: "fixed the thing with the stuff"               |
+----------------------------------------------------------------+

EXEMPLARS: 45 stored | Last updated: 2 hours ago
```

## Privacy Considerations

- All memory stored locally in `~/.commit-critic/`
- No commit data sent to external services except OpenAI for scoring/embedding
- Remote repo clones are temporary and cleaned up
- User can clear all memory with `critic memory clear`
- Config option to disable memory entirely
- `--no-roasts` flag to skip humorous content

## Memory Lifecycle

```
CREATE
  └─> critic init seeds from history
  └─> critic analyze discovers new exemplars
  └─> critic write saves accepted suggestions

READ
  └─> Retrieve exemplars for few-shot prompts
  └─> Load conventions for style matching
  └─> Fetch collaborator context for personalization

UPDATE
  └─> Re-score exemplars periodically
  └─> Refresh conventions on new analysis
  └─> Update preferences from feedback

DELETE
  └─> critic memory clear (full reset)
  └─> Auto-prune old/low-value exemplars
```
