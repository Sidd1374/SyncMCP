"""Session tracker — monitors context usage and auto-flushes snapshots.

Tracks total characters written during the current MCP session.
When accumulated context exceeds ~80% of a typical context window,
compresses and saves a snapshot so nothing is lost.

Token estimation: len(text) / 4 (simple heuristic, no tokenizer dependency).
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from syncmcp import project_store

# Approximate context window sizes (in characters, ~4 chars per token)
CONTEXT_WINDOW_CHARS = 400_000  # ~100K tokens
FLUSH_THRESHOLD = 0.80  # Flush at 80% of context window


class SessionTracker:
    """Tracks session context accumulation and triggers auto-flush."""

    def __init__(self, project_path: str | Path | None = None) -> None:
        self._project_path = project_path
        self._buffer: list[dict[str, Any]] = []
        self._total_chars: int = 0
        self._flush_count: int = 0
        self._started_at: str = datetime.now(timezone.utc).isoformat()

    @property
    def usage_pct(self) -> float:
        """Current context usage as a percentage."""
        return (self._total_chars / CONTEXT_WINDOW_CHARS) * 100

    @property
    def should_flush(self) -> bool:
        """Whether the session should auto-flush (>80% of context window)."""
        return self._total_chars >= int(CONTEXT_WINDOW_CHARS * FLUSH_THRESHOLD)

    def track(self, content: str, source: str = "unknown") -> dict[str, Any]:
        """Track a piece of content written during this session.

        Args:
            content: The content that was written
            source: Where it came from (tool name, CLI, etc.)

        Returns:
            Status dict with usage info and whether a flush occurred.
        """
        char_count = len(content)
        self._total_chars += char_count
        self._buffer.append({
            "content": content,
            "source": source,
            "chars": char_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        result = {
            "chars_added": char_count,
            "total_chars": self._total_chars,
            "usage_pct": round(self.usage_pct, 1),
            "flushed": False,
        }

        # Auto-flush if threshold exceeded
        if self.should_flush:
            self.flush()
            result["flushed"] = True
            result["total_chars"] = self._total_chars

        return result

    def flush(self, label: str | None = None) -> str:
        """Compress and save the session buffer to a snapshot.

        Returns:
            Path to the created snapshot file, or a message if buffer is empty.
        """
        if not self._buffer:
            return "Nothing to flush — session buffer is empty."

        self._flush_count += 1

        # Compress: deduplicate similar entries, keep most recent
        compressed = self._compress()

        # Build snapshot content
        lines = [
            f"## Session #{self._flush_count} — {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
            f"_Characters tracked: {self._total_chars:,} ({self.usage_pct:.0f}% of context window)_\n",
        ]

        # Group by source
        by_source: dict[str, list[str]] = {}
        for entry in compressed:
            source = entry.get("source", "unknown")
            by_source.setdefault(source, []).append(entry["content"])

        for source, contents in by_source.items():
            lines.append(f"### From: {source}")
            for content in contents:
                # Truncate very long entries
                if len(content) > 500:
                    content = content[:500] + "..."
                lines.append(f"- {content}")
            lines.append("")

        snapshot_content = "\n".join(lines)

        # Save snapshot
        try:
            path = project_store.save_snapshot(
                snapshot_content,
                self._project_path,
                label=label or f"session-{self._flush_count}",
            )
        except FileNotFoundError:
            # No project context folder — save to temp
            path = "(no project context — snapshot not saved)"

        # Reset buffer but keep total for stats
        self._buffer.clear()
        self._total_chars = 0

        return f"✓ Flushed session to {path}"

    def _compress(self) -> list[dict[str, Any]]:
        """Deduplicate and compress the session buffer."""
        seen: set[str] = set()
        compressed: list[dict[str, Any]] = []

        # Walk backwards (newest first) and deduplicate
        for entry in reversed(self._buffer):
            # Use first 100 chars as a dedup key
            key = entry["content"][:100].strip()
            if key not in seen:
                seen.add(key)
                compressed.append(entry)

        compressed.reverse()
        return compressed

    def status(self) -> dict[str, Any]:
        """Get current session status."""
        return {
            "started_at": self._started_at,
            "total_chars": self._total_chars,
            "estimated_tokens": self._total_chars // 4,
            "usage_pct": round(self.usage_pct, 1),
            "entries_buffered": len(self._buffer),
            "flushes": self._flush_count,
            "should_flush": self.should_flush,
        }


# Module-level singleton — created when MCP server starts
_session: SessionTracker | None = None


def get_session(project_path: str | Path | None = None) -> SessionTracker:
    """Get or create the global session tracker."""
    global _session
    if _session is None:
        _session = SessionTracker(project_path)
    return _session


def reset_session(project_path: str | Path | None = None) -> SessionTracker:
    """Reset the global session tracker."""
    global _session
    _session = SessionTracker(project_path)
    return _session


# Allow running as a module for flush: python -m syncmcp.session --flush <project_path>
if __name__ == "__main__":
    if "--flush" in sys.argv:
        path = sys.argv[sys.argv.index("--flush") + 1] if len(sys.argv) > sys.argv.index("--flush") + 1 else None
        session = get_session(path)
        print(session.flush(label="git-hook"))
    else:
        session = get_session()
        print(session.status())
