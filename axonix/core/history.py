"""
This module manages the persistent storage of user conversations and agent activities.
It uses the JSONL (JSON Lines) format to ensure that logs are durable, 
append-only, and easily recoverable even if a session is interrupted.
"""

import json
import os
from datetime import datetime

class ChatHistory:
    """
    Handles the recording and retrieval of historical session data.
    Every interaction is timestamped and stored in the dedicated history folder.
    """
    def __init__(self, workspace: str):
        # We store history in a hidden folder within the project workspace.
        self.log_dir = os.path.join(workspace, ".axonix", "history")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # We generate a unique filename for the current session based on the current time.
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.current_file = os.path.join(self.log_dir, f"chat_{timestamp}.jsonl")

    def append(self, role: str, content: str, **kwargs):
        """
        Records a new message or event into the active session log.
        Supports additional metadata via keyword arguments.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            **kwargs
        }
        with open(self.current_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def get_sessions(self) -> list[str]:
        """
        Retrieves a list of all recorded session files, sorted by the most recent.
        Useful for auditing or resuming past conversations.
        """
        if not os.path.exists(self.log_dir):
            return []
        files = [f for f in os.listdir(self.log_dir) if f.endswith(".jsonl")]
        return sorted(files, reverse=True)

    def load_session(self, filename: str) -> list[dict]:
        """
        Loads and parses all entries from a specific historical session file.
        """
        path = os.path.join(self.log_dir, filename)
        messages = []
        if not os.path.exists(path):
            return []
        
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Skip corrupted lines to preserve as much history as possible.
                        continue
        return messages
