"""Project store — manages <project>/context/ (git-tracked markdown files).

Each project gets a `context/` folder committed alongside the code.
Contains: active_task.md, file_map.md, arch.md, errors.md, theme.md, snapshots/
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# All known project context files
PROJECT_STORES = ("active_task", "file_map", "arch", "errors", "theme")

# Markers used to detect a project root directory
_PROJECT_MARKERS = (
    ".git",
    "package.json",
    "pyproject.toml",
    "pubspec.yaml",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Makefile",
)


def detect_project_root(start_path: str | Path | None = None) -> Path | None:
    """Walk up from start_path (or CWD) to find the project root.

    Looks for common project markers (.git, package.json, pyproject.toml, etc.).
    Returns None if no project root is found.
    """
    current = Path(start_path or os.getcwd()).resolve()

    # Walk up to drive root
    while True:
        for marker in _PROJECT_MARKERS:
            if (current / marker).exists():
                return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def context_dir(project_path: str | Path | None = None) -> Path:
    """Get the .context/ directory for a project.

    Args:
        project_path: Explicit project root. Auto-detects if None.

    Raises:
        FileNotFoundError: If no project root could be determined.
    """
    if project_path:
        root = Path(project_path).resolve()
    else:
        root = detect_project_root()
        if root is None:
            raise FileNotFoundError(
                "Could not detect project root. "
                "Run 'ctx init' inside a project, or pass --project <path>."
            )
    return root / ".context"


def _store_path(store: str, project_path: str | Path | None = None) -> Path:
    """Get the full path to a project context file."""
    if store not in PROJECT_STORES:
        raise ValueError(f"Unknown project store: {store}. Valid: {', '.join(PROJECT_STORES)}")
    return context_dir(project_path) / f"{store}.md"


# ──────────────────────────────────────────────
#  Read / Write
# ──────────────────────────────────────────────

def read_store(store: str, project_path: str | Path | None = None) -> str:
    """Read a project context file. Returns empty string if it doesn't exist."""
    path = _store_path(store, project_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_store(
    store: str,
    content: str,
    project_path: str | Path | None = None,
    mode: str = "append",
) -> str:
    """Write to a project context file.

    Args:
        store: One of 'active_task', 'file_map', 'arch', 'errors', 'theme'
        content: The content to write (markdown)
        project_path: Explicit project root. Auto-detects if None.
        mode: 'append' to add to existing, 'replace' to overwrite

    Returns:
        Confirmation message.
    """
    path = _store_path(store, project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if mode == "replace":
        path.write_text(content, encoding="utf-8")
    else:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        entry = f"\n\n---\n_Added: {now}_\n\n{content}"
        path.write_text(existing + entry, encoding="utf-8")

    return f"✓ Saved to .context/{store}.md ({mode})"


def read_all(project_path: str | Path | None = None) -> dict[str, str]:
    """Read all project context files into a dict.

    Returns:
        Dict mapping store name to content. Empty stores are omitted.
    """
    result = {}
    for store in PROJECT_STORES:
        content = read_store(store, project_path)
        if content.strip():
            result[store] = content
    return result


# ──────────────────────────────────────────────
#  Snapshots
# ──────────────────────────────────────────────

def save_snapshot(
    content: str,
    project_path: str | Path | None = None,
    label: str | None = None,
) -> str:
    """Save a session snapshot to .context/snapshots/.

    Args:
        content: The snapshot content (compressed session notes)
        project_path: Explicit project root
        label: Optional label suffix for the filename

    Returns:
        Path to the created snapshot file.
    """
    ctx = context_dir(project_path)
    snapshots_dir = ctx / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    suffix = f"_{label}" if label else ""
    filename = f"{today}{suffix}.md"
    path = snapshots_dir / filename

    # If file exists for today, append to it
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        now = datetime.now(timezone.utc).strftime("%H:%M UTC")
        path.write_text(existing + f"\n\n---\n_Session update: {now}_\n\n{content}", encoding="utf-8")
    else:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        header = f"# Session Snapshot — {now}\n\n{content}"
        path.write_text(header, encoding="utf-8")

    return str(path)


def list_snapshots(project_path: str | Path | None = None) -> list[str]:
    """List all snapshot files for a project, most recent first."""
    ctx = context_dir(project_path)
    snapshots_dir = ctx / "snapshots"
    if not snapshots_dir.exists():
        return []
    return sorted(
        [f.name for f in snapshots_dir.glob("*.md")],
        reverse=True,
    )


# ──────────────────────────────────────────────
#  Initialization
# ──────────────────────────────────────────────

_STARTER_TEMPLATES: dict[str, str] = {
    "active_task": """# Active Task

## Current Goal
_No active task set. Use `ctx save --store active_task "working on X"` to set one._

## Progress
- 

## Blockers
- None
""",
    "arch": """# Architecture Decisions

_Record architecture decisions, stack choices, and design rationale here._
""",
    "errors": """# Error Log

_Errors encountered in this project and their fixes._
""",
    "theme": """# Theme & UI Decisions

_Design tokens, color palette, UI component patterns for this project._
""",
}


from syncmcp import agents_md


def initialize(project_path: str | Path | None = None, force_agents: bool = False) -> str:
    """Initialize the .context/ folder for a project.

    Creates the directory structure, starter templates, and AGENTS.md.
    Does NOT overwrite existing context files, but can force-regen AGENTS.md.

    Returns:
        Summary of what was created.
    """
    ctx = context_dir(project_path)
    ctx.mkdir(parents=True, exist_ok=True)
    (ctx / "snapshots").mkdir(exist_ok=True)
    
    root = detect_project_root(project_path) or Path(project_path or os.getcwd())
    created: list[str] = []

    # 1. Create AGENTS.md in project root
    agents_msg = agents_md.write(root, force=force_agents)
    created.append(agents_msg)

    # 2. Create starter context files if they don't exist
    for store, template in _STARTER_TEMPLATES.items():
        path = ctx / f"{store}.md"
        if not path.exists():
            path.write_text(template, encoding="utf-8")
            created.append(f"  ✓ .context/{store}.md")

    # file_map.md is auto-generated, just create an empty placeholder
    file_map_path = ctx / "file_map.md"
    if not file_map_path.exists():
        file_map_path.write_text("# File Map\n\n_Run `ctx files` to auto-generate._\n", encoding="utf-8")
        created.append("  ✓ .context/file_map.md")

    return f"Initialized project context for '{root.name}':\n" + "\n".join(created)
