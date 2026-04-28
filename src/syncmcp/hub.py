"""Central hub — routes all requests to the correct scope and assembles context.

This is the brain of SyncMCP. Every MCP tool and CLI command goes through here.
Handles scope detection (global vs project), context assembly, and write routing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from syncmcp import error_index, file_mapper, global_store, project_store, session

# Global scope stores
GLOBAL_SCOPES = {"preferences", "arch_patterns", "tech_stack", "agent_settings"}

# Project scope stores
PROJECT_SCOPES = {"active_task", "file_map", "arch", "errors", "theme"}

# Keywords that hint at global scope
_GLOBAL_KEYWORDS = re.compile(
    r"\b(prefer|always|never|convention|style|naming|pattern|rule|standard)\b",
    re.IGNORECASE,
)

# Keywords that hint at error content
_ERROR_KEYWORDS = re.compile(
    r"\b(error|bug|fix|crash|exception|traceback|failed|broken|issue)\b",
    re.IGNORECASE,
)


def _detect_scope(store: str | None, content: str = "") -> str:
    """Detect whether content belongs to global or project scope.

    Args:
        store: Explicit store name (if provided, determines scope)
        content: Content text (used for auto-detection if store is None)

    Returns:
        'global' or 'project'
    """
    if store:
        if store in GLOBAL_SCOPES:
            return "global"
        if store in PROJECT_SCOPES:
            return "project"

    # Auto-detect from content
    if _GLOBAL_KEYWORDS.search(content):
        return "global"

    return "project"


# ──────────────────────────────────────────────
#  get_context — assembles context from both scopes
# ──────────────────────────────────────────────

def get_context(
    query: str = "",
    project_path: str | None = None,
    stores: list[str] | None = None,
) -> str:
    """Assemble context from both scopes for an agent.

    Merges global preferences + project context into one clean markdown block.

    Args:
        query: What the agent is working on (used for relevance filtering)
        project_path: Explicit project root
        stores: Optional filter to specific stores

    Returns:
        Formatted markdown context block.
    """
    sections: list[str] = []

    # --- Global context ---
    sections.append("# 🌐 Global Context\n")

    if not stores or "preferences" in stores:
        prefs = global_store.read_store("preferences")
        if prefs.strip():
            sections.append("## Preferences\n" + prefs)

    if not stores or "arch_patterns" in stores:
        patterns = global_store.read_store("arch_patterns")
        if patterns.strip():
            sections.append("## Architecture Patterns\n" + patterns)

    if not stores or "tech_stack" in stores:
        stack = global_store.read_store("tech_stack")
        if stack.strip():
            sections.append("## Tech Stack\n" + stack)

    # --- Project context ---
    try:
        project_ctx = project_store.read_all(project_path)
        if project_ctx:
            root = project_store.detect_project_root(project_path)
            project_name = root.name if root else "current project"
            sections.append(f"\n# 📁 Project: {project_name}\n")

            store_labels = {
                "active_task": "Active Task",
                "file_map": "File Map",
                "arch": "Architecture",
                "errors": "Error Log",
                "theme": "Theme & UI",
            }

            for store_name, content in project_ctx.items():
                if stores and store_name not in stores:
                    continue
                label = store_labels.get(store_name, store_name)
                sections.append(f"## {label}\n{content}")
    except FileNotFoundError:
        sections.append("\n_No project context found. Run `ctx init` to set up._")

    # --- Relevant errors (if query provided) ---
    if query:
        errors = error_index.search(query, limit=3)
        if errors:
            sections.append("\n## 🔍 Related Errors (cross-project)\n")
            sections.append(error_index.format_results(errors))

    context = "\n\n---\n\n".join(sections)

    # Track in session
    tracker = session.get_session(project_path)
    tracker.track(context, source="get_context")

    return context


# ──────────────────────────────────────────────
#  search_memory — full-text search across stores
# ──────────────────────────────────────────────

def search_memory(query: str, scope: str | None = None, limit: int = 10) -> str:
    """Search across all memory stores using SQLite FTS5.

    Args:
        query: Search query
        scope: 'global', 'project', or None for both
        limit: Max results

    Returns:
        Formatted search results.
    """
    results: list[str] = []

    # Search global store
    if scope in (None, "global"):
        global_results = global_store.search(query, limit=limit)
        if global_results:
            results.append("## Global Memory Matches\n")
            for r in global_results:
                results.append(f"**[{r['store']}]** {r['content'][:200]}...")
                results.append("")

    # Search error index (always cross-project)
    error_results = error_index.search(query, limit=limit)
    if error_results:
        results.append(error_index.format_results(error_results))

    if not results:
        return f"_No results found for: {query}_"

    return "\n".join(results)


# ──────────────────────────────────────────────
#  save_note — write to correct scope
# ──────────────────────────────────────────────

def save_note(
    content: str,
    store: str | None = None,
    project_path: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Save a note to the correct scope.

    Auto-detects scope from content if store is not specified.
    Error saves go to BOTH scopes (project errors.md + global errors.jsonl).

    Args:
        content: The note content
        store: Explicit store name, or None for auto-detect
        project_path: Explicit project root
        metadata: Optional metadata

    Returns:
        Confirmation message(s).
    """
    messages: list[str] = []

    # Auto-detect store if not specified
    if not store:
        if _ERROR_KEYWORDS.search(content):
            store = "errors"
        elif _GLOBAL_KEYWORDS.search(content):
            store = "preferences"
        else:
            store = "active_task"

    scope = _detect_scope(store, content)

    # Write to the correct scope
    if scope == "global" and store in global_store.GLOBAL_STORES:
        msg = global_store.write_store(store, content)
        messages.append(msg)

    elif scope == "project" and store in project_store.PROJECT_STORES:
        msg = project_store.write_store(store, content, project_path)
        messages.append(msg)

    # Error saves → BOTH scopes
    if store == "errors":
        # Parse error/fix from content
        error_text, fix_text = _parse_error_fix(content)

        # Save to global error index
        idx_msg = error_index.save_error(
            error_text=error_text,
            fix_text=fix_text,
            file_path=metadata.get("file", "") if metadata else "",
        )
        messages.append(idx_msg)

        # Also save to project errors.md
        try:
            proj_msg = project_store.write_store("errors", content, project_path)
            messages.append(proj_msg)
        except FileNotFoundError:
            pass

    # Track in session
    tracker = session.get_session(project_path)
    tracker.track(content, source=f"save_note/{store}")

    return " | ".join(messages)


