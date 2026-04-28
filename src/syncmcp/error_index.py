"""Error index — cross-project error search (errors.jsonl + SQLite FTS5).

Two-tier storage:
1. errors.jsonl — append-only log, git-friendly, grep-friendly (source of truth)
2. SQLite errors table + FTS5 — instant full-text search across all projects

When an error is saved, it goes to:
- Project scope: context/errors.md (human-readable log for THIS project)
- Global scope: C:\\AgentMemory\\error_index\\errors.jsonl + SQLite (cross-project search)
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from syncmcp import global_store


def _get_db() -> sqlite3.Connection:
    """Get the global SQLite connection with errors table + FTS5."""
    conn = global_store._get_db()

    # Errors table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            error_text TEXT NOT NULL,
            fix_text TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '[]',
            file_path TEXT DEFAULT '',
            date TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # FTS5 for error search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS errors_fts USING fts5(
            error_text, fix_text, project, tags, file_path,
            content=errors,
            content_rowid=id
        )
    """)

    # Sync triggers
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS errors_ai AFTER INSERT ON errors BEGIN
            INSERT INTO errors_fts(rowid, error_text, fix_text, project, tags, file_path)
            VALUES (new.id, new.error_text, new.fix_text, new.project, new.tags, new.file_path);
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS errors_ad AFTER DELETE ON errors BEGIN
            INSERT INTO errors_fts(errors_fts, rowid, error_text, fix_text, project, tags, file_path)
            VALUES ('delete', old.id, old.error_text, old.fix_text, old.project, old.tags, old.file_path);
        END
    """)

    conn.commit()
    return conn


def _jsonl_path() -> Path:
    """Get the path to the global errors.jsonl file."""
    return global_store.GLOBAL_ROOT / "error_index" / "errors.jsonl"


# ──────────────────────────────────────────────
#  Save
# ──────────────────────────────────────────────

def save_error(
    error_text: str,
    fix_text: str = "",
    project: str = "",
    file_path: str = "",
    tags: list[str] | None = None,
) -> str:
    """Save an error+fix to both the global index and project context.

    Args:
        error_text: The error message or description
        fix_text: How it was fixed
        project: Project name (auto-detected from CWD if empty)
        file_path: File where the error occurred
        tags: Optional tags for categorization

    Returns:
        Confirmation message.
    """
    if not project:
        from syncmcp import project_store
        root = project_store.detect_project_root()
        project = root.name if root else "unknown"

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    tags_list = tags or _auto_tag(error_text, fix_text)

    # 1. Append to errors.jsonl (source of truth)
    entry = {
        "error": error_text,
        "fix": fix_text,
        "project": project,
        "file": file_path,
        "tags": tags_list,
        "date": date_str,
    }

    jsonl = _jsonl_path()
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(jsonl, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # 2. Index into SQLite
    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO errors (project, error_text, fix_text, tags, file_path, date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (project, error_text, fix_text, json.dumps(tags_list), file_path, date_str, now.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    return f"✓ Error indexed (project: {project}, tags: {', '.join(tags_list)})"


def _auto_tag(error_text: str, fix_text: str) -> list[str]:
    """Auto-generate tags from error and fix text using keyword matching."""
    combined = (error_text + " " + fix_text).lower()
    tags = []

    # Common error categories
    tag_patterns = {
        "cors": r"\bcors\b",
        "auth": r"\bauth|jwt|token|login|session\b",
        "database": r"\bsql|sqlite|postgres|mongo|db\b",
        "api": r"\bapi|endpoint|rest|graphql|fetch\b",
        "import": r"\bimport|module|require|package\b",
        "types": r"\btype|typescript|typing|annotation\b",
        "build": r"\bbuild|compile|webpack|vite|gradle\b",
        "network": r"\bnetwork|timeout|connection|socket\b",
        "permission": r"\bpermission|access|denied|forbidden\b",
        "null": r"\bnull|undefined|none|nil\b",
        "async": r"\basync|await|promise|future\b",
        "css": r"\bcss|style|layout|flexbox|grid\b",
        "git": r"\bgit|merge|conflict|branch\b",
        "deploy": r"\bdeploy|docker|container|server\b",
    }

    for tag, pattern in tag_patterns.items():
        if re.search(pattern, combined):
            tags.append(tag)

    return tags or ["general"]


# ──────────────────────────────────────────────
#  Search (cross-project)
# ──────────────────────────────────────────────

def search(
    query: str,
    project: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search errors across all projects using SQLite FTS5.

    Args:
        query: Search query (natural language or error text)
        project: Optional filter to a specific project
        limit: Max results

    Returns:
        List of error dicts with project, error, fix, tags, date.
    """
    conn = _get_db()
    try:
        # Sanitize query for FTS5
        safe_query = " ".join(f'"{term}"' for term in query.split() if term.strip())
        if not safe_query:
            return []

        if project:
            rows = conn.execute(
                """SELECT e.project, e.error_text, e.fix_text, e.tags, e.file_path, e.date
                   FROM errors_fts f
                   JOIN errors e ON f.rowid = e.id
                   WHERE errors_fts MATCH ? AND e.project = ?
                   ORDER BY rank
                   LIMIT ?""",
                (safe_query, project, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT e.project, e.error_text, e.fix_text, e.tags, e.file_path, e.date
                   FROM errors_fts f
                   JOIN errors e ON f.rowid = e.id
                   WHERE errors_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (safe_query, limit),
            ).fetchall()

        return [
            {
                "project": row["project"],
                "error": row["error_text"],
                "fix": row["fix_text"],
                "tags": json.loads(row["tags"]),
                "file": row["file_path"],
                "date": row["date"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def format_results(results: list[dict[str, Any]]) -> str:
    """Format search results as a readable markdown block."""
    if not results:
        return "_No matching errors found._"

    lines = [f"## Cross-Project Error Search — {len(results)} result(s)\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"### {i}. [{r['project']}] — {r['date']}")
        lines.append(f"**Error:** {r['error']}")
        if r["fix"]:
            lines.append(f"**Fix:** {r['fix']}")
        if r["file"]:
            lines.append(f"**File:** `{r['file']}`")
        if r["tags"]:
            lines.append(f"**Tags:** {', '.join(r['tags'])}")
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────
#  Rebuild index from JSONL (recovery)
# ──────────────────────────────────────────────

def rebuild_from_jsonl() -> str:
    """Rebuild the SQLite errors index from errors.jsonl.

    Use this if the DB gets corrupted — the JSONL is the source of truth.
    """
    jsonl = _jsonl_path()
    if not jsonl.exists():
        return "No errors.jsonl found."

    conn = _get_db()
    try:
        # Clear existing errors
        conn.execute("DELETE FROM errors")
        conn.commit()

        count = 0
        with open(jsonl, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                conn.execute(
                    """INSERT INTO errors (project, error_text, fix_text, tags, file_path, date, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entry.get("project", "unknown"),
                        entry.get("error", ""),
                        entry.get("fix", ""),
                        json.dumps(entry.get("tags", [])),
                        entry.get("file", ""),
                        entry.get("date", ""),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                count += 1

        conn.commit()
        return f"✓ Rebuilt error index: {count} entries from errors.jsonl"
    finally:
        conn.close()
