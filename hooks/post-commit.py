#!/usr/bin/env python3
"""SyncMCP post-commit hook — cross-platform (Windows, macOS, Linux).

Auto-updates file_map.md and flushes session notes after every git commit.
Runs in-process for reliability — no subprocess spawning.

Install: ctx init (automatic) or manually copy to .git/hooks/post-commit
"""

import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path | None:
    """Get the git project root."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def main() -> None:
    root = get_project_root()
    if root is None:
        return

    context_dir = root / "context"
    if not context_dir.exists():
        return

    # Update file map
    try:
        from syncmcp import file_mapper
        file_mapper.update_file_map(str(root))
    except Exception:
        pass  # Never block a commit

    # Flush pending session notes
    try:
        from syncmcp.session import get_session
        session = get_session(str(root))
        session.flush(label="git-hook")
    except Exception:
        pass  # Never block a commit


if __name__ == "__main__":
    main()
