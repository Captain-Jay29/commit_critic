"""OpenAI embedding utilities for the memory system."""

import numpy as np
from openai import OpenAI

from ..config import get_settings

# text-embedding-3-small produces 1536-dimensional vectors
EMBEDDING_DIMENSIONS = 1536


class EmbeddingGenerator:
    """Generate embeddings using OpenAI's text-embedding-3-small model."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.model = self.settings.embedding_model

    def generate(self, text: str) -> bytes:
        """
        Generate an embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding as bytes (1536-dim float32 array).
        """
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        embedding = response.data[0].embedding
        return self._to_bytes(embedding)

    def generate_batch(self, texts: list[str]) -> list[bytes]:
        """
        Generate embeddings for multiple texts in a single API call.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embeddings as bytes.
        """
        if not texts:
            return []

        # OpenAI allows batches up to 2048 inputs
        # For safety, we'll process in chunks of 100
        chunk_size = 100
        all_embeddings: list[bytes] = []

        for i in range(0, len(texts), chunk_size):
            chunk = texts[i : i + chunk_size]
            response = self.client.embeddings.create(
                model=self.model,
                input=chunk,
            )
            # Sort by index to maintain order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            for item in sorted_data:
                all_embeddings.append(self._to_bytes(item.embedding))

        return all_embeddings

    def _to_bytes(self, embedding: list[float]) -> bytes:
        """Convert embedding list to bytes."""
        return np.array(embedding, dtype=np.float32).tobytes()


def embedding_to_array(embedding_bytes: bytes) -> np.ndarray:
    """Convert embedding bytes back to numpy array."""
    return np.frombuffer(embedding_bytes, dtype=np.float32)


def cosine_similarity(a: bytes, b: bytes) -> float:
    """
    Calculate cosine similarity between two embeddings.

    Args:
        a: First embedding as bytes.
        b: Second embedding as bytes.

    Returns:
        Cosine similarity score between -1 and 1.
    """
    vec_a = embedding_to_array(a)
    vec_b = embedding_to_array(b)

    dot_product = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot_product / (norm_a * norm_b))


def format_commit_for_embedding(
    message: str,
    commit_type: str | None = None,
    scope: str | None = None,
    files_changed: list[str] | int | None = None,
) -> str:
    """
    Format a commit for embedding generation.

    Combines commit metadata into a text representation that captures
    semantic meaning for similarity search.

    Args:
        message: Commit message.
        commit_type: Type like "feat", "fix", etc.
        scope: Scope like "auth", "api", etc.
        files_changed: List of changed file paths or count.

    Returns:
        Formatted text for embedding.
    """
    parts = []

    # Add type and scope if available
    if commit_type:
        parts.append(f"Type: {commit_type}")
    if scope:
        parts.append(f"Scope: {scope}")

    # Add the main message
    parts.append(f"Message: {message}")

    # Add file context if available (just the first few)
    if files_changed and isinstance(files_changed, list):
        # Extract just filenames for context
        file_names = [f.split("/")[-1] for f in files_changed[:5]]
        parts.append(f"Files: {', '.join(file_names)}")

    return " | ".join(parts)


def format_diff_for_embedding(
    diff_text: str,
    files_changed: list[str],
    additions: int,
    deletions: int,
) -> str:
    """
    Format a diff for embedding generation (for writer mode).

    Creates a text representation of code changes for finding
    similar exemplars.

    Args:
        diff_text: The actual diff content.
        files_changed: List of changed file paths.
        additions: Number of lines added.
        deletions: Number of lines deleted.

    Returns:
        Formatted text for embedding.
    """
    parts = []

    # File context
    if files_changed:
        parts.append(f"Files changed: {', '.join(files_changed[:10])}")

    # Change magnitude
    parts.append(f"Changes: +{additions} -{deletions}")

    # Extract key information from diff
    # Look for function/class definitions, imports, etc.
    key_changes = _extract_key_changes(diff_text)
    if key_changes:
        parts.append(f"Key changes: {key_changes}")

    return " | ".join(parts)


def _extract_key_changes(diff_text: str) -> str:
    """Extract key semantic information from a diff."""
    key_items = []

    for line in diff_text.split("\n"):
        line = line.strip()
        # Skip diff metadata
        if line.startswith(("+++", "---", "@@", "diff --git")):
            continue

        # Look for added lines with important patterns
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:].strip()

            # Function/method definitions
            if content.startswith(("def ", "async def ", "function ", "const ", "class ")):
                # Extract just the name
                name = content.split("(")[0].split(" ")[-1]
                if name and name not in key_items:
                    key_items.append(f"added {name}")

            # Import statements
            elif content.startswith(("import ", "from ", "require(")):
                key_items.append("modified imports")

        # Look for removed lines
        elif line.startswith("-") and not line.startswith("---"):
            content = line[1:].strip()
            if content.startswith(("def ", "async def ", "function ", "const ", "class ")):
                name = content.split("(")[0].split(" ")[-1]
                if name:
                    key_items.append(f"removed {name}")

    # Deduplicate and limit
    seen = set()
    unique_items = []
    for item in key_items:
        if item not in seen and len(unique_items) < 10:
            seen.add(item)
            unique_items.append(item)

    return ", ".join(unique_items)
