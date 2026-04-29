"""CLI tool — the `ctx` command for manual saves and non-MCP agents.

Usage:
    ctx init                              Initialize project context + install hook
    ctx save "fixed CORS by adding headers"  Smart-route to correct scope
    ctx save --store errors "CORS -> headers"  Explicit store
    ctx context [--query "auth flow"]      Print pasteable context block
    ctx files [--path .]                   Regenerate file_map.md
    ctx search "CORS error"               Cross-project search
    ctx status                            Show session + stores health
    ctx setup                             Initialize global store
    ctx sync push|pull|init|status        Sync global store to git remote
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import click

from syncmcp import hub, global_store, project_store, file_mapper, error_index, sync


# ──────────────────────────────────────────────
#  Hook installer helper
# ──────────────────────────────────────────────

def _find_hooks_source() -> Path | None:
    """Find the hooks/ directory shipped with the SyncMCP package."""
    # Try relative to this file (editable install)
    src_dir = Path(__file__).resolve().parent.parent.parent  # src/syncmcp -> src -> SyncMCP
    hooks_dir = src_dir / "hooks"
    if (hooks_dir / "post-commit.py").exists():
        return hooks_dir

    # Try CWD-based (if running from SyncMCP repo)
    cwd_hooks = Path.cwd() / "hooks"
    if (cwd_hooks / "post-commit.py").exists():
        return cwd_hooks

    return None


def _install_git_hook(project_path: str | Path | None, force: bool = False) -> str:
    """Install the SyncMCP post-commit hook into a project's .git/hooks/.

    Args:
        project_path: Project root (auto-detect if None)
        force: Overwrite existing hook if True

    Returns:
        Status message.
    """
    root = project_store.detect_project_root(project_path)
    if root is None:
        return "  [SKIP] No .git directory found — hook not installed"

    git_hooks_dir = root / ".git" / "hooks"
    if not git_hooks_dir.exists():
        return "  [SKIP] No .git/hooks directory — hook not installed"

    target = git_hooks_dir / "post-commit"
    hooks_src = _find_hooks_source()

    if hooks_src is None:
        # Fallback: write a minimal Python hook inline
        return _write_inline_hook(target, force)

    # Check if a hook already exists
    if target.exists() and not force:
        # Check if it's our hook
        content = target.read_text(encoding="utf-8", errors="ignore")
        if "syncmcp" in content.lower():
            return "  [OK] SyncMCP hook already installed"
        return (
            "  [SKIP] Existing post-commit hook found (not ours).\n"
            "  Use 'ctx init --force' to overwrite."
        )

    # Copy the Python hook as the main post-commit file
    py_hook = hooks_src / "post-commit.py"
    # Write a self-contained hook that calls Python
    hook_content = f"""#!/usr/bin/env python3
# SyncMCP post-commit hook — auto-installed by 'ctx init'
# Updates file_map.md and flushes session notes after every commit.
import subprocess, sys
from pathlib import Path

def main():
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if not root or not Path(root, "context").exists():
            return
        from syncmcp import file_mapper
        file_mapper.update_file_map(root)
        from syncmcp.session import get_session
        get_session(root).flush(label="git-hook")
    except Exception:
        pass  # Never block a commit

if __name__ == "__main__":
    main()
"""
    target.write_text(hook_content, encoding="utf-8")

    # Make executable on Unix
    if os.name != "nt":
        target.chmod(0o755)

    return "  [OK] Git post-commit hook installed"


def _write_inline_hook(target: Path, force: bool) -> str:
    """Write a minimal inline hook when source hooks directory isn't found."""
    if target.exists() and not force:
        content = target.read_text(encoding="utf-8", errors="ignore")
        if "syncmcp" in content.lower():
            return "  [OK] SyncMCP hook already installed"
        return "  [SKIP] Existing hook found. Use 'ctx init --force' to overwrite."

    hook_content = """#!/usr/bin/env python3
# SyncMCP post-commit hook (inline install)
import subprocess
from pathlib import Path
try:
    root = subprocess.run(["git","rev-parse","--show-toplevel"],
        capture_output=True,text=True,timeout=5).stdout.strip()
    if root and Path(root,"context").exists():
        from syncmcp import file_mapper
        file_mapper.update_file_map(root)
        from syncmcp.session import get_session
        get_session(root).flush(label="git-hook")
except Exception:
    pass
"""
    target.write_text(hook_content, encoding="utf-8")
    if os.name != "nt":
        target.chmod(0o755)
    return "  [OK] Git post-commit hook installed (inline)"


# ──────────────────────────────────────────────
#  Custom help formatter
# ──────────────────────────────────────────────

