# SyncMCP — Setup & Agent Connection Guide

Complete setup instructions and per-agent connection guides for every supported tool.

---

## Prerequisites

- **Python 3.11+** — [Download](https://python.org/downloads/)
- **Git** — [Download](https://git-scm.com/downloads)
- **pip** — comes with Python (verify: `pip --version`)

---

## Step 1 — Install SyncMCP

### Windows (recommended)

```cmd
cd SyncMCP
setup.bat
```

This runs everything: creates `C:\AgentMemory\`, installs the package, initializes templates, verifies `ctx`.

### Manual install (any OS)

```bash
cd SyncMCP
pip install -e .
ctx setup
```

On macOS/Linux, set the global store location:

```bash
# Add to ~/.bashrc or ~/.zshrc
export AGENT_MEMORY_ROOT="$HOME/.agent-memory"
```

### Step 2 — Init & Scan
Run this inside every project you want SyncMCP to track:

```bash
cd your-project
ctx init
ctx scan
```

The `ctx scan` command reads your codebase and auto-populates the `context/` folder. It uses regex to find TODOs/FIXMEs and (optionally) an LLM to generate architecture and task summaries.

---

## Invisible Automation (Recommended)

SyncMCP works best when you don't have to think about it. We provide rule files that tell your AI agent exactly how to use the memory tools.

### 1. Claude Code
Copy `CLAUDE.md` from the SyncMCP repo to your project root.
- **Effect:** Claude will call `get_context` on every startup and `save_note` whenever you make a decision.

### 2. Cursor
Copy `.cursorrules` (or rename to `.cursorrules`) from the SyncMCP repo to your project root.
- **Effect:** Cursor's composer/agent will proactively manage your project memory.

### 3. Antigravity
Add the following to **Custom Instructions** (Settings → Agent):
> *"At the start of every task, call get_context. If context is empty, call scan_project. Automatically call save_note when you solve a problem or make a tech decision. Do not ask for permission."*

---

## Agent Connection Guides

### Claude Code (CLI)

```bash
claude mcp add syncmcp -- python -m syncmcp.server
```

That's it. Claude Code discovers all 5 tools automatically.

**Pro tip:** At the start of every session, say *"run get_context first"* — or add it to your project's `CLAUDE.md`:

```markdown
## Instructions
- At the start of every task, call get_context with the task description
- When you fix an error, call save_note with format "error -> fix"
- Before ending a session, call save_note to record what was completed
```

---

### Claude Desktop (Windows)

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "syncmcp": {
      "command": "python",
      "args": ["-m", "syncmcp.server"]
    }
  }
}
```

Restart Claude Desktop. SyncMCP appears in the tools list (hammer icon).

### Claude Desktop (macOS)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "syncmcp": {
      "command": "python3",
      "args": ["-m", "syncmcp.server"]
    }
  }
}
```

---

### Cursor

Create `.cursor/mcp.json` in your project root (or `~/.cursor/mcp.json` for global):

```json
{
  "mcpServers": {
    "syncmcp": {
      "command": "python",
      "args": ["-m", "syncmcp.server"]
    }
  }
}
```

Cursor auto-detects config changes — no restart needed.

---

### VS Code + GitHub Copilot

Create `.vscode/mcp.json` in your project root:

```json
{
  "servers": {
    "syncmcp": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "syncmcp.server"]
    }
  }
}
```

> **Requires VS Code 1.99+** with Copilot agent mode enabled (Settings → Copilot → Agent Mode).

---

### Antigravity (Google AI IDE)

Antigravity supports MCP the same way as Cursor. Add to Antigravity's MCP config:

**Windows:** `%APPDATA%\Antigravity\mcp_config.json`
**macOS/Linux:** `~/.config/antigravity/mcp_config.json`

```json
{
  "mcpServers": {
    "syncmcp": {
      "command": "python",
      "args": ["-m", "syncmcp.server"]
    }
  }
}
```

#### Antigravity-specific notes

**Tool limit warning:** Antigravity recommends keeping total enabled tools across all MCP servers to ~25 for stability and warns above 50. SyncMCP only has 5 tools so you're fine — but keep this in mind if running GitHub MCP, Firebase MCP, etc. alongside it.

**Custom instructions** (Settings → Agent → Custom Instructions):

```
At the start of every task, call get_context with the current task description.
Before ending a session, call save_note to record what was completed.
When you hit an error and fix it, call save_note with format "error -> fix".
```

**`ag-ask` complement:** Antigravity's `ag-ask` routes questions to module agents grounded in the active codebase. SyncMCP's `search_memory` does the same thing for your **personal knowledge** across all projects. The two complement each other — `ag-ask` for codebase questions, `search_memory` for your cross-project decisions and fixes.

**Debug connection issues:** Check MCP server logs at `~/.config/antigravity/logs/mcp-*.log`. Use `ctx context --copy` as a fallback if the MCP connection drops.

---

### Codex (OpenAI CLI)

Codex doesn't support MCP natively. Use the CLI paste method:

```cmd
ctx context --query "what I'm working on" --copy
```

Then paste the clipboard contents at the top of your Codex prompt. This is the "CLI paste" node in the architecture diagram.

To save learnings from a Codex session:

```cmd
ctx save "learned that JWT refresh tokens go in httpOnly cookies"
ctx save --store errors "TypeError: null is not iterable -> Added null check before .map()"
```

---

### Web Agents (ChatGPT, Kimi, Gemini web)

Same paste flow as Codex — these agents are sandboxed in the browser and can't call MCP directly:

```cmd
:: Generate context and copy to clipboard
ctx context --query "building REST API with auth" --copy

