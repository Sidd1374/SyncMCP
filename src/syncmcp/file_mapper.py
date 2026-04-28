"""File mapper — auto-generates file_map.md by walking the project tree.

Respects .gitignore patterns, detects key files, and generates a clean
annotated tree for agent context.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from syncmcp import project_store

# Directories always excluded (even if not in .gitignore)
_ALWAYS_SKIP = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    ".idea", ".vscode", "dist", "build", ".next", ".nuxt",
    ".dart_tool", ".flutter-plugins", ".eggs", "*.egg-info",
    ".tox", ".mypy_cache", ".pytest_cache", ".coverage",
    "coverage", ".gradle", ".android", ".ios",
}

# File extensions to skip
_SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".exe",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".wav", ".avi",
    ".zip", ".tar", ".gz", ".rar",
    ".woff", ".woff2", ".ttf", ".eot",
    ".lock",
}

# Key file patterns and their descriptions
_KEY_FILE_PATTERNS: list[tuple[str, str]] = [
    ("main.py", "Application entry point"),
    ("main.dart", "Flutter app entry point"),
    ("app.py", "Application entry point"),
    ("server.py", "Server entry point"),
    ("index.ts", "Module entry point"),
    ("index.js", "Module entry point"),
    ("index.html", "Web entry point"),
    ("package.json", "Node.js project config"),
    ("pyproject.toml", "Python project config"),
    ("pubspec.yaml", "Flutter/Dart project config"),
    ("Cargo.toml", "Rust project config"),
    ("go.mod", "Go module config"),
    ("Dockerfile", "Container build config"),
    ("docker-compose.yml", "Multi-container config"),
    (".env", "Environment variables"),
    (".env.example", "Environment template"),
    ("README.md", "Project documentation"),
    ("Makefile", "Build automation"),
    ("setup.py", "Python setup script"),
    ("requirements.txt", "Python dependencies"),
    ("tsconfig.json", "TypeScript config"),
    ("vite.config.ts", "Vite bundler config"),
    ("next.config.js", "Next.js config"),
    ("tailwind.config.js", "Tailwind CSS config"),
]


def _parse_gitignore(project_root: Path) -> list[str]:
    """Parse .gitignore and return a list of glob patterns to ignore."""
    gitignore = project_root / ".gitignore"
    if not gitignore.exists():
        return []

    patterns = []
    for line in gitignore.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _should_skip(path: Path, project_root: Path, gitignore_patterns: list[str]) -> bool:
    """Check if a path should be skipped based on exclusion rules."""
    name = path.name

    # Always-skip directories
    if name in _ALWAYS_SKIP:
        return True

    # Skip hidden files/dirs (except important ones)
    if name.startswith(".") and name not in (".env", ".env.example", ".gitignore"):
        return True

    # Skip by extension
    if path.is_file() and path.suffix.lower() in _SKIP_EXTENSIONS:
        return True

    # Basic gitignore matching (simplified — handles most common patterns)
    rel = str(path.relative_to(project_root)).replace("\\", "/")
    for pattern in gitignore_patterns:
        pattern_clean = pattern.rstrip("/")
        if pattern_clean in rel or rel.startswith(pattern_clean):
            return True

    return False


def _get_annotation(path: Path) -> str:
    """Try to generate a brief annotation for a file."""
    name = path.name

    # Check against known key file patterns
    for pattern, desc in _KEY_FILE_PATTERNS:
        if name == pattern:
            return desc

    # Try to read the first docstring or comment
    if path.suffix in (".py", ".dart", ".ts", ".js", ".go", ".rs"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:500]

            # Python docstring
            match = re.search(r'"""(.+?)"""', text, re.DOTALL)
            if match:
                first_line = match.group(1).strip().split("\n")[0]
                if len(first_line) <= 60:
                    return first_line

            # Single-line comment at top
            for line in text.split("\n")[:5]:
                line = line.strip()
                if line.startswith(("//", "#")) and not line.startswith(("#!")):
                    comment = line.lstrip("/#").strip()
                    if 5 < len(comment) <= 60:
                        return comment
                    break
        except (OSError, UnicodeDecodeError):
            pass

    return ""


def generate_tree(
    project_path: str | Path | None = None,
    max_depth: int = 4,
    annotate: bool = True,
) -> str:
    """Generate a file tree for the project.

    Args:
        project_path: Project root. Auto-detects if None.
        max_depth: Maximum directory depth to traverse
        annotate: Whether to add annotations for key files

    Returns:
        Formatted tree as a string.
    """
    if project_path:
        root = Path(project_path).resolve()
    else:
        root = project_store.detect_project_root()
        if root is None:
            raise FileNotFoundError("Could not detect project root.")

    gitignore = _parse_gitignore(root)
    lines: list[str] = [f"# File Map — {root.name}\n"]
    lines.append(f"_Auto-generated on {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}_\n")
    lines.append("```")

    def _walk(directory: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return

        # Get sorted entries: directories first, then files
        try:
            entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        # Filter out skipped entries
        entries = [e for e in entries if not _should_skip(e, root, gitignore)]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "

            if entry.is_dir():
                child_count = sum(1 for _ in entry.iterdir()) if entry.exists() else 0
                lines.append(f"{prefix}{connector}{entry.name}/")
                _walk(entry, prefix + extension, depth + 1)
            else:
                annotation = ""
                if annotate:
                    ann = _get_annotation(entry)
                    if ann:
                        annotation = f"  # {ann}"
                lines.append(f"{prefix}{connector}{entry.name}{annotation}")

    _walk(root, "", 0)
    lines.append("```")

    return "\n".join(lines)


def update_file_map(project_path: str | Path | None = None) -> str:
    """Generate the file tree and write it to context/file_map.md.

    Returns:
        Confirmation message.
    """
    tree = generate_tree(project_path)
    result = project_store.write_store("file_map", tree, project_path, mode="replace")
    return f"✓ Updated file_map.md ({tree.count(chr(10))} lines)"


# Allow running as a module: python -m syncmcp.file_mapper <project_path>
if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else None
    print(update_file_map(path))
