"""Global store — manages C:\\AgentMemory\\ (SQLite + FTS5 + human-editable markdown).

Dual-write strategy: every write goes to both markdown (human-editable) and SQLite (searchable).
Reads prefer markdown for display, searches use SQLite FTS5 for speed.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Default global store root — can be overridden via AGENT_MEMORY_ROOT env var
def _get_default_root() -> Path:
    if "AGENT_MEMORY_ROOT" in os.environ:
        return Path(os.environ["AGENT_MEMORY_ROOT"])
    if os.name == "nt":
        return Path(r"C:\.agent-memory")
    return Path.home() / ".agent-memory"

GLOBAL_ROOT = _get_default_root()

# All known global markdown stores
GLOBAL_STORES = ("preferences", "arch_patterns", "tech_stack")

# SQLite DB path
DB_PATH = GLOBAL_ROOT / "global.db"


def _ensure_dirs() -> None:
    """Create the global store directory structure if it doesn't exist."""
    GLOBAL_ROOT.mkdir(parents=True, exist_ok=True)
    (GLOBAL_ROOT / "agent_settings").mkdir(exist_ok=True)
    (GLOBAL_ROOT / "error_index").mkdir(exist_ok=True)


def _get_db() -> sqlite3.Connection:
    """Get a connection to the global SQLite database, creating schema if needed."""
    _ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Core memories table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL DEFAULT 'global',
            store TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # FTS5 virtual table for full-text search on memories
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content, store, metadata_json,
            content=memories,
            content_rowid=id
        )
    """)

    # Triggers to keep FTS index in sync
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, store, metadata_json)
            VALUES (new.id, new.content, new.store, new.metadata_json);
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, store, metadata_json)
            VALUES ('delete', old.id, old.content, old.store, old.metadata_json);
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, store, metadata_json)
            VALUES ('delete', old.id, old.content, old.store, old.metadata_json);
            INSERT INTO memories_fts(rowid, content, store, metadata_json)
            VALUES (new.id, new.content, new.store, new.metadata_json);
        END
    """)

    conn.commit()
    return conn


# ──────────────────────────────────────────────
#  Markdown read/write
# ──────────────────────────────────────────────

def _md_path(store: str) -> Path:
    """Get the markdown file path for a global store."""
    return GLOBAL_ROOT / f"{store}.md"


