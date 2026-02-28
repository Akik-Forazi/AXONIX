"""
Axonix Backend - Multi-Provider Engine
Supports: Ollama, LlamaCpp (in-process), Web APIs, and custom Zarx/Torch loaders.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Iterator, Optional, List, Dict, Any
from abc import ABC, abstractmethod
from axonix.core.debug import debug, info, warn, error, log_json

# ── Response Types ──────────────────────────────────────────

class TextResponse:
    def __init__(self, text: str):
        self.text = text

class ToolCallResponse:
    def __init__(self, calls: List[Dict[str, Any]]):
        """calls: [{"name": str, "args": dict}, ...]"""
        self.calls = calls

# ── Base Class ──────────────────────────────────────────────

class Backend(ABC):
    @abstractmethod
    def complete(self, messages: List[Dict[str, str]]) -> Any:
        """Blocking call. Returns TextResponse or ToolCallResponse."""
        pass

    @abstractmethod
    def stream_text(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        """Streaming plain text. Yields str tokens."""
        pass

    def load(self) -> str:
        """Optional load step. Returns 'ok' or error msg."""
        return "ok"

    def is_loaded(self) -> bool:
        return True

    def unload(self):
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        pass

# ── Ollama Implementation ───────────────────────────────────

class OllamaBackend(Backend):
    def __init__(self, model_name="gemma3-4b", temperature=0.2, max_tokens=4096,
                 base_url="http://localhost:11434", tools=None):
        self.model_name  = model_name
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self.base_url    = base_url.rstrip("/")
        self.tools       = tools or []
        debug(f"OllamaBackend initialized: {model_name} @ {base_url}")

    def _post(self, url, payload, timeout=600):
        debug(f"Ollama POST: {url}")
        log_json(payload, "Payload")
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp_data = json.loads(r.read())
                log_json(resp_data, "Response")
                return resp_data
        except urllib.error.URLError as e:
            error(f"Ollama connection error: {e}")
            raise

    def _post_stream(self, url, payload, timeout=600):
        debug(f"Ollama POST Stream: {url}")
        log_json(payload, "Payload")
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                for raw in r:
                    raw = raw.strip()
                    if raw:
                        try: 
                            chunk = json.loads(raw)
                            yield chunk
                        except json.JSONDecodeError: continue
        except urllib.error.URLError as e:
            error(f"Ollama stream connection error: {e}")
            raise

    def complete(self, messages):
        payload = {
            "model":    self.model_name,
            "messages": messages,
            "stream":   False,
            "options":  {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        if self.tools: payload["tools"] = self.tools
        try:
            resp = self._post(f"{self.base_url}/api/chat", payload)
            msg  = resp.get("message", {})
            raw_tc = msg.get("tool_calls")
            if raw_tc:
                debug(f"Ollama returned {len(raw_tc)} tool calls.")
                calls = []
                for tc in raw_tc:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except: 
                            warn(f"Failed to parse arguments string for tool {name}: {args}")
                            args = {}
                    if name: calls.append({"name": name, "args": args})
                if calls: return ToolCallResponse(calls)
            
            content = msg.get("content", "")
            debug(f"Ollama returned text response: {content[:100]}...")
            return TextResponse(content)
        except urllib.error.HTTPError as e:
            if e.code == 400:
                warn("Ollama returned 400. Attempting to strip tool-related messages and retry...")
                # Model doesn't support tool calling OR tool_calls in message history
                # Strip tools AND any tool_call/tool role messages, retry as plain chat
                clean_messages = []
                for m in messages:
                    if m.get("role") == "tool":
                        # Convert tool result to user message
                        clean_messages.append({"role": "user", "content": f"[Tool result]: {m.get('content', '')}"})
                    elif "tool_calls" in m:
                        # Convert assistant tool call to plain assistant message
                        calls_text = "; ".join(
                            f"{tc['function']['name']}({tc['function'].get('arguments','{}')})"
                            for tc in m.get("tool_calls", [])
                        )
                        clean_messages.append({"role": "assistant", "content": f"[Calling tools: {calls_text}]"})
                    else:
                        clean_messages.append(m)
                plain_payload = {
                    "model":    self.model_name,
                    "messages": clean_messages,
                    "stream":   False,
                    "options":  {"temperature": self.temperature, "num_predict": self.max_tokens},
                }
                try:
                    resp = self._post(f"{self.base_url}/api/chat", plain_payload)
                    return TextResponse(resp.get("message", {}).get("content", ""))
                except Exception as e2:
                    error(f"Ollama retry failed: {e2}")
                    return TextResponse(f"[ERROR] Ollama failed: {e2}")
            error(f"Ollama HTTP error {e.code}: {e.reason}")
            return TextResponse(f"[ERROR] Ollama failed: {e}")
        except Exception as e:
            error(f"Ollama exception: {e}")
            return TextResponse(f"[ERROR] Ollama failed: {e}")

    def stream_text(self, messages):
        payload = {
            "model":    self.model_name,
            "messages": messages,
            "stream":   True,
            "options":  {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        try:
            for chunk in self._post_stream(f"{self.base_url}/api/chat", payload):
                token = chunk.get("message", {}).get("content", "")
                if token: yield token
                if chunk.get("done"): break
        except Exception as e:
            error(f"Ollama stream exception: {e}")
            yield f"[ERROR] Stream failed: {e}"

    def health_check(self):
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as r:
                return {"status": "ok", "backend": "ollama", "model": self.model_name}
        except Exception as e:
            debug(f"Ollama health check failed: {e}")
            return {"status": "error", "error": str(e), "backend": "ollama"}

# ── LlamaCpp Implementation (Direct GGUF) ──────────────────

class LlamaCppBackend(Backend):
    def __init__(self, model_path: str, temperature=0.2, max_tokens=4096, n_ctx=8192, tools=None):
        self.model_path  = model_path
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self.n_ctx       = n_ctx
        self.tools       = tools or []
        self.llm         = None
        debug(f"LlamaCppBackend initialized for path: {model_path}")

    def load(self):
        if not os.path.exists(self.model_path):
            msg = f"[ERROR] Model file not found: {self.model_path}"
            error(msg)
            return msg
        try:
            info(f"Loading LlamaCpp model from {self.model_path}...")
            from llama_cpp import Llama
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_gpu_layers=0, # CPU only by default
                verbose=True if os.environ.get("AXONIX_DEBUG") else False
            )
            info("LlamaCpp model loaded successfully.")
            return "ok"
        except Exception as e:
            msg = f"[ERROR] Failed to load llama-cpp: {e}"
            error(msg)
            import traceback
            debug(traceback.format_exc())
            return msg

    def is_loaded(self):
        return self.llm is not None

    def complete(self, messages):
        if not self.llm: 
            warn("Attempted complete() on uninitialized LlamaCpp backend.")
            return TextResponse("[ERROR] Backend not loaded")
        try:
            debug(f"LlamaCpp completion request with {len(messages)} messages.")
            resp = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            log_json(resp, "LlamaCpp Response")
            content = resp["choices"][0]["message"].get("content", "")
            return TextResponse(content)
        except Exception as e:
            error(f"LlamaCpp completion exception: {e}")
            return TextResponse(f"[ERROR] LlamaCpp failed: {e}")

    def stream_text(self, messages):
        if not self.llm: 
            warn("Attempted stream_text() on uninitialized LlamaCpp backend.")
            yield "[ERROR] Backend not loaded"; return
        try:
            debug("LlamaCpp stream request.")
            stream = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True
            )
            for chunk in stream:
                delta = chunk["choices"][0]["delta"]
                if "content" in delta:
                    yield delta["content"]
        except Exception as e:
            error(f"LlamaCpp stream exception: {e}")
            yield f"[ERROR] LlamaCpp stream failed: {e}"

    def health_check(self):
        if self.llm:
            return {"status": "ok", "backend": "llamacpp", "model": os.path.basename(self.model_path)}
        return {"status": "error", "error": "Model not loaded", "backend": "llamacpp"}

# ── Backend Factory ────────────────────────────────────────

def get_backend(cfg: dict, tools=None) -> Backend:
    prov = cfg.get("provider", cfg.get("backend", "ollama")).lower()
    debug(f"Factory creating backend for provider: {prov}")
    
    if prov == "ollama":
        return OllamaBackend(
            model_name  = cfg.get("model_name", "gemma3-4b"),
            temperature = float(cfg.get("temperature", 0.2)),
            max_tokens  = int(cfg.get("max_tokens", 4096)),
            base_url    = cfg.get("base_url", "http://localhost:11434"),
            tools       = tools
        )
    
    if prov in ("llamacpp", "local"):
        return LlamaCppBackend(
            model_path  = cfg.get("model_path", ""),
            temperature = float(cfg.get("temperature", 0.2)),
            max_tokens  = int(cfg.get("max_tokens", 4096)),
            n_ctx       = int(cfg.get("n_ctx", 8192)),
            tools       = tools
        )
    
    warn(f"Unknown provider '{prov}', falling back to Ollama.")
    return OllamaBackend(model_name=cfg.get("model_name", "gemma3-4b"), tools=tools)

# ── Helper functions for CLI ───────────────────────────────

def ollama_running():
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as r: return True
    except: return False

def ollama_model_exists(name):
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as r:
            data = json.loads(r.read())
            models = [m["name"] for m in data.get("models", [])]
            return name in models or f"{name}:latest" in models
    except: return False