HELP_TEXT = """\
\b
  ███████╗██╗   ██╗███╗   ██╗ ██████╗███╗   ███╗ ██████╗██████╗
  ██╔════╝╚██╗ ██╔╝████╗  ██║██╔════╝████╗ ████║██╔════╝██╔══██╗
  ███████╗ ╚████╔╝ ██╔██╗ ██║██║     ██╔████╔██║██║     ██████╔╝
  ╚════██║  ╚██╔╝  ██║╚██╗██║██║     ██║╚██╔╝██║██║     ██╔═══╝
  ███████║   ██║   ██║ ╚████║╚██████╗██║ ╚═╝ ██║╚██████╗██║
  ╚══════╝   ╚═╝   ╚═╝  ╚═══╝ ╚═════╝╚═╝     ╚═╝ ╚═════╝╚═╝
  Universal Agent Memory — persistent, shared context for every AI agent.

\b
SETUP
  ctx setup                                  Initialize global store (one-time)
  ctx init [--force]                         Init project context/ + git hook

\b
MEMORY
  ctx save "fixed CORS with headers"         Smart-route to correct scope
  ctx save -s errors "CORS -> added header"  Save to a specific store
  ctx context [-q "auth"] [--copy]           Print/copy pasteable context block
  ctx status                                 Session + store health

\b
SEARCH
  ctx search "CORS error"                    Full-text search across all stores
  ctx lookup "TypeError"                     Cross-project error search
  ctx files [--print-only]                   Generate/view project file map

\b
SYNC
  ctx sync init <remote-url>                 Set up git remote for global store
  ctx sync push [-m "msg"]                   Commit + push global store
  ctx sync pull                              Pull latest from remote
  ctx sync status                            Show sync state

\b
RECOVERY
  ctx rebuild-index                          Rebuild SQLite index from errors.jsonl

\b
EXAMPLES
  ctx save "prefer composition over inheritance"
    -> auto-detected as preference, saved to global/preferences.md

  ctx save --store errors "CORS blocked -> Added Allow-Origin header"
    -> saved to BOTH project errors.md AND global error index

  ctx lookup "CORS"
    -> searches errors across ALL your projects

  ctx context --query "building auth" --copy
    -> generates context block, copies to clipboard for web agents

For full docs see: https://github.com/yourusername/SyncMCP
"""


