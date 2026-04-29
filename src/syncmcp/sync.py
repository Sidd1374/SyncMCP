"""Sync module — git-based sync for the global store.

Manages a git repo inside C:\\AgentMemory\\ so your preferences,
patterns, and error index can be pushed to GitHub/OneDrive and
pulled on a new machine.

Project-level context/ is already git-tracked with the project itself.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from syncmcp import global_store


def _run_git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a git command in the global store directory."""
    work_dir = cwd or global_store.GLOBAL_ROOT
    return subprocess.run(
        ["git", *args],
        cwd=str(work_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _is_git_repo() -> bool:
    """Check if the global store is already a git repo."""
    return (global_store.GLOBAL_ROOT / ".git").exists()


# ──────────────────────────────────────────────
#  Init
# ──────────────────────────────────────────────

def sync_init(remote_url: str | None = None) -> str:
    """Initialize a git repo in the global store and optionally set a remote.

    Args:
        remote_url: GitHub/remote URL to add as origin (optional)

    Returns:
        Status message.
    """
    global_store._ensure_dirs()
    messages: list[str] = []

    if not _is_git_repo():
        result = _run_git("init")
        if result.returncode != 0:
            return f"[ERROR] git init failed: {result.stderr.strip()}"
        messages.append("[OK] Initialized git repo in global store")

        # Create .gitignore for the global store
        gitignore = global_store.GLOBAL_ROOT / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                "# SyncMCP global store\n"
                "# SQLite DB is regenerated from source files — don't sync it\n"
                "global.db\n"
                "global.db-wal\n"
                "global.db-shm\n",
                encoding="utf-8",
            )
            messages.append("[OK] Created .gitignore (excludes global.db)")
    else:
        messages.append("[OK] Git repo already exists")

    if remote_url:
        # Check if remote already exists
        check = _run_git("remote", "get-url", "origin")
        if check.returncode == 0:
            existing = check.stdout.strip()
            if existing == remote_url:
                messages.append(f"[OK] Remote 'origin' already set to {remote_url}")
            else:
                _run_git("remote", "set-url", "origin", remote_url)
                messages.append(f"[OK] Updated remote 'origin' to {remote_url}")
        else:
            _run_git("remote", "add", "origin", remote_url)
            messages.append(f"[OK] Added remote 'origin': {remote_url}")

    return "\n".join(messages)


# ──────────────────────────────────────────────
#  Push
# ──────────────────────────────────────────────

def sync_push(message: str | None = None) -> str:
    """Stage all changes, commit, and push to remote.

    Args:
        message: Commit message (auto-generated if not provided)

    Returns:
        Status message.
    """
    if not _is_git_repo():
        return "[ERROR] Global store is not a git repo. Run: ctx sync init <remote-url>"

    # Stage all changes
    _run_git("add", "-A")

    # Check if there are changes to commit
    status = _run_git("status", "--porcelain")
    if not status.stdout.strip():
        return "[OK] Nothing to sync — no changes since last commit"

    # Commit
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commit_msg = message or f"SyncMCP auto-sync: {now}"
    commit_result = _run_git("commit", "-m", commit_msg)
    if commit_result.returncode != 0:
        return f"[ERROR] Commit failed: {commit_result.stderr.strip()}"

    # Push
    push_result = _run_git("push", "origin", "main")
    if push_result.returncode != 0:
        # Try 'master' branch if 'main' fails
        push_result = _run_git("push", "origin", "master")
        if push_result.returncode != 0:
            # Push might fail if no remote is configured — that's okay
            if "No configured push destination" in push_result.stderr:
                return f"[OK] Committed locally. No remote configured — run: ctx sync init <url>"
            return (
                f"[OK] Committed locally.\n"
                f"[WARNING] Push failed: {push_result.stderr.strip()}\n"
                f"You may need to set up the remote: ctx sync init <url>"
            )

    return f"[OK] Synced to remote ({commit_msg})"


# ──────────────────────────────────────────────
#  Pull
# ──────────────────────────────────────────────

def sync_pull() -> str:
    """Pull latest changes from remote.

    Returns:
        Status message.
    """
    if not _is_git_repo():
        return "[ERROR] Global store is not a git repo. Run: ctx sync init <remote-url>"

    result = _run_git("pull", "origin", "main")
    if result.returncode != 0:
        result = _run_git("pull", "origin", "master")
        if result.returncode != 0:
            return f"[ERROR] Pull failed: {result.stderr.strip()}"

    output = result.stdout.strip()
    if "Already up to date" in output:
        return "[OK] Already up to date"

    return f"[OK] Pulled latest changes:\n{output}"


# ──────────────────────────────────────────────
#  Status
# ──────────────────────────────────────────────

def sync_status() -> str:
    """Show sync status of the global store.

    Returns:
        Formatted status report.
    """
    lines: list[str] = ["# Sync Status\n"]
    lines.append(f"Global store: {global_store.GLOBAL_ROOT}")

    if not _is_git_repo():
        lines.append("Git: [NOT INITIALIZED]")
        lines.append("Run: ctx sync init <remote-url>")
        return "\n".join(lines)

    lines.append("Git: [INITIALIZED]")

    # Remote
    remote = _run_git("remote", "get-url", "origin")
    if remote.returncode == 0:
        lines.append(f"Remote: {remote.stdout.strip()}")
    else:
        lines.append("Remote: [NONE] — run: ctx sync init <url>")

    # Last commit
    log = _run_git("log", "-1", "--format=%h %s (%ar)")
    if log.returncode == 0 and log.stdout.strip():
        lines.append(f"Last commit: {log.stdout.strip()}")
    else:
        lines.append("Last commit: [NO COMMITS YET]")

    # Dirty state
    status = _run_git("status", "--porcelain")
    changed = len(status.stdout.strip().splitlines()) if status.stdout.strip() else 0
    if changed > 0:
        lines.append(f"Pending changes: {changed} file(s) — run: ctx sync push")
    else:
        lines.append("Pending changes: none (clean)")

    return "\n".join(lines)
