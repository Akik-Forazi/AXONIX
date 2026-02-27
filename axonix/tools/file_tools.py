"""
File Tools - Read, write, edit, delete, search files
"""

import os
import glob
import shutil
from pathlib import Path


class FileTools:
    def __init__(self, workspace: str = "."):
        self.workspace = os.path.abspath(workspace)

    def _resolve(self, path: str) -> str:
        """Resolve path relative to workspace."""
        p = Path(path)
        if p.is_absolute():
            return str(p)
        return str(Path(self.workspace) / path)

    def read(self, path: str) -> str:
        full = self._resolve(path)
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            lines = content.split("\n")
            numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
            return f"[FILE: {full}] ({len(lines)} lines)\n{numbered}"
        except FileNotFoundError:
            return f"[ERROR] File not found: {full}"
        except Exception as e:
            return f"[ERROR] {e}"

    def write(self, path: str, content: str) -> str:
        full = self._resolve(path)
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[OK] Written {len(content)} chars to {full}"

    def edit(self, path: str, old: str, new: str) -> str:
        full = self._resolve(path)
        try:
            with open(full, "r", encoding="utf-8") as f:
                content = f.read()
            if old not in content:
                return f"[ERROR] Text not found in {full}:\n{old}"
            count = content.count(old)
            updated = content.replace(old, new)
            with open(full, "w", encoding="utf-8") as f:
                f.write(updated)
            return f"[OK] Replaced {count} occurrence(s) in {full}"
        except FileNotFoundError:
            return f"[ERROR] File not found: {full}"

    def delete(self, path: str) -> str:
        full = self._resolve(path)
        try:
            if os.path.isfile(full):
                os.remove(full)
                return f"[OK] Deleted file: {full}"
            elif os.path.isdir(full):
                shutil.rmtree(full)
                return f"[OK] Deleted directory: {full}"
            else:
                return f"[ERROR] Not found: {full}"
        except Exception as e:
            return f"[ERROR] {e}"

    def list_dir(self, path: str = ".") -> str:
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
            return f"[DIR: {full}]\n" + "\n".join(result) if result else f"[DIR: {full}] (empty)"
        except Exception as e:
            return f"[ERROR] {e}"

    def search(self, path: str = ".", pattern: str = "*") -> str:
        full = self._resolve(path)
        matches = glob.glob(os.path.join(full, "**", pattern), recursive=True)
        if not matches:
            return f"[SEARCH] No files matching '{pattern}' in {full}"
        return f"[SEARCH] Found {len(matches)} file(s):\n" + "\n".join(f"  {m}" for m in matches[:50])

    def append(self, path: str, content: str) -> str:
        full = self._resolve(path)
        with open(full, "a", encoding="utf-8") as f:
            f.write(content)
        return f"[OK] Appended to {full}"

    def copy(self, src: str, dst: str) -> str:
        full_src = self._resolve(src)
        full_dst = self._resolve(dst)
        shutil.copy2(full_src, full_dst)
        return f"[OK] Copied {full_src} → {full_dst}"

    def move(self, src: str, dst: str) -> str:
        full_src = self._resolve(src)
        full_dst = self._resolve(dst)
        shutil.move(full_src, full_dst)
        return f"[OK] Moved {full_src} → {full_dst}"
