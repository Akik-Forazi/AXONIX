"""
DevNet Backend - Ollama only.
"""

import json
import urllib.request
import urllib.error
from typing import Iterator

OLLAMA_BASE = "http://localhost:11434"


def _post(url, payload, timeout=300):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _post_stream(url, payload, timeout=300):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            raw = raw.strip()
            if raw:
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    continue


def _get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def ollama_running():
    try:
        _get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        return True
    except Exception:
        return False


def ollama_list_models():
    try:
        return [m["name"] for m in _get(f"{OLLAMA_BASE}/api/tags").get("models", [])]
    except Exception:
        return []


def ollama_model_exists(name):
    models = ollama_list_models()
    return name in models or f"{name}:latest" in models


class TextResponse:
    def __init__(self, text):
        self.text = text


class ToolCallResponse:
    def __init__(self, calls):
        self.calls = calls  # [{"name": str, "args": dict}, ...]


class OllamaBackend:
    def __init__(self, model_name="gemma3-4b", temperature=0.2, max_tokens=4096,
                 base_url=OLLAMA_BASE, tools=None):
        self.model_name  = model_name
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self.base_url    = base_url.rstrip("/")
        self.tools       = tools or []

    def complete(self, messages):
        """Blocking call. Returns TextResponse or ToolCallResponse."""
        payload = {
            "model":    self.model_name,
            "messages": messages,
            "stream":   False,
            "options":  {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        if self.tools:
            payload["tools"] = self.tools
        try:
            resp = _post(f"{self.base_url}/api/chat", payload)
            msg  = resp.get("message", {})
            raw_tc = msg.get("tool_calls")
            if raw_tc:
                calls = []
                for tc in raw_tc:
                    fn   = tc.get("function", {})
                    name = fn.get("name", "")
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except Exception: args = {}
                    if name:
                        calls.append({"name": name, "args": args})
                if calls:
                    return ToolCallResponse(calls)
            return TextResponse(msg.get("content", ""))
        except Exception as e:
            return TextResponse(f"[ERROR] Ollama failed: {e}")

    def stream_text(self, messages):
        """Streaming plain text, no tools. Yields str tokens."""
        payload = {
            "model":    self.model_name,
            "messages": messages,
            "stream":   True,
            "options":  {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        try:
            for chunk in _post_stream(f"{self.base_url}/api/chat", payload):
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break
        except Exception as e:
            yield f"[ERROR] Stream failed: {e}"

    def load(self):
        if not ollama_running():
            return "[ERROR] Ollama is not running. Start: ollama serve"
        if not ollama_model_exists(self.model_name):
            return f"[ERROR] Model '{self.model_name}' not in Ollama. Run: devnet setup"
        return "ok"

    def is_loaded(self):
        return ollama_running() and ollama_model_exists(self.model_name)

    def unload(self):
        pass

    def health_check(self):
        try:
            _get(f"{self.base_url}/api/tags", timeout=3)
            return {"status": "ok", "backend": "ollama", "model": self.model_name, "url": self.base_url}
        except Exception as e:
            return {"status": "error", "error": str(e), "backend": "ollama"}
