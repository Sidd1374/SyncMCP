# SyncMCP — Universal Agent Memory System

> Give **every AI agent** persistent, shared memory across sessions, tools, and projects.

SyncMCP is a locally-running MCP server that acts as a universal memory layer for all your AI coding agents — Claude Code, Cursor, Codex, Gemini, GPT, or any web tool. It remembers your preferences, tracks your active tasks, logs errors with their fixes, and lets you search across every project you've ever worked on.

**The killer feature:** Cross-project error lookup. Ask *"how did I fix that CORS error before?"* and get the exact fix from whichever project you solved it in, with date and file path.

---

## Architecture

SyncMCP uses a **two-scope model**:

| Scope | Location | Synced via | Contains |
|-------|----------|-----------|----------|
| **Global** | `C:\AgentMemory\` | GitHub / OneDrive | Preferences, architecture patterns, tech stack, agent configs, cross-project error index |
| **Project** | `<project>/context/` | Git (committed with code) | Active task, file map, architecture decisions, errors, theme/UI tokens, session snapshots |

```
┌─────────────────────────────────────────────────────────────────┐
│  Agents: Claude Code · Cursor · Codex · GPT · Web · CLI paste  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ MCP (stdio) / CLI
┌───────────────────────────▼─────────────────────────────────────┐
│  MCP Memory Server (Python · runs locally)                      │
│  get_context · search_memory · save_note · get_project          │
│  cross_project_lookup                                           │
└──────────┬────────────────────────────────────┬─────────────────┘
           │                                    │
┌──────────▼──────────┐          ┌──────────────▼──────────────┐
│  Global Store       │          │  Project Store               │
│  C:\AgentMemory\    │◄─cross──►│  my-project/context/         │
│                     │  ref     │                              │
│  preferences.md     │          │  active_task.md              │
│  arch_patterns.md   │          │  file_map.md (auto-gen)      │
│  tech_stack.md      │          │  arch.md                     │
│  agent_settings/    │          │  errors.md                   │
│  error_index/       │          │  theme.md                    │
│    errors.jsonl     │          │  snapshots/                  │
│  global.db (SQLite) │          │    2026-04-29.md             │
└─────────────────────┘          └──────────────────────────────┘
```

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/yourusername/SyncMCP.git
cd SyncMCP
pip install -e .
```

Or on Windows, just run:

```cmd
setup.bat
```

### 2. Initialize & Scan

```bash
# Set up the global store (one-time)
ctx setup

# Initialize context for your current project
cd my-project
ctx init

# Scan the codebase (AI extracts arch, theme, tasks, and TODOs)
ctx scan
```

### 3. Connect Your Agent

| Agent | Connection method |
|-------|------------------|
| **Claude Code** | `claude mcp add syncmcp -- python -m syncmcp.server` |
| **Cursor** | Add to `.cursor/mcp.json` |
| **Antigravity** | Add to `%APPDATA%\Antigravity\mcp_config.json` |
| **Codex / Web agents** | `ctx context --copy` then paste |

**Invisible Automation:** SyncMCP now includes `CLAUDE.md` and `.cursorrules`. Copy these to your project root, and your agent will automatically load context, scan empty projects, and save decisions without you ever having to ask.

---

## MCP Tools

| Tool | Description |
|------|-------------|
| `get_context(query)` | Assembles context from both scopes — auto-called on startup |
| `scan_project()` | AI-powered deep scan to auto-fill architecture, theme, and tasks |
| `save_note(content)` | Write to memory — auto-routes decisions to arch and errors to index |
| `search_memory(query)` | Full-text search across all stores using SQLite FTS5 |
| `cross_project_lookup()` | The "Killer Feature" — find fixes from any of your other projects |

---

## CLI Reference (`ctx`)

