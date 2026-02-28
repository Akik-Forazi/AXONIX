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
        # ... (rest of tree code) ...

    def analyze(self, path: str = ".") -> str:
        """Scan Python files and provide an architectural summary (classes/defs)."""
        full = self._resolve(path)
        summary = [f"[ANALYSIS: {full}]"]
        
        files_to_scan = []
        if os.path.isfile(full):
            if full.endswith(".py"):
                files_to_scan.append(full)
        else:
            for root, _, files in os.walk(full):
                if any(x in root for x in [".git", "__pycache__", ".axonix"]):
                    continue
                for f in files:
                    if f.endswith(".py"):
                        files_to_scan.append(os.path.join(root, f))
        
        if not files_to_scan:
            return f"{summary[0]} No Python files found."

        import re
        for fpath in files_to_scan:
            rel = os.path.relpath(fpath, self.workspace)
            summary.append(f"\n📄 {rel}:")
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("class ") or line.startswith("def "):
                            # Capture name and signature start
                            m = re.match(r"(class|def)\s+(\w+)", line)
                            if m:
                                summary.append(f"  {m.group(1)} {m.group(2)}")
            except Exception as e:
                summary.append(f"  [ERROR] {e}")

        return "\n".join(summary)