:: Paste into the chat window
```

To save back from a web session, copy the key learnings and run:

```cmd
ctx save "decided to use Passport.js over custom auth middleware"
```

---

### SSE Transport (HTTP-based agents)

If an agent needs an HTTP endpoint instead of stdio:

```bash
python -m syncmcp.server --transport sse --port 8765
```

Then point the agent to `http://127.0.0.1:8765/sse`. This also works for the MCP Inspector:

```bash
# Open the MCP Inspector UI to test tools manually
python -m mcp dev src/syncmcp/server.py
```

---

## Summary: Which config to use

| Agent | Method | Config file / command |
|-------|--------|----------------------|
| **Claude Code** | MCP (stdio) | `claude mcp add syncmcp -- python -m syncmcp.server` |
| **Claude Desktop** | MCP (stdio) | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Cursor** | MCP (stdio) | `.cursor/mcp.json` |
| **VS Code + Copilot** | MCP (stdio) | `.vscode/mcp.json` (VS Code 1.99+) |
| **Antigravity** | MCP (stdio) | `%APPDATA%\Antigravity\mcp_config.json` |
| **Codex** | CLI paste | `ctx context --copy` then paste |
| **ChatGPT / Kimi / Gemini** | CLI paste | `ctx context --copy` then paste |
| **HTTP agents** | MCP (SSE) | `python -m syncmcp.server --transport sse` |

---

## Installing the Git Hook

### Automatic (recommended)

`ctx init` automatically installs the post-commit hook when you initialize a project:

```bash
cd my-project
ctx init
# Output includes: [OK] Git post-commit hook installed
```

If a non-SyncMCP hook already exists, it warns instead of overwriting. Use `--force` to override:

```bash
ctx init --force
```

### Manual install

```bash
# Copy the hook (Windows CMD)
copy d:\NexiEvolv\Projects\SyncMCP\hooks\post-commit.py .git\hooks\post-commit

# Copy the hook (Git Bash / macOS / Linux)
cp /path/to/SyncMCP/hooks/post-commit.py .git/hooks/post-commit
chmod +x .git/hooks/post-commit
```

### Global hook (all repos)

```bash
git config --global core.hooksPath /path/to/SyncMCP/hooks
```

> **Warning:** This replaces hooks for ALL your git repos.

---

## Syncing the Global Store

Your global preferences, patterns, and error index can be synced via git:

```bash
# Set up a remote (one-time)
ctx sync init https://github.com/yourusername/agent-memory.git

# Push changes
ctx sync push

# Pull on a new machine
ctx sync pull

# Check status
ctx sync status
```

The `global.db` (SQLite) is excluded from sync — it's rebuilt automatically from the source markdown files and `errors.jsonl`.

Project-level `context/` folders sync automatically since they're committed with your code.

---

## Verification Checklist

```bash
# 1. CLI works
ctx --version                    # Should print: ctx, version 0.1.0

# 2. Global store exists
ctx status                       # Should show global store at C:\AgentMemory

# 3. Project init works
cd your-project
ctx init                         # Creates context/ + installs hook

# 4. Save and search
ctx save "test note"
ctx search "test"

# 5. Error indexing
ctx save --store errors "TypeError: null -> Added null check"
ctx lookup "TypeError"           # Should find the error

# 6. Context generation
ctx context --query "setup"      # Prints full context block

# 7. File map
ctx files --print-only           # Shows annotated tree

# 8. MCP server
python -m syncmcp.server --help  # Shows --transport and --port flags
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MEMORY_ROOT` | `C:\AgentMemory` | Location of the global store |
| `PYTHONIOENCODING` | (system) | Set to `utf-8` if you see encoding errors |

### Customizing Global Preferences

Edit these files directly — they're plain markdown, picked up on next `get_context` call:

```
C:\AgentMemory\
├── preferences.md       <- Response format, coding style, tone
├── arch_patterns.md     <- Patterns you always follow
└── tech_stack.md        <- "Always use X over Y" decisions
```

---

## Troubleshooting

### `ctx` command not found

```cmd
:: Add Python Scripts to PATH (Windows)
set PATH=%PATH%;%USERPROFILE%\AppData\Local\Programs\Python\Python313\Scripts

:: Or run directly
python -m syncmcp.cli --version
```

### Unicode encoding errors on Windows

```cmd
set PYTHONIOENCODING=utf-8
ctx status
```

Or use `setup.bat` which sets this automatically.

### MCP server not connecting

1. Test manually: `python -m syncmcp.server` (should start without errors)
2. Check config file path and JSON syntax
3. Restart your IDE (Claude Desktop requires full restart)
4. Test with inspector: `python -m mcp dev src/syncmcp/server.py`

### SQLite database corrupted

```bash
ctx rebuild-index    # Rebuilds from errors.jsonl (source of truth)
```

### Git hook not running

```bash
# Check if hook exists
ls .git/hooks/post-commit

# Re-install
ctx init --force
```

---

## Updating SyncMCP

```bash
cd SyncMCP
git pull
pip install -e .
```

Memory stores are never touched by updates.
