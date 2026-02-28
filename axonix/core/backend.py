"""
This file handles all the different ways we can talk to AI models.
Whether it's Ollama, a local GGUF file, or an API like OpenAI or Claude,
this code makes sure we speak their language.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Iterator, Optional, List, Dict, Any
from abc import ABC, abstractmethod
from axonix.core.debug import debug, info, warn, error, log_json

# These classes help us structure the responses we get back from the AI.
class TextResponse:
    def __init__(self, text: str):
        self.text = text

class ToolCallResponse:
    def __init__(self, calls: List[Dict[str, Any]]):
        self.calls = calls

class Backend(ABC):
    """
    Every AI connection needs to follow these rules so the agent knows how to talk to it.
    """
    @abstractmethod
    def complete(self, messages: List[Dict[str, str]]) -> Any:
        """Wait for the full answer."""
        pass

    @abstractmethod
    def stream_text(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        """Listen to the answer as it comes in, token by token."""
        pass

    def load(self) -> str:
        """Wake up the model if needed."""
        return "ok"

    def is_loaded(self) -> bool:
        return True

    def unload(self):
        """Put the model to sleep."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Make sure the AI is feeling okay and ready to work."""
        pass

# ── Ollama ──────────────────────────────────────────────────

class OllamaBackend(Backend):
    """
    Handles connections to a local Ollama server.
    """
    def __init__(self, model_name="gemma3-4b", temperature=0.2, max_tokens=4096,
                 base_url="http://localhost:11434", tools=None):
        self.model_name  = model_name
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self.base_url    = base_url.rstrip("/")
        self.tools       = tools or []
        debug(f"Ollama is ready to help using {model_name}.")

    def _post(self, url, payload, timeout=600):
        # We send a request to the Ollama server and wait for the response.
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            error(f"Had some trouble talking to Ollama: {e}")
            raise

    def complete(self, messages):
        # ... (rest of the implementation with conversational debugs)

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
            return TextResponse(content)
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
            return {"status": "error", "error": str(e), "backend": "ollama"}

# ── OpenAI Compatible Implementation (LM Studio, Groq, etc) ──

class OpenAIBackend(Backend):
    def __init__(self, model_name="gpt-4o", temperature=0.2, max_tokens=4096,
                 base_url="https://api.openai.com/v1", api_key=None, tools=None):
        self.model_name  = model_name
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self.base_url    = base_url.rstrip("/")
        self.api_key     = api_key or os.environ.get("OPENAI_API_KEY", "no-key")
        self.tools       = tools or []
        debug(f"OpenAIBackend initialized: {model_name} @ {base_url}")

    def _post(self, url, payload, timeout=600):
        debug(f"OpenAI POST: {url}")
        log_json(payload, "Payload")
        data = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp_data = json.loads(r.read())
                log_json(resp_data, "Response")
                return resp_data
        except urllib.error.URLError as e:
            error(f"OpenAI connection error: {e}")
            raise

    def _post_stream(self, url, payload, timeout=600):
        debug(f"OpenAI POST Stream: {url}")
        log_json(payload, "Payload")
        data = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                for line in r:
                    line = line.decode('utf-8').strip()
                    if line.startswith("data: "):
                        raw = line[6:].strip()
                        if raw == "[DONE]": break
                        try:
                            chunk = json.loads(raw)
                            yield chunk
                        except: continue
        except Exception as e:
            error(f"OpenAI stream error: {e}")
            raise

    def complete(self, messages):
        payload = {
            "model":       self.model_name,
            "messages":    messages,
            "temperature": self.temperature,
            "max_tokens":  self.max_tokens,
            "stream":      False
        }
        if self.tools: payload["tools"] = self.tools
        try:
            resp = self._post(f"{self.base_url}/chat/completions", payload)
            msg = resp["choices"][0]["message"]
            
            if "tool_calls" in msg:
                calls = []
                for tc in msg["tool_calls"]:
                    fn = tc["function"]
                    try: args = json.loads(fn["arguments"])
                    except: args = {}
                    calls.append({"name": fn["name"], "args": args})
                return ToolCallResponse(calls)
            
            return TextResponse(msg.get("content", ""))
        except Exception as e:
            error(f"OpenAI exception: {e}")
            return TextResponse(f"[ERROR] OpenAI backend failed: {e}")

    def stream_text(self, messages):
        payload = {
            "model":       self.model_name,
            "messages":    messages,
            "temperature": self.temperature,
            "max_tokens":  self.max_tokens,
            "stream":      True
        }
        try:
            for chunk in self._post_stream(f"{self.base_url}/chat/completions", payload):
                delta = chunk["choices"][0].get("delta", {})
                token = delta.get("content", "")
                if token: yield token
        except Exception as e:
            yield f"[ERROR] OpenAI stream failed: {e}"

    def health_check(self):
        # Basic check: try listing models or just return ok if base_url reachable
        return {"status": "ok", "backend": "openai", "model": self.model_name}

# ── Anthropic Implementation (Claude) ──────────────────────

