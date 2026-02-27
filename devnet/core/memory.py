"""
Memory - Persistent key-value store for the agent
Stored at ~/.devnet/memory.json
"""

import json
import os
from devnet.core.config import MEMORY_PATH


class Memory:
    def __init__(self, path: str = None):
        self.path = path or MEMORY_PATH
        self._data: dict = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _persist(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def save(self, key: str, value: str) -> str:
        self._data[key] = value
        self._persist()
        return f"Saved '{key}' to memory."

    def get(self, key: str) -> str:
        return self._data.get(key, f"[MEMORY] Key '{key}' not found.")

    def list_keys(self) -> str:
        if not self._data:
            return "[MEMORY] Empty."
        return "\n".join(f"  • {k}: {str(v)[:80]}" for k, v in self._data.items())

    def clear(self):
        self._data = {}
        self._persist()

    def all(self) -> dict:
        return self._data.copy()
