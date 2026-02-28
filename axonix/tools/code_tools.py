"""
This module provides specialized tools for analyzing and manipulating source code.
It includes capabilities for linting, formatting, structural visualization, 
and high-level architectural analysis of Python projects.
"""

import os
import subprocess
import re


class CodeTools:
    """
    A collection of utilities designed to help AXONIX-ZERO understand 
    and maintain high-quality codebases.
    """
    def __init__(self, workspace: str = "."):
        self.workspace = os.path.abspath(workspace)

    def _resolve(self, path: str) -> str:
        """Translates a relative path into an absolute system path."""
        if os.path.isabs(path):
            return path
        return os.path.join(self.workspace, path)

    def lint(self, path: str) -> str:
        """
        Performs a static analysis check using 'flake8' to identify potential 
        errors or stylistic inconsistencies in Python code.
        """
        full = self._resolve(path)
        try:
            result = subprocess.run(
                ["flake8", full, "--max-line-length=120"],
                capture_output=True, text=True, timeout=30
            )
            out = result.stdout.strip()
            return f"Linting Analysis for {full}:\n{out}" if out else f"No stylistic issues detected in {full}."
        except FileNotFoundError:
            return "The 'flake8' utility is not installed. Please run: pip install flake8"
        except Exception as e:
            return f"An unexpected error occurred during linting: {e}"

    def format_code(self, path: str) -> str:
        """
        Automatically reformats Python source code using the 'black' formatter 
         to ensure compliance with professional coding standards.
        """
        full = self._resolve(path)
        try:
            result = subprocess.run(
                ["black", full],
                capture_output=True, text=True, timeout=30
            )
            return f"Code Formatting Result for {full}:\n{result.stdout or result.stderr}"
        except FileNotFoundError:
            return "The 'black' formatter is not installed. Please run: pip install black"
        except Exception as e:
            return f"Formatting failed due to an error: {e}"

    def tree(self, path: str = ".", max_depth: int = 4) -> str:
        """
        Generates a visual directory structure to help the agent understand 
        the project's physical layout.
        """
        full = self._resolve(path)
        lines = [f"{full}/"]

        def _walk(directory: str, prefix: str, depth: int):
            if depth > max_depth:
                return
            try:
                items = sorted(os.listdir(directory))
            except PermissionError:
                return

            # Exclude non-essential directories to reduce noise.
            ignore = {".git", "__pycache__", "node_modules", ".venv", "venv", ".axonix"}
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

    def analyze(self, path: str = ".") -> str:
        """
        Scans Python source files to extract structural information like classes 
        and function definitions, providing a high-level architectural summary.
        """
        full = self._resolve(path)
        summary = [f"Architectural Overview: {full}"]
        
        files_to_scan = []
        if os.path.isfile(full):
            if full.endswith(".py"):
                files_to_scan.append(full)
        else:
            for root, _, files in os.walk(full):
                # Skip internal data and temporary folders.
                if any(x in root for x in [".git", "__pycache__", ".axonix"]):
                    continue
                for f in files:
                    if f.endswith(".py"):
                        files_to_scan.append(os.path.join(root, f))
        
        if not files_to_scan:
            return f"{summary[0]} - No Python source files were found in this directory."

        for fpath in files_to_scan:
            rel = os.path.relpath(fpath, self.workspace)
            summary.append(f"\nSource File: {rel}")
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("class ") or line.startswith("def "):
                            m = re.match(r"(class|def)\s+(\w+)", line)
                            if m:
                                summary.append(f"  [{m.group(1).upper()}] {m.group(2)}")
            except Exception as e:
                summary.append(f"  [ERROR] Failed to read file structure: {e}")

        return "\n".join(summary)
