"""
This module provides a persistent key-value memory system for AXONIX-ZERO.
It allows the agent to retain important information across sessions, 
enhancing its ability to learn from past interactions and maintain project context.
"""

import json
import os
from axonix.core.config import MEMORY_PATH


class Memory:
    """
    Manages the lifecycle of AXONIX-ZERO's persistent knowledge base.
    Data is stored in a structured JSON format for reliability and interoperability.
    """
    def __init__(self, path: str = None):
        self.path = path or MEMORY_PATH
        self._data: dict = {}
        self._load()

    def _load(self):
        """Initializes the memory state from disk storage."""
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                # If memory is unreadable, we start with a clean state.
                self._data = {}

    def _persist(self):
        """Synchronizes the current memory state to permanent storage."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def save(self, key: str, value: str) -> str:
        """
        Stores a specific fact or data point in memory.
        Returns a confirmation message.
        """
        self._data[key] = value
        self._persist()
        return f"Information successfully retained under '{key}'."

    def get(self, key: str) -> str:
        """Retrieves a specific value from memory by its unique identifier."""
        return self._data.get(key, f"Record '{key}' not found in active memory.")

    def list_keys(self) -> str:
        """Provides a formatted summary of all currently stored knowledge."""
        if not self._data:
            return "Active memory is currently empty."
        lines = ["Current Knowledge Base:"]
        for k, v in self._data.items():
            lines.append(f"  • {k}: {str(v)[:100]}...")
        return "\n".join(lines)

    def clear(self):
        """Permanently erases all stored knowledge."""
        self._data = {}
        self._persist()

    def all(self) -> dict:
        """Returns a snapshot of the entire memory dictionary."""
        return self._data.copy()