def _parse_error_fix(content: str) -> tuple[str, str]:
    """Parse error and fix text from a free-form note.

    Supports formats:
    - "error → fix"
    - "error -> fix"
    - "Error: ... Fix: ..."
    - Just the error text (no fix)
    """
    # Try arrow separator
    for sep in ("→", "->", "=>"):
        if sep in content:
            parts = content.split(sep, 1)
            return parts[0].strip(), parts[1].strip()

    # Try "Fix:" label
    match = re.search(r"(?:fix|solution|resolved):\s*(.+)", content, re.IGNORECASE | re.DOTALL)
    if match:
        error_part = content[:match.start()].strip()
        fix_part = match.group(1).strip()
        return error_part, fix_part

    # Just error text, no fix
    return content.strip(), ""


# ──────────────────────────────────────────────
#  get_project — returns full project context bundle
# ──────────────────────────────────────────────

def get_project(project_path: str | None = None) -> str:
    """Get the full project context bundle as formatted markdown.

    Args:
        project_path: Explicit project root

    Returns:
        Complete project context (all stores merged).
    """
    try:
        ctx = project_store.read_all(project_path)
    except FileNotFoundError:
        return "_No project context found. Run `ctx init` to set up._"

    if not ctx:
        return "_Project context is empty. Run `ctx init` to create starter templates._"

    root = project_store.detect_project_root(project_path)
    project_name = root.name if root else "current project"

    sections = [f"# Project Context — {project_name}\n"]

    store_labels = {
        "active_task": "🎯 Active Task",
        "file_map": "🗂️ File Map",
        "arch": "🏗️ Architecture",
        "errors": "🐛 Error Log",
        "theme": "🎨 Theme & UI",
    }

    for store_name, content in ctx.items():
        label = store_labels.get(store_name, store_name)
        sections.append(f"## {label}\n{content}")

    # Add snapshots list
    snapshots = project_store.list_snapshots(project_path)
    if snapshots:
        sections.append(f"## 📸 Snapshots ({len(snapshots)} saved)")
        for s in snapshots[:5]:
            sections.append(f"- {s}")

    return "\n\n---\n\n".join(sections)