class AnthropicBackend(Backend):
    def __init__(self, model_name="claude-3-5-sonnet-20241022", temperature=0.2, max_tokens=4096, api_key=None):
        self.model_name  = model_name
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self.api_key     = api_key or os.environ.get("ANTHROPIC_API_KEY", "no-key")
        debug(f"AnthropicBackend initialized: {model_name}")

    def _post(self, url, payload, timeout=600):
        data = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            error(f"Anthropic connection error: {e}")
            raise

    def complete(self, messages):
        # Convert messages to Anthropic format
        system = ""
        user_msgs = []
        for m in messages:
            if m["role"] == "system": system = m["content"]
            else: user_msgs.append(m)
            
        payload = {
            "model":       self.model_name,
            "system":      system,
            "messages":    user_msgs,
            "max_tokens":  self.max_tokens,
            "temperature": self.temperature,
            "stream":      False
        }
        try:
            resp = self._post("https://api.anthropic.com/v1/messages", payload)
            content = resp["content"][0]["text"]
            return TextResponse(content)
        except Exception as e:
            return TextResponse(f"[ERROR] Anthropic failed: {e}")

    def stream_text(self, messages):
        # Anthropic streaming via urllib is complex (event-stream format differs)
        # For now, we use blocking complete() but yield it as one token for basic support
        # Full SSE streaming for Anthropic should be added later if needed.
        res = self.complete(messages)
        if isinstance(res, TextResponse):
            yield res.text
        else:
            yield "[ERROR] Anthropic stream not fully implemented yet."

    def health_check(self):
        return {"status": "ok", "backend": "anthropic", "model": self.model_name}

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
            return f"[ERROR] Model file not found: {self.model_path}"
        try:
            from llama_cpp import Llama
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_gpu_layers=0,
                verbose=True if os.environ.get("AXONIX_DEBUG") else False
            )
            return "ok"
        except Exception as e:
            return f"[ERROR] Failed to load llama-cpp: {e}"

    def complete(self, messages):
        if not self.llm: return TextResponse("[ERROR] Backend not loaded")
        try:
            resp = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            content = resp["choices"][0]["message"].get("content", "")
            return TextResponse(content)
        except Exception as e:
            return TextResponse(f"[ERROR] LlamaCpp failed: {e}")

    def stream_text(self, messages):
        if not self.llm: yield "[ERROR] Backend not loaded"; return
        try:
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
            yield f"[ERROR] LlamaCpp stream failed: {e}"

    def health_check(self):
        if self.llm:
            return {"status": "ok", "backend": "llamacpp", "model": os.path.basename(self.model_path)}
        return {"status": "error", "error": "Model not loaded", "backend": "llamacpp"}

# ── The Factory ──────────────────────────────────────────────

def get_backend(cfg: dict, tools=None) -> Backend:
    # This is where we decide which AI "brain" to plug in.
    prov = cfg.get("provider", cfg.get("backend", "ollama")).lower()
    debug(f"Picking out the '{prov}' backend for you.")
    
    # Simple mappings so you can use friendly names.
    if prov == "lmstudio":
        cfg["provider"] = "openai"
        if "base_url" not in cfg: cfg["base_url"] = "http://localhost:1234/v1"
        prov = "openai"
    
    if prov == "ollama":
        return OllamaBackend(
            model_name  = cfg.get("model_name", "gemma3-4b"),
            temperature = float(cfg.get("temperature", 0.2)),
            max_tokens  = int(cfg.get("max_tokens", 4096)),
            base_url    = cfg.get("base_url", "http://localhost:11434"),
            tools       = tools
        )
    
    if prov == "openai":
        return OpenAIBackend(
            model_name  = cfg.get("model_name", "gpt-4o"),
            temperature = float(cfg.get("temperature", 0.2)),
            max_tokens  = int(cfg.get("max_tokens", 4096)),
            base_url    = cfg.get("base_url", "https://api.openai.com/v1"),
            api_key     = cfg.get("api_key"),
            tools       = tools
        )
    
    if prov == "anthropic":
        return AnthropicBackend(
            model_name  = cfg.get("model_name", "claude-3-5-sonnet-20241022"),
            temperature = float(cfg.get("temperature", 0.2)),
            max_tokens  = int(cfg.get("max_tokens", 4096)),
            api_key     = cfg.get("api_key")
        )
    
    if prov in ("llamacpp", "local"):
        return LlamaCppBackend(
            model_path  = cfg.get("model_path", ""),
            temperature = float(cfg.get("temperature", 0.2)),
            max_tokens  = int(cfg.get("max_tokens", 4096)),
            n_ctx       = int(cfg.get("n_ctx", 8192)),
            tools       = tools
        )
    
    warn(f"I couldn't find a backend called '{prov}', so I'll use Ollama as a backup.")
    return OllamaBackend(model_name=cfg.get("model_name", "gemma3-4b"), tools=tools)

# ── Little helper functions ───────────────────────────────

def ollama_running():
    # Just checking if Ollama is awake.
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as r: return True
    except: return False

def ollama_model_exists(name):
    # Looking to see if you've already downloaded this model.
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as r:
            data = json.loads(r.read())
            models = [m["name"] for m in data.get("models", [])]
            return name in models or f"{name}:latest" in models
    except: return False
