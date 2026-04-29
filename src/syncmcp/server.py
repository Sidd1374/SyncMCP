"""MCP Memory Server — the entry point for all agent connections.

Exposes 5 tools via FastMCP:
  get_context      — assembles context from both scopes for a task
  search_memory    — full-text search across all stores (SQLite FTS5)
  save_note        — write to the correct scope (auto-detects)
  get_project      — returns the full project context bundle
  cross_project_lookup — searches errors across ALL projects

Transport: stdio (default) for Claude Code, Cursor, Codex.
           SSE available via --transport sse flag.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from syncmcp import hub

mcp = FastMCP(
    "SyncMCP",
    instructions=(
        "SyncMCP is your persistent memory system. "
        "Use get_context at the start of every task to load relevant memory. "
        "Use save_note to remember decisions, fixes, and progress. "
        "Use cross_project_lookup to find how you fixed similar errors before."
    ),
)


@mcp.tool()
def get_context(
    query: str = "",
    project_path: str | None = None,
    stores: list[str] | None = None,
) -> str:
    """Fetch relevant memory for a task — merges global prefs + project context.

    Call this at the START of every conversation to load context.

    Args:
        query: What you're working on (used to find relevant errors/notes)
        project_path: Project root path. Auto-detects from CWD if not provided.
        stores: Optional filter to specific stores. Valid values:
                Global: 'preferences', 'arch_patterns', 'tech_stack'
                Project: 'active_task', 'file_map', 'arch', 'errors', 'theme'

    Returns:
        Formatted markdown context block with all relevant memory.
    """
    return hub.get_context(query, project_path, stores)


@mcp.tool()
def search_memory(
    query: str,
    scope: str | None = None,
    limit: int = 10,
) -> str:
    """Full-text search across all memory stores.

    Searches both global preferences and project-level context using SQLite FTS5.

    Args:
        query: Search query (supports AND, OR, NOT, "exact phrases")
        scope: 'global' or 'project' — searches both if not specified
        limit: Maximum number of results to return

    Returns:
        Formatted search results with source attribution.
    """
    return hub.search_memory(query, scope, limit)


@mcp.tool()
def save_note(
    content: str,
    store: str | None = None,
    project_path: str | None = None,
) -> str:
    """Save a note, decision, error fix, or progress update to memory.

    Auto-detects the right store and scope from content:
    - Error keywords → errors store (saved to BOTH project + global index)
    - Preference keywords → global preferences
    - Everything else → project active_task

    Args:
        content: What to save (markdown supported). For errors, use format:
                 "error description → how it was fixed"
        store: Explicit store override. Valid values:
               Global: 'preferences', 'arch_patterns', 'tech_stack'
               Project: 'active_task', 'file_map', 'arch', 'errors', 'theme'
        project_path: Project root path. Auto-detects if not provided.

    Returns:
        Confirmation of where the note was saved.
    """
    return hub.save_note(content, store, project_path)


@mcp.tool()
def get_project(project_path: str | None = None) -> str:
    """Get the complete project context bundle.

    Returns all project-level context files merged into one document:
    active task, file map, architecture, errors, theme, and snapshots.

    Args:
        project_path: Project root path. Auto-detects if not provided.

    Returns:
        Full project context as formatted markdown.
    """
    return hub.get_project(project_path)


@mcp.tool()
def cross_project_lookup(
    error_pattern: str,
    limit: int = 10,
) -> str:
    """Search for errors and fixes across ALL your projects.

    This is the killer feature — ask "how did I fix that CORS error before?"
    and get results from any project where you solved it, with the fix.

    Args:
        error_pattern: The error to search for (natural language or error text)
        limit: Maximum number of results

    Returns:
        Matching errors with project name, date, error text, fix, and file path.
    """
    return hub.cross_project_lookup(error_pattern, limit)


# ──────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────

def main() -> None:
    """Start the MCP server.

    Supports:
        python -m syncmcp.server                    # stdio (default)
        python -m syncmcp.server --transport sse    # SSE on port 8765
        python -m syncmcp.server --transport sse --port 9000
    """
    import argparse

    parser = argparse.ArgumentParser(description="SyncMCP Memory Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for SSE transport (default: 8765)",
    )
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.run(transport="sse", host="127.0.0.1", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

