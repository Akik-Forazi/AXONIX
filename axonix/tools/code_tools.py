"""
Code Tools - Lint, format, tree view
"""

import os
import subprocess


class CodeTools:
    def __init__(self, workspace: str = "."):
        self.workspace = os.path.abspath(workspace)

    def _resolve(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.join(self.workspace, path)

    def lint(self, path: str) -> str:
        """Lint a Python file with flake8 (if installed) or basic checks."""
        full = self._resolve(path)
        try:
            result = subprocess.run(
                ["flake8", full, "--max-line-length=120"],
                capture_output=True, text=True, timeout=30
            )
            out = result.stdout.strip()
            return f"[LINT: {full}]\n{out}" if out else f"[LINT: {full}] No issues found."
        except FileNotFoundError:
            return "[LINT] flake8 not installed. Run: pip install flake8"
        except Exception as e:
            return f"[LINT ERROR] {e}"

    def format_code(self, path: str) -> str:
        """Format a Python file with black (if installed)."""
        full = self._resolve(path)
        try:
            result = subprocess.run(
                ["black", full],
                capture_output=True, text=True, timeout=30
            )
            return f"[FORMAT: {full}]\n{result.stdout or result.stderr}"
        except FileNotFoundError:
            return "[FORMAT] black not installed. Run: pip install black"
        except Exception as e:
            return f"[FORMAT ERROR] {e}"

    def tree(self, path: str = ".", max_depth: int = 4) -> str:
        """Generate a tree view of a directory."""
        full = self._resolve(path)
        lines = [f"{full}/"]

        def _walk(directory: str, prefix: str, depth: int):
            if depth > max_depth:
                return
            try:
                items = sorted(os.listdir(directory))
            except PermissionError:
                return

            # Filter common noise
            ignore = {".git", "__pycache__", "node_modules", ".venv", "venv", ".axonix_memory.json"}
            items = [i for i in items if i not in ignore]

            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                full_path = os.path.join(directory, item)
                lines.append(f"{prefix}{connector}{item}")
                if os.path.isdir(full_path):
                    extension = "    " if is_last else "│   "
                    _walk(full_path, prefix + extension, depth + 1)

        _walk(full, "", 1)
        return "\n".join(lines)
