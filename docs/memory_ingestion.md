# Memory Ingestion Architecture

This document outlines how Commit Critic ingests, stores, and retrieves memory to improve response quality over time.

## Overview

The memory system transforms Commit Critic from a stateless tool into a learning assistant that:
- Remembers your best commits as exemplars
- Learns your project's conventions
- Maintains context across sessions
- Provides increasingly personalized suggestions

## Memory Ingestion Process

### 1. Initial Seeding (`--init`)

```
┌─────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Git History ──► Score Commits ──► Filter (≥8) ──► Embed    │
│       │              │                  │             │      │
│       ▼              ▼                  ▼             ▼      │
│  [50 commits]   [GPT-5.2 rates]   [~10-15 pass]   [Store]   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Step-by-step flow:**

1. **Fetch History** - GitPython retrieves last N commits (default: 50)
2. **Score Each Commit** - GPT-5.2 rates message quality 1-10
3. **Filter Exemplars** - Only commits scoring 8+ are stored
4. **Generate Embeddings** - text-embedding-3-small creates 1536-dim vectors
5. **Store in SQLite** - Commit data + embedding persisted locally
6. **Detect Conventions** - Analyze patterns across all commits

### 2. Continuous Learning

Memory grows organically during normal usage:

```
┌─────────────────────────────────────────────────────────────┐
│                  CONTINUOUS INGESTION                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  --analyze mode:                                             │
│    └─► High-scoring commits (≥8) auto-saved as exemplars    │
│                                                              │
│  --write mode:                                               │
│    └─► User-accepted commits saved with implicit score 8+   │
│                                                              │
│  User feedback:                                              │
│    └─► Regenerated commits learn from rejection patterns    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Memory Storage Architecture

### SQLite Schema

```sql
-- Core exemplar storage
CREATE TABLE exemplars (
    id TEXT PRIMARY KEY,
    commit_hash TEXT,
    message TEXT NOT NULL,
    score INTEGER NOT NULL,
    project TEXT,
    repo_url TEXT,
    diff_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector embeddings (stored as BLOB)
CREATE TABLE embeddings (
    exemplar_id TEXT PRIMARY KEY REFERENCES exemplars(id),
    vector BLOB NOT NULL,  -- 1536 floats as bytes
    model TEXT DEFAULT 'text-embedding-3-small'
);

-- Project conventions
CREATE TABLE conventions (
    project TEXT PRIMARY KEY,
    style TEXT,           -- 'conventional', 'freeform', 'angular'
    uses_scope BOOLEAN,
    uses_tickets BOOLEAN,
    ticket_pattern TEXT,  -- e.g., 'JIRA-\d+', '#\d+'
    uses_emoji BOOLEAN,
    common_types TEXT,    -- JSON array: ["feat", "fix", "refactor"]
    updated_at TIMESTAMP
);

-- Agent conversation context
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    project TEXT,
    started_at TIMESTAMP,
    last_active TIMESTAMP
);

-- Chat messages for context
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    role TEXT,            -- 'user', 'assistant', 'system'
    content TEXT,
    created_at TIMESTAMP
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

## Types of Memory

### 1. Commit Exemplars

**What:** High-quality commit messages from your history
**Why:** Few-shot examples dramatically improve LLM output quality
**How used:** Retrieved via embedding similarity, injected into prompts

```python
@dataclass
class CommitExemplar:
    id: str
    commit_hash: str
    message: str
    score: int
    project: str
    diff_summary: str | None
    embedding: list[float]
    created_at: datetime
```

**Retrieval process:**
```
User's staged diff ──► Embed diff summary ──► Cosine similarity search
                                                      │
                                              Top 3 exemplars
                                                      │
                                                      ▼
                                            Inject into prompt
```

### 2. Project Conventions

**What:** Detected patterns from repository commit history
**Why:** Suggestions match existing project style
**How used:** Included in system prompt for both agents

```python
@dataclass
class ProjectConventions:
    style: Literal["conventional", "angular", "freeform"]
    uses_scope: bool           # feat(scope): message
    uses_tickets: bool         # References like JIRA-123
    ticket_pattern: str | None # Regex for ticket format
    uses_emoji: bool           # Emoji prefixes
    common_types: list[str]    # ["feat", "fix", "docs", ...]
```

**Detection algorithm:**
```python
def detect_conventions(commits: list[str]) -> ProjectConventions:
    # Count conventional commit patterns
    conventional_count = sum(1 for c in commits if re.match(r'^\w+(\(.+\))?:', c))

    # Check for scopes
    scope_count = sum(1 for c in commits if re.match(r'^\w+\(.+\):', c))

    # Detect ticket patterns
    ticket_patterns = [
        (r'[A-Z]+-\d+', 'jira'),      # JIRA-123
        (r'#\d+', 'github'),           # #123
        (r'\[\w+-\d+\]', 'bracketed'), # [PROJ-123]
    ]

    # Check emoji usage
    emoji_count = sum(1 for c in commits if has_emoji(c))

    return ProjectConventions(...)
