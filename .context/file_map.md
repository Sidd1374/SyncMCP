# File Map — SyncMCP

_Auto-generated on 2026-04-30 00:46_

```
├── Docs/
│   ├── AGENTS.md
│   ├── agents_md.py
│   ├── CLAUDE.md
│   ├── cli.py
│   ├── cursorrules.txt
│   ├── project_store.py
│   ├── scanner.py
│   ├── server.py  # Server entry point
│   └── SETUP.md
├── hooks/
│   ├── post-commit
│   └── post-commit.py
├── src/
│   └── syncmcp/
│       ├── __init__.py  # SyncMCP — Two-scope agent memory system with MCP server.
│       ├── agents_md.py  # Agents.md module — generates unified AI agent rules.
│       ├── cli.py
│       ├── error_index.py
│       ├── file_mapper.py
│       ├── global_store.py
│       ├── hub.py
│       ├── project_store.py
│       ├── scanner.py  # Scanner module — AI-powered codebase ingestion.
│       ├── server.py  # Server entry point
│       ├── session.py
│       └── sync.py  # Sync module — git-based sync for the global store.
├── .gitignore
├── AGENTS.md
├── pyproject.toml  # Python project config
├── README.md  # Project documentation
├── setup.bat
├── SETUP.md
└── setup.sh
```