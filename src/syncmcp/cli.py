"""CLI tool — the `ctx` command for manual saves and non-MCP agents.

Usage:
    ctx init                              Initialize project context
    ctx save "fixed CORS by adding headers"  Smart-route to correct scope
    ctx save --store errors "CORS → headers"  Explicit store
    ctx context [--query "auth flow"]      Print pasteable context block
    ctx files [--path .]                   Regenerate file_map.md
    ctx search "CORS error"               Cross-project search
    ctx status                            Show session + stores health
    ctx setup                             Initialize global store
"""

from __future__ import annotations

import click

from syncmcp import hub, global_store, project_store, file_mapper, error_index


@click.group()
@click.version_option(package_name="syncmcp")
def main() -> None:
    """ctx — Agent memory CLI. Gives every AI agent persistent, shared memory."""
    pass


# ──────────────────────────────────────────────
#  ctx init
# ──────────────────────────────────────────────

@main.command()
@click.option("--project", "-p", default=None, help="Project root path (auto-detects if not given)")
def init(project: str | None) -> None:
    """Initialize the context/ folder for the current project."""
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
        click.echo("⚠️  Could not generate file map (no project root detected)")


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
    For errors, use: ctx save "error description → fix"
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
@click.option("--copy", "-c", is_flag=True, help="Copy to clipboard (requires pyperclip)")
def context(query: str, project: str | None, stores: str | None, copy: bool) -> None:
    """Print a pasteable context block for web agents.

    Use this to paste memory into ChatGPT, Kimi, or other web tools.
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
            click.echo("✓ Context copied to clipboard!")
            click.echo(f"  ({len(result):,} chars)")
        except Exception:
            click.echo(result)
            click.echo("\n⚠️  Could not copy to clipboard. Content printed above.")
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
#  ctx lookup (alias for cross_project_lookup)
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
#  ctx rebuild-index (recovery)
# ──────────────────────────────────────────────

@main.command("rebuild-index")
def rebuild_index() -> None:
    """Rebuild the SQLite error index from errors.jsonl (disaster recovery)."""
    result = error_index.rebuild_from_jsonl()
    click.echo(result)


if __name__ == "__main__":
    main()
