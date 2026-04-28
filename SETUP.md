# SyncMCP — Setup Guide

Step-by-step setup for SyncMCP on Windows, macOS, and Linux.

---

## Prerequisites

- **Python 3.11+** — [Download](https://python.org/downloads/)
- **Git** — [Download](https://git-scm.com/downloads)
- **pip** — comes with Python (verify with `pip --version`)

---

## Windows Setup (Recommended)

### Option A: One-command setup

```cmd
cd SyncMCP
setup.bat
```

This will:
1. Verify Python is installed
2. Create `C:\AgentMemory\` with all subfolders
3. Install SyncMCP as an editable package (`pip install -e .`)
4. Initialize the global store with starter templates
5. Verify the `ctx` command is available
6. Print agent configuration instructions

### Option B: Manual setup

```cmd
:: 1. Install the package
cd SyncMCP
pip install -e .

:: 2. Set up global store
ctx setup

:: 3. Initialize your first project
cd your-project
ctx init
```

---

## macOS / Linux Setup

```bash
# 1. Clone and install
git clone https://github.com/yourusername/SyncMCP.git
cd SyncMCP
pip install -e .

# 2. Set the global store location (add to .bashrc / .zshrc)
export AGENT_MEMORY_ROOT="$HOME/.agent-memory"

# 3. Set up global store
ctx setup

# 4. Initialize project context
cd your-project
ctx init
```

> **Note:** On non-Windows systems, set `AGENT_MEMORY_ROOT` environment variable to your preferred location. Default is `C:\AgentMemory\` (Windows-specific).

---

## Agent Configuration

### Claude Code

```bash
claude mcp add syncmcp -- python -m syncmcp.server
```

That's it. Claude Code will automatically discover the 5 tools.

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

Restart Cursor after creating this file.

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

Restart Claude Desktop after editing.

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

### Codex / Other MCP Clients

Use the same JSON pattern — the only thing that changes is the config file path for each client. The server command is always:

```
python -m syncmcp.server
```

### Web Agents (ChatGPT, Kimi, Gemini Web)

Web agents don't support MCP directly. Use the CLI to generate a pasteable context block:

```bash
# Generate context and copy to clipboard
ctx context --query "building a REST API with auth" --copy

# Then paste into your web agent chat
```

For saving notes from a web agent session, copy the key learnings and run:

```bash
ctx save "learned that JWT refresh tokens should be stored in httpOnly cookies"
```

---

## Installing the Git Hook

The post-commit hook auto-updates `file_map.md` after every commit.

### Automatic (per project)

When you run `ctx init`, the hook is NOT auto-installed (to avoid overwriting existing hooks). Install manually:

```bash
# From your project root
cp /path/to/SyncMCP/hooks/post-commit .git/hooks/post-commit
chmod +x .git/hooks/post-commit   # macOS/Linux only
```

### Windows (Git Bash)

```bash
cp /d/NexiEvolv/Projects/SyncMCP/hooks/post-commit .git/hooks/post-commit
```

### Global Git Hook (all projects)

```bash
git config --global core.hooksPath /path/to/SyncMCP/hooks
```

> **Warning:** This replaces hooks for ALL your git repos. Only do this if you want SyncMCP active everywhere.

---

## Verifying the Setup

```bash
# 1. Check ctx is installed
ctx --version

# 2. Check global store
ctx status

# 3. Test a save
ctx save "test note — setup verification"

# 4. Test search
ctx search "test"

# 5. Test error indexing
ctx save --store errors "TypeError: null is not iterable → Added null check before .map()"

# 6. Test cross-project lookup
ctx lookup "TypeError"

# 7. Test context generation
ctx context --query "setup"

# 8. Test file map generation
ctx files --print-only

# 9. Test MCP server (opens inspector UI)
python -m mcp dev src/syncmcp/server.py
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MEMORY_ROOT` | `C:\AgentMemory` | Location of the global store |

### Customizing Global Preferences

Edit these files directly — they're plain markdown:

```
C:\AgentMemory\
├── preferences.md       ← Your response format, coding style, tone
├── arch_patterns.md     ← Patterns you always follow
└── tech_stack.md        ← "Always use X over Y" decisions
```

Changes are picked up immediately by the MCP server on the next `get_context` call.

---

## Troubleshooting

### `ctx` command not found

Python scripts may not be in your PATH. Try:

```cmd
:: Windows
set PATH=%PATH%;%USERPROFILE%\AppData\Local\Programs\Python\Python311\Scripts

:: Or run directly
python -m syncmcp.cli --version
```

### MCP server not connecting

1. Verify the server starts: `python -m syncmcp.server`
2. Check your agent's MCP config file for typos
3. Restart your agent (Claude Desktop requires full restart)
4. Try the MCP inspector: `python -m mcp dev src/syncmcp/server.py`

### SQLite database corrupted

The JSONL file is the source of truth. Rebuild:

```bash
ctx rebuild-index
```

### Context too large

If `ctx context` generates too much text:

```bash
# Filter to specific stores
ctx context --stores active_task,arch

# Or search for something specific
ctx search "auth flow"
```

---

## Updating

```bash
cd SyncMCP
git pull
pip install -e .
```

Your memory stores (`C:\AgentMemory\` and project `context/` folders) are never touched by updates.

---

## Uninstalling

```bash
pip uninstall syncmcp
```

Your memory files at `C:\AgentMemory\` and project `context/` folders are NOT deleted. Remove them manually if desired.