```

### 3. Conversation Context

**What:** Recent interactions within a session
**Why:** Maintains coherence across multiple operations
**How used:** Sliding window of recent messages in prompt

```python
@dataclass
class ConversationContext:
    id: str
    project: str
    messages: list[Message]
    started_at: datetime

    def get_recent(self, n: int = 5) -> list[Message]:
        """Return last n messages for context injection."""
        return self.messages[-n:]
```

### 4. User Preferences

**What:** Explicit user settings and implicit learned preferences
**Why:** Personalization without repeated configuration
**How used:** Applied during generation and formatting

```python
@dataclass
class UserPreferences:
    # Explicit settings
    default_commit_style: str
    preferred_length: Literal["concise", "detailed"]
    include_body: bool

    # Learned preferences
    rejected_patterns: list[str]  # Patterns user often edits out
    accepted_types: dict[str, int]  # Type frequency from accepts
```

## How Memory Improves Response Quality

### 1. Few-Shot Learning with Exemplars

**Without memory:**
```
System: You are a commit message assistant.
User: Write a commit for this diff: [diff]
```
Generic output, may not match project style.

**With memory:**
```
System: You are a commit message assistant.

Here are examples of excellent commits from this project:
- "feat(auth): implement OAuth2 flow with refresh tokens"
- "fix(api): handle rate limiting with exponential backoff"
- "refactor(db): extract query builder into separate module"

User: Write a commit for this diff: [diff]
```
Output matches established patterns and quality bar.

### 2. Convention Awareness

**Without memory:**
```
Suggested: "Add user authentication feature"
```

**With detected conventions:**
```
Detected: conventional commits with scope, JIRA references
Suggested: "feat(auth): add user authentication flow

Implements OAuth2 login with session management.

JIRA-1234"
```

### 3. Semantic Retrieval

Embedding-based retrieval finds *relevant* exemplars, not just recent ones:

```
Staged changes: Modified error handling in payment module

Retrieved exemplars (by similarity):
1. "fix(payments): handle declined card errors gracefully" (0.89)
2. "fix(checkout): add retry logic for payment timeouts" (0.84)
3. "feat(billing): implement invoice error recovery" (0.79)

These domain-specific examples produce better suggestions than
generic "good commit" examples would.
```

### 4. Feedback Loop

User actions create implicit training signals:

| Action | Signal | Memory Update |
|--------|--------|---------------|
| Accept suggestion | Positive | Save as exemplar (score 8) |
| Edit then accept | Neutral | Save edited version |
| Regenerate | Negative | Note rejected pattern |
| Quit without using | Strong negative | Skip storage |

Over time, this shapes suggestions toward user preferences.

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
| File paths | Domain clustering |

### Similarity Search

```python
def find_similar_exemplars(
    query_embedding: list[float],
    top_k: int = 3,
    min_score: float = 0.7
) -> list[CommitExemplar]:
    """
    Cosine similarity search against stored embeddings.
    Returns top_k exemplars above minimum similarity threshold.
    """
    # Load all embeddings from SQLite
    exemplars = load_exemplars_with_embeddings()

    # Compute similarities
    similarities = [
        (e, cosine_similarity(query_embedding, e.embedding))
        for e in exemplars
    ]

    # Filter and sort
    filtered = [(e, s) for e, s in similarities if s >= min_score]
    filtered.sort(key=lambda x: x[1], reverse=True)

    return [e for e, _ in filtered[:top_k]]
```

## Memory Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                     MEMORY LIFECYCLE                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  CREATE                                                      │
│    └─► --init seeds from history                            │
│    └─► --analyze discovers new exemplars                    │
│    └─► --write saves accepted suggestions                   │
│                                                              │
│  READ                                                        │
│    └─► Retrieve exemplars for few-shot prompts              │
│    └─► Load conventions for style matching                  │
│    └─► Fetch conversation context                           │
│                                                              │
│  UPDATE                                                      │
│    └─► Re-score exemplars periodically                      │
│    └─► Refresh conventions on new analysis                  │
│    └─► Update preferences from feedback                     │
│                                                              │
│  DELETE                                                      │
│    └─► critic memory clear (full reset)                     │
│    └─► Auto-prune old/low-value exemplars                   │
│    └─► Expire stale conversation contexts                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Privacy Considerations

- All memory stored locally in `~/.commit-critic/`
- No commit data sent to external services except OpenAI for scoring/embedding
- Remote repo clones are temporary and cleaned up
- User can clear all memory with `critic memory clear`
- Config option to disable memory entirely: `critic config set memory_enabled false`