# ──────────────────────────────────────────────
#  cross_project_lookup — search errors across all projects
# ──────────────────────────────────────────────

def cross_project_lookup(error_pattern: str, limit: int = 10) -> str:
    """Search for errors across ALL projects.

    This is the killer feature — "how did I fix that CORS error before?"

    Args:
        error_pattern: The error to search for (natural language or error text)
        limit: Max results

    Returns:
        Formatted results with project name, date, error, fix.
    """
    results = error_index.search(error_pattern, limit=limit)
    return error_index.format_results(results)


# ──────────────────────────────────────────────
#  list_files — get/regenerate file map
# ──────────────────────────────────────────────

def list_files(project_path: str | None = None, regenerate: bool = False) -> str:
    """Get the project file map.

    Args:
        project_path: Project root
        regenerate: If True, re-scan the directory tree

    Returns:
        File map content.
    """
    if regenerate:
        return file_mapper.update_file_map(project_path)

    # Try to read existing file_map.md
    try:
        content = project_store.read_store("file_map", project_path)
        if content.strip() and "Run `ctx files`" not in content:
            return content
    except (FileNotFoundError, ValueError):
        pass

    # Fallback: generate fresh
    return file_mapper.generate_tree(project_path)


# ──────────────────────────────────────────────
#  status — session and store health
# ──────────────────────────────────────────────

def status(project_path: str | None = None) -> str:
    """Get overall status of the memory system.

    Returns:
        Formatted status report.
    """
    tracker = session.get_session(project_path)
    sess = tracker.status()

    lines = ["# SyncMCP Status\n"]

    # Session
    lines.append("## Session")
    lines.append(f"- Started: {sess['started_at']}")
    lines.append(f"- Context used: {sess['usage_pct']}% ({sess['estimated_tokens']:,} tokens)")
    lines.append(f"- Entries buffered: {sess['entries_buffered']}")
    lines.append(f"- Auto-flushes: {sess['flushes']}")
    lines.append("")

    # Global store
    lines.append("## Global Store")
    lines.append(f"- Location: {global_store.GLOBAL_ROOT}")
    for store_name in global_store.GLOBAL_STORES:
        content = global_store.read_store(store_name)
        size = len(content) if content else 0
        status_icon = "✅" if size > 0 else "⬜"
        lines.append(f"  {status_icon} {store_name}.md ({size:,} chars)")
    lines.append("")

    # Project store
    lines.append("## Project Store")
    try:
        root = project_store.detect_project_root(project_path)
        if root:
            lines.append(f"- Project: {root.name}")
            lines.append(f"- Context: {root / 'context'}")
            for store_name in project_store.PROJECT_STORES:
                content = project_store.read_store(store_name, project_path)
                size = len(content) if content else 0
                status_icon = "✅" if size > 0 else "⬜"
                lines.append(f"  {status_icon} {store_name}.md ({size:,} chars)")

            snapshots = project_store.list_snapshots(project_path)
            lines.append(f"  📸 {len(snapshots)} snapshot(s)")
        else:
            lines.append("  _No project detected_")
    except FileNotFoundError:
        lines.append("  _No project context initialized_")

    return "\n".join(lines)
