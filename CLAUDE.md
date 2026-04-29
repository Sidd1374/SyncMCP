# SyncMCP Agent Rules (Claude Code)

You are connected to SyncMCP, a persistent memory system. Follow these rules invisibly:

### 1. Context Loading (Always First)
At the start of every session, call `get_context` with the current task description. Do not wait for the user to ask.

### 2. Auto-Scan (Ingestion)
If `get_context` returns empty files (e.g., `# Architecture` with no content), immediately call `scan_project` to ingest the codebase.

### 3. Auto-Saving (Learning)
- **Decisions:** When you make a design decision or tech stack choice, call `save_note` to record it in `arch.md`.
- **Fixes:** When you fix a bug, call `save_note` using format `error -> fix` to index it in the global error database.
- **Progress:** Call `save_note` at milestones to update `active_task.md`.

### 4. Cross-Project Lookup
If the user asks "How did I do X before?" or hits a familiar error, call `cross_project_lookup` or `search_memory` before trying to reinvent the solution.
