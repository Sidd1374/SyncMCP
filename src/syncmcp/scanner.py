"""Scanner module — AI-powered codebase ingestion.

Reads your whole codebase and automatically populates:
- context/arch.md       (Architecture & tech stack)
- context/theme.md      (UI/UX & design patterns)
- context/active_task.md (Current state & next steps)
- context/errors.md      (TODOs, FIXMEs, and known issues)

Requires an LLM API key (defaults to Gemini or Anthropic).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from syncmcp import file_mapper, project_store


class CodeScanner:
    def __init__(self, project_path: str | Path | None = None):
        self.root = project_store.detect_project_root(project_path)
        if self.root is None:
            raise FileNotFoundError("Could not detect project root.")
        self.gitignore = file_mapper._parse_gitignore(self.root)

    def scan_todos(self) -> str:
        """Find TODOs and FIXMEs using regex (no AI needed)."""
        todos: list[str] = ["# Known Issues & TODOs (Auto-scanned)\n"]
        
        # Walk files
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
                
            # Skip the .context folder itself
            if ".context" in path.parts:
                continue

            # Respect all skip rules from file_mapper
            # We check if any parent is in the skip list
            skip = False
            for parent in path.parents:
                if parent == self.root:
                    break
                if file_mapper._should_skip(parent, self.root, self.gitignore):
                    skip = True
                    break
            
            if skip or file_mapper._should_skip(path, self.root, self.gitignore):
                continue
                
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    if any(k in line for k in ["TODO:", "FIXME:", "BUG:", "HACK:"]):
                        # Skip the scanner's own code detection lines
                        if "if any(k in line" in line and "scanner.py" in str(path):
                            continue
                            
                        clean_line = line.strip().lstrip("/#* ")
                        rel_path = path.relative_to(self.root)
                        todos.append(f"- [{rel_path}:{i+1}] {clean_line}")
            except Exception:
                continue

        if len(todos) == 1:
            todos.append("_No pending TODOs found in codebase._")
            
        return "\n".join(todos)

    def prepare_codebase_summary(self, max_chars: int = 30000) -> str:
        """Collect key file contents to send to the AI."""
        summary: list[str] = []
        current_chars = 0
        
        # Priority 1: Config files & README
        # Priority 2: main/index files
        # Priority 3: everything else (up to limit)
        
        all_files = []
        for path in self.root.rglob("*"):
            if path.is_file() and not file_mapper._should_skip(path, self.root, self.gitignore):
                all_files.append(path)

        # Sort by importance (shorter paths, config names first)
        all_files.sort(key=lambda p: (len(p.parts), p.name.lower()))

        for path in all_files:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                rel_path = path.relative_to(self.root)
                snippet = f"--- FILE: {rel_path} ---\n{content}\n"
                
                if current_chars + len(snippet) > max_chars:
                    summary.append(f"... (limit reached, skipping {len(all_files) - all_files.index(path)} files)")
                    break
                    
                summary.append(snippet)
                current_chars += len(snippet)
            except Exception:
                continue

        return "\n".join(summary)

    def ai_summarize(self, api_key: str | None = None) -> dict[str, str]:
        """Send codebase to LLM (Gemini, OpenAI, Anthropic, or Ollama) via LiteLLM."""
        import litellm
        from dotenv import load_dotenv
        
        # Load .env if present
        load_dotenv(self.root / ".env")
        
        # Priority: SYNC_MODEL > env variables
        model_name = os.getenv("SYNC_MODEL", "gemini/gemini-1.5-flash")
        
        # Check for keys based on model
        if "gemini" in model_name and not os.getenv("GEMINI_API_KEY"):
             return {"error": "No GEMINI_API_KEY found in .env or environment."}
        if "gpt" in model_name and not os.getenv("OPENAI_API_KEY"):
             return {"error": "No OPENAI_API_KEY found in .env or environment."}
        if "claude" in model_name and not os.getenv("ANTHROPIC_API_KEY"):
             return {"error": "No ANTHROPIC_API_KEY found in .env or environment."}

        print(f"🤖 AI Summarizer starting ({model_name})...")
        code_bundle = self.prepare_codebase_summary()
        tree = file_mapper.generate_tree(self.root)
        
        prompt = f"""
You are an expert software architect. Analyze the following codebase and generate three concise markdown documents.

PROJECT TREE:
{tree}

CODEBASE SNIPPETS:
{code_bundle}

OUTPUT FORMAT (Exactly as follows with triple backticks and labels):

```arch
# Architecture
(Describe stack, high-level structure, core logic)
```

```theme
# Theme & UI
(Describe styling, UI components, design patterns)
```

```task
# Active Task
(Describe current state and next steps)
```
"""

        try:
            # Universal completion call
            response = litellm.completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                api_key=api_key, # Can be None if set in environment
                # For Ollama, we don't need many extra params
            )
            text = response.choices[0].message.content
            
            # Parse sections using regex
            arch = re.search(r"```arch\n(.*?)\n```", text, re.DOTALL)
            theme = re.search(r"```theme\n(.*?)\n```", text, re.DOTALL)
            task = re.search(r"```task\n(.*?)\n```", text, re.DOTALL)
            
            return {
                "arch": arch.group(1) if arch else "# Architecture\n(Parsing failed)",
                "theme": theme.group(1) if theme else "# Theme\n(Parsing failed)",
                "task": task.group(1) if task else "# Active Task\n(Parsing failed)"
            }
        except Exception as e:
            return {"error": f"AI call failed ({model_name}): {str(e)}"}

    def _mock_ai_call(self, prompt: str) -> dict[str, str]:
        # This is now handled by ai_summarize
        return {}


def run_scan(project_path: str | Path | None = None, deep: bool = False) -> str:
    """Run a full scan and update all context stores."""
    scanner = CodeScanner(project_path)
    
    # 1. Update File Map (standard)
    file_mapper.update_file_map(scanner.root)
    
    # 2. Update Errors (TODOs)
    todos = scanner.scan_todos()
    project_store.write_store("errors", todos, scanner.root, mode="replace")
    
    # 3. AI Update (optional)
    if deep:
        results = scanner.ai_summarize()
        if "error" in results:
            return f"✓ TODOs scanned, but AI failed: {results['error']}"
        
        for store in ["arch", "theme", "active_task"]:
            if store in results:
                project_store.write_store(store, results[store], scanner.root, mode="replace")
        
        return f"✓ Deep scan complete! Updated file_map, architecture, theme, and tasks."

    # Standard scan initializes files if empty
    for store in ["arch", "theme", "active_task"]:
        content = project_store.read_store(store, scanner.root)
        if not content or "empty" in content.lower() or "run 'ctx scan'" in content.lower():
            placeholder = f"# {store.replace('_', ' ').title()}\nAuto-generated placeholder. Use 'ctx save' or 'ctx scan --deep' to fill."
            project_store.write_store(store, placeholder, scanner.root, mode="replace")

    return f"✓ Codebase scanned. Updated file_map.md and errors.md with {todos.count('- [')} TODOs."

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else None
    print(run_scan(path))
