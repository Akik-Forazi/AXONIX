"""
DevNet History — JSONL persistence for chats
"""

import json
import os
from datetime import datetime

class ChatHistory:
    def __init__(self, workspace: str):
        self.log_dir = os.path.join(workspace, ".devnet", "history")
        os.makedirs(self.log_dir, exist_ok=True)
        self.current_file = os.path.join(self.log_dir, f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")

    def append(self, role: str, content: str, **kwargs):
        """Append a message to the JSONL log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            **kwargs
        }
        with open(self.current_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + " ")

    def get_sessions(self) -> list[str]:
        """List all history files."""
        if not os.path.exists(self.log_dir): return []
        return sorted([f for f in os.listdir(self.log_dir) if f.endswith(".jsonl")], reverse=True)

    def load_session(self, filename: str) -> list[dict]:
        """Load messages from a specific file."""
        path = os.path.join(self.log_dir, filename)
        messages = []
        if not os.path.exists(path): return []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    messages.append(json.loads(line))
        return messages