class OrderedGroup(click.Group):
    """Click group that preserves command insertion order in help."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands)


@click.group(cls=OrderedGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="syncmcp")
def main() -> None:
    """ctx — Agent memory CLI. Gives every AI agent persistent, shared memory."""
    pass


# Override the default help with our custom text
main.help = HELP_TEXT


# ──────────────────────────────────────────────
#  ctx init
# ──────────────────────────────────────────────

@main.command()
@click.option("--project", "-p", default=None, help="Project root path (auto-detects if not given)")
@click.option("--force", is_flag=True, help="Overwrite existing git hook")
def init(project: str | None, force: bool) -> None:
    """Initialize project context, file map, and git hook."""
    # Ensure global store exists too
    global_msg = global_store.initialize()
    click.echo(global_msg)
    click.echo()

    # Initialize project context
    project_msg = project_store.initialize(project)
    click.echo(project_msg)
    click.echo()

    # Generate initial file map
    try:
        fm_msg = file_mapper.update_file_map(project)
        click.echo(fm_msg)
    except FileNotFoundError:
        click.echo("  [SKIP] Could not generate file map (no project root detected)")

    # Install git hook
    hook_msg = _install_git_hook(project, force)
    click.echo(hook_msg)


# ──────────────────────────────────────────────
#  ctx save
# ──────────────────────────────────────────────

@main.command()
@click.argument("content")
@click.option("--store", "-s", default=None, help="Target store (auto-detects if not given)")
@click.option("--project", "-p", default=None, help="Project root path")
def save(content: str, store: str | None, project: str | None) -> None:
    """Save a note, decision, or error fix to memory.

    Auto-detects the right store from content keywords.
    For errors, use: ctx save "error description -> fix"
    """
    result = hub.save_note(content, store, project)
    click.echo(result)


# ──────────────────────────────────────────────
#  ctx context
# ──────────────────────────────────────────────

@main.command()
@click.option("--query", "-q", default="", help="What you're working on (for relevance)")
@click.option("--project", "-p", default=None, help="Project root path")
@click.option("--stores", default=None, help="Comma-separated store filter")
@click.option("--copy", "-c", is_flag=True, help="Copy to clipboard")
def context(query: str, project: str | None, stores: str | None, copy: bool) -> None:
    """Print a pasteable context block for web agents.

    Use this to paste memory into ChatGPT, Kimi, Antigravity, or other tools.
    """
    store_list = stores.split(",") if stores else None
    result = hub.get_context(query, project, store_list)

    if copy:
        try:
            import subprocess
            process = subprocess.Popen(
                ["clip"], stdin=subprocess.PIPE, shell=True
            )
            process.communicate(result.encode("utf-8"))
            click.echo("[OK] Context copied to clipboard!")
            click.echo(f"  ({len(result):,} chars)")
        except Exception:
            click.echo(result)
            click.echo("\n[WARNING] Could not copy to clipboard. Content printed above.")
    else:
        click.echo(result)


# ──────────────────────────────────────────────
#  ctx files
# ──────────────────────────────────────────────

@main.command()
@click.option("--path", "-p", default=None, help="Project root path")
@click.option("--print-only", is_flag=True, help="Print tree without saving to file_map.md")
def files(path: str | None, print_only: bool) -> None:
    """Generate or regenerate the project file map."""
    if print_only:
        tree = file_mapper.generate_tree(path)
        click.echo(tree)
    else:
        result = file_mapper.update_file_map(path)
        click.echo(result)


# ──────────────────────────────────────────────
#  ctx search
# ──────────────────────────────────────────────

@main.command()
@click.argument("query")
@click.option("--scope", default=None, type=click.Choice(["global", "project"]))
@click.option("--errors-only", is_flag=True, help="Search only the error index")
@click.option("--limit", "-n", default=10, help="Max results")
def search(query: str, scope: str | None, errors_only: bool, limit: int) -> None:
    """Search across all memory stores (or just errors)."""
    if errors_only:
        result = hub.cross_project_lookup(query, limit)
    else:
        result = hub.search_memory(query, scope, limit)
    click.echo(result)


# ──────────────────────────────────────────────
#  ctx status
# ──────────────────────────────────────────────

@main.command()
@click.option("--project", "-p", default=None, help="Project root path")
def status(project: str | None) -> None:
    """Show session status and store health."""
    result = hub.status(project)
    click.echo(result)


# ──────────────────────────────────────────────
#  ctx setup
# ──────────────────────────────────────────────

@main.command()
def setup() -> None:
    """Initialize the global store at C:\\AgentMemory\\."""
    result = global_store.initialize()
    click.echo(result)
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Edit C:\\AgentMemory\\preferences.md with your preferences")
    click.echo("  2. Edit C:\\AgentMemory\\arch_patterns.md with your patterns")
    click.echo("  3. Edit C:\\AgentMemory\\tech_stack.md with your stack choices")
    click.echo("  4. Run 'ctx init' inside any project to set up project context")


# ──────────────────────────────────────────────
#  ctx lookup
# ──────────────────────────────────────────────

@main.command()
@click.argument("error_pattern")
@click.option("--limit", "-n", default=10, help="Max results")
def lookup(error_pattern: str, limit: int) -> None:
    """Search for errors and fixes across ALL your projects.

    Example: ctx lookup "CORS error"
    """
    result = hub.cross_project_lookup(error_pattern, limit)
    click.echo(result)


# ──────────────────────────────────────────────
#  ctx sync (group)
# ──────────────────────────────────────────────

@main.group()
def sync_cmd() -> None:
    """Sync the global store to a git remote."""
    pass


# Register as 'ctx sync' (not 'ctx sync-cmd')
main.add_command(sync_cmd, "sync")


@sync_cmd.command("init")
@click.argument("remote_url", required=False, default=None)
def sync_init(remote_url: str | None) -> None:
    """Initialize git repo in global store and set remote.

    Example: ctx sync init https://github.com/user/agent-memory.git
    """
    result = sync.sync_init(remote_url)
    click.echo(result)


@sync_cmd.command("push")
@click.option("--message", "-m", default=None, help="Commit message")
def sync_push(message: str | None) -> None:
    """Commit and push global store changes to remote."""
    result = sync.sync_push(message)
    click.echo(result)


@sync_cmd.command("pull")
def sync_pull() -> None:
    """Pull latest global store changes from remote."""
    result = sync.sync_pull()
    click.echo(result)


@sync_cmd.command("status")
def sync_status() -> None:
    """Show sync status of the global store."""
    result = sync.sync_status()
    click.echo(result)


# ──────────────────────────────────────────────
#  ctx rebuild-index
# ──────────────────────────────────────────────

@main.command("rebuild-index")
def rebuild_index() -> None:
    """Rebuild the SQLite error index from errors.jsonl (disaster recovery)."""
    result = error_index.rebuild_from_jsonl()
    click.echo(result)


if __name__ == "__main__":
    main()