def read_store(store: str) -> str:
    """Read a global markdown store. Returns empty string if file doesn't exist."""
    if store not in GLOBAL_STORES:
        raise ValueError(f"Unknown global store: {store}. Valid: {', '.join(GLOBAL_STORES)}")
    path = _md_path(store)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_store(store: str, content: str, mode: str = "append") -> str:
    """Write to a global markdown store and mirror to SQLite.

    Args:
        store: One of 'preferences', 'arch_patterns', 'tech_stack'
        content: The content to write (markdown)
        mode: 'append' to add to existing, 'replace' to overwrite

    Returns:
        Confirmation message.
    """
    if store not in GLOBAL_STORES:
        raise ValueError(f"Unknown global store: {store}. Valid: {', '.join(GLOBAL_STORES)}")

    _ensure_dirs()
    path = _md_path(store)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if mode == "append":
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        entry = f"\n\n---\n_Added: {now}_\n\n{content}"
        path.write_text(existing + entry, encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")

    # Mirror to SQLite
    _index_to_db(store, content)

    return f"✓ Saved to global/{store}.md ({mode})"


def _index_to_db(store: str, content: str, metadata: dict[str, Any] | None = None) -> None:
    """Index content into the SQLite memories table."""
    now = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(metadata or {})

    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO memories (scope, store, content, metadata_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("global", store, content, meta_json, now, now),
        )
        conn.commit()
    finally:
        conn.close()


# ──────────────────────────────────────────────
#  Search (SQLite FTS5)
# ──────────────────────────────────────────────

def search(query: str, store: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Full-text search across global memories using SQLite FTS5.

    Args:
        query: Search query (supports FTS5 syntax: AND, OR, NOT, "phrases")
        store: Optional filter to a specific store
        limit: Max results

    Returns:
        List of dicts with keys: store, content, metadata, rank, created_at
    """
    conn = _get_db()
    try:
        # Sanitize query for FTS5 — wrap each term in quotes for safety
        safe_query = " ".join(f'"{term}"' for term in query.split() if term.strip())
        if not safe_query:
            return []

        if store:
            rows = conn.execute(
                """SELECT m.store, m.content, m.metadata_json, m.created_at,
                          rank AS relevance
                   FROM memories_fts f
                   JOIN memories m ON f.rowid = m.id
                   WHERE memories_fts MATCH ? AND m.store = ?
                   ORDER BY rank
                   LIMIT ?""",
                (safe_query, store, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT m.store, m.content, m.metadata_json, m.created_at,
                          rank AS relevance
                   FROM memories_fts f
                   JOIN memories m ON f.rowid = m.id
                   WHERE memories_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (safe_query, limit),
            ).fetchall()

        return [
            {
                "store": row["store"],
                "content": row["content"],
                "metadata": json.loads(row["metadata_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


# ──────────────────────────────────────────────
#  Agent settings
# ──────────────────────────────────────────────

def read_agent_settings(agent: str) -> dict[str, Any]:
    """Read agent-specific settings (cursor.json, claude_code.json, etc.)."""
    path = GLOBAL_ROOT / "agent_settings" / f"{agent}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_agent_settings(agent: str, settings: dict[str, Any]) -> str:
    """Write agent-specific settings."""
    _ensure_dirs()
    path = GLOBAL_ROOT / "agent_settings" / f"{agent}.json"
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return f"✓ Saved agent settings for {agent}"


# ──────────────────────────────────────────────
#  Initialization
# ──────────────────────────────────────────────

_STARTER_TEMPLATES = {
    "preferences": """# Agent Preferences

## Response Format
- Be concise, avoid filler
- Use markdown formatting
- Show code with language tags

## Coding Style
- Prefer descriptive variable names
- Add docstrings to public functions
- Follow language-specific conventions

## Tone
- Professional but friendly
- Explain tradeoffs, not just solutions
""",
    "arch_patterns": """# Architecture Patterns

## Patterns I Always Follow
- Separate concerns: data, logic, presentation
- Prefer composition over inheritance
- Keep functions small and focused
- Handle errors explicitly, never silently

## Anti-Patterns to Avoid
- God classes / god functions
- Magic numbers without named constants
- Deep nesting (max 3 levels)
""",
    "tech_stack": """# Tech Stack Preferences

## General
- Python 3.11+ for scripts and backends
- TypeScript for web frontends
- Flutter/Dart for mobile

## Preferences
- SQLite over heavy databases for local tools
- Click over argparse for CLI tools
- Pathlib over os.path
""",
}


def initialize() -> str:
    """Initialize the global store with directory structure and starter templates.

    Returns:
        Summary of what was created.
    """
    _ensure_dirs()
    created = []

    for store, template in _STARTER_TEMPLATES.items():
        path = _md_path(store)
        if not path.exists():
            path.write_text(template, encoding="utf-8")
            _index_to_db(store, template)
            created.append(f"  ✓ {store}.md")

    # Ensure errors.jsonl exists
    jsonl_path = GLOBAL_ROOT / "error_index" / "errors.jsonl"
    if not jsonl_path.exists():
        jsonl_path.write_text("", encoding="utf-8")
        created.append("  ✓ error_index/errors.jsonl")

    # Ensure DB is initialized
    conn = _get_db()
    conn.close()
    created.append("  ✓ global.db")

    if not created:
        return "Global store already initialized at " + str(GLOBAL_ROOT)

    return f"Initialized global store at {GLOBAL_ROOT}:\n" + "\n".join(created)