```bash
ctx setup                                  # Initialize global store
ctx init [--force]                         # Initialize project context/ + git hook
ctx save "fixed CORS by adding headers"    # Smart-route to correct scope
ctx save --store errors "CORS -> headers"  # Explicit store target
ctx context [--query "auth"] [--copy]      # Print/copy pasteable context
ctx files [--path .]                       # Regenerate file_map.md
ctx search "CORS error"                    # Full-text search
ctx lookup "CORS error"                    # Cross-project error search
ctx status                                 # Session + store health
ctx sync init <remote-url>                 # Set up git sync for global store
ctx sync push                              # Commit + push global store
ctx sync pull                              # Pull latest from remote
ctx sync status                            # Show sync state
ctx rebuild-index                          # Recovery: rebuild SQLite from JSONL
```

---

## Write Triggers

Content flows into memory through 3 mechanisms:

| Trigger | What happens |
|---------|-------------|
| **`ctx save "..."`** | Manual CLI save — auto-routes to the right store based on content keywords |
| **`git commit`** | Post-commit hook auto-updates `file_map.md` and flushes session notes |
| **Auto-flush** | MCP server tracks session context; at ~80% of context window, compresses and saves a snapshot |

---

## Cross-Project Error Lookup

The feature nobody else has. Every error+fix you save gets indexed in two places:

1. **Project-level:** `context/errors.md` (stays with the project)
2. **Global index:** `C:\AgentMemory\error_index\errors.jsonl` (searchable across ALL projects)

```bash
# Save an error fix
ctx save --store errors "CORS policy blocked → Added Access-Control-Allow-Origin header in Express middleware"

# Later, in a different project:
ctx lookup "CORS"
# → [my-api] 2026-04-29: CORS policy blocked → Added Access-Control-Allow-Origin header...
```

Each error is auto-tagged by keyword detection (cors, auth, database, api, build, etc.) and stored with project name, date, file path, and tags.

---

## File Structure

### Global Store — `C:\AgentMemory\`

| File | Purpose | Editable? |
|------|---------|-----------|
| `preferences.md` | Response format, coding style, naming conventions | ✅ Human-editable |
| `arch_patterns.md` | Patterns you always follow (composition over inheritance, etc.) | ✅ Human-editable |
| `tech_stack.md` | Tech preferences ("always use X over Y") | ✅ Human-editable |
| `agent_settings/cursor.json` | Per-agent MCP configuration | ✅ JSON |
| `error_index/errors.jsonl` | Cross-project error log (append-only) | ⚠️ Append-only |
| `global.db` | SQLite database with FTS5 search indexes | 🔒 Auto-managed |

### Project Store — `<project>/context/`

| File | Purpose | Updated by |
|------|---------|-----------|
| `active_task.md` | Current goal, progress, blockers | `ctx save` / MCP |
| `file_map.md` | Auto-generated directory tree with annotations | Git hook / `ctx files` |
| `arch.md` | Architecture decisions, stack choices, ADRs | `ctx save --store arch` |
| `errors.md` | Errors + fixes for THIS project | `ctx save --store errors` |
| `theme.md` | Design tokens, UI patterns, color palette | `ctx save --store theme` |
| `snapshots/*.md` | Auto-saved session snapshots (compressed) | Auto-flush / git hook |

---

## Design Decisions

### Why SQLite over ChromaDB?

| | ChromaDB | SQLite + FTS5 |
|---|----------|---------------|
| Install size | ~200 MB | **0 MB** (built into Python) |
| Cold start | 2–4 seconds | **<50 ms** |
| Dependencies | numpy, onnxruntime, tokenizers | **None** |
| Error search | Overkill (semantic) | **FTS5 is perfect** for error patterns |
| Recovery | Complex | `errors.jsonl` is the source of truth |

### Why two scopes?

- **Global** = survives across ALL projects (preferences, patterns, error index)
- **Project** = travels WITH the code via git (architecture, tasks, file map)
- Clone a repo on a new machine → project context comes with it
- Global preferences sync separately via GitHub/OneDrive

### Why JSONL for errors?

- Append-only: never loses data
- Git-diff friendly: one error per line
- Grep-able: works even if SQLite breaks
- SQLite mirrors it for fast FTS5 search
- Rebuild-from-JSONL available as disaster recovery

---

## License

MIT
