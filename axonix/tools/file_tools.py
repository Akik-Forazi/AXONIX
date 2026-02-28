"""
This module provides a robust suite of tools for file system interaction.
It handles reading, writing, editing, and managing files and directories
within the user's workspace, ensuring safe and predictable I/O operations.
"""

import os
import glob
import shutil
from pathlib import Path


class FileTools:
    """
    A comprehensive set of file manipulation utilities designed for 
    high-reliability autonomous agent operations.
    """
    def __init__(self, workspace: str = "."):
        self.workspace = os.path.abspath(workspace)

    def _resolve(self, path: str) -> str:
        """
        Determines the absolute system path for a given file or directory,
        defaulting to the project workspace for relative paths.
        """
        p = Path(path)
        if p.is_absolute():
            return str(p)
        return str(Path(self.workspace) / path)

    def read(self, path: str) -> str:
        """
        Reads the content of a file and returns it with professional line numbering.
        This helps the agent reference specific sections of code accurately.
        """
        full = self._resolve(path)
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            lines = content.split("\n")
            numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
            return f"Reading {full} ({len(lines)} lines):\n{numbered}"
        except FileNotFoundError:
            return f"Error: The file at {full} could not be found."
        except Exception as e:
            return f"Error: Unable to read file {full}. {e}"

    def write(self, path: str, content: str) -> str:
        """
        Creates or overwrites a file with the provided content.
        Automatically creates parent directories if they don't already exist.
        """
        full = self._resolve(path)
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully saved {len(content)} characters to {full}."

    def edit(self, path: str, old: str, new: str) -> str:
        """
        Performs a precise search-and-replace operation within a specific file.
        """
        full = self._resolve(path)
        try:
            with open(full, "r", encoding="utf-8") as f:
                content = f.read()
            if old not in content:
                return f"Error: The target text segment was not found in {full}."
            count = content.count(old)
            updated = content.replace(old, new)
            with open(full, "w", encoding="utf-8") as f:
                f.write(updated)
            return f"Successfully updated {count} occurrence(s) in {full}."
        except FileNotFoundError:
            return f"Error: File not found during edit operation: {full}"

    def delete(self, path: str) -> str:
        """
        Permanently removes a file or directory from the system.
        """
        full = self._resolve(path)
        try:
            if os.path.isfile(full):
                os.remove(full)
                return f"File removed: {full}"
            elif os.path.isdir(full):
                shutil.rmtree(full)
                return f"Directory removed: {full}"
            else:
                return f"Error: Target path {full} does not exist."
        except Exception as e:
            return f"Error: Failed to delete {full}. {e}"

    def list_dir(self, path: str = ".") -> str:
        """
        Provides a detailed inventory of items within a directory,
        including file sizes for better situational awareness.
        """
        full = self._resolve(path)
        try:
            items = sorted(os.listdir(full))
            result = []
            for item in items:
                item_path = os.path.join(full, item)
                if os.path.isdir(item_path):
                    result.append(f"  [DIR]  {item}/")
                else:
                    size = os.path.getsize(item_path)
                    result.append(f"  [FILE] {item}  ({size} bytes)")
            return f"Contents of {full}:\n" + "\n".join(result) if result else f"The directory {full} is currently empty."
        except Exception as e:
            return f"Error: Unable to list directory {full}. {e}"

    def search(self, path: str = ".", pattern: str = "*") -> str:
        """
        Locates files matching a specific pattern recursively throughout the directory tree.
        """
        full = self._resolve(path)
        matches = glob.glob(os.path.join(full, "**", pattern), recursive=True)
        if not matches:
            return f"Search result: No items matching '{pattern}' were found in {full}."
        return f"Search result: Found {len(matches)} item(s):\n" + "\n".join(f"  {m}" for m in matches[:50])

    def append(self, path: str, content: str) -> str:
        """Adds new content to the end of an existing file."""
        full = self._resolve(path)
        with open(full, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended new data to {full}."

    def copy(self, src: str, dst: str) -> str:
        """Creates a duplicate of a file or directory at a new location."""
        full_src = self._resolve(src)
        full_dst = self._resolve(dst)
        shutil.copy2(full_src, full_dst)
        return f"Successfully copied {full_src} to {full_dst}."

    def move(self, src: str, dst: str) -> str:
        """Relocates a file or directory to a different path."""
        full_src = self._resolve(src)
        full_dst = self._resolve(dst)
        shutil.move(full_src, full_dst)
        return f"Successfully moved {full_src} to {full_dst}."
