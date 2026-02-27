"""
LlamaCpp Backend - Direct integration with llama.cpp server
Supports: llama.cpp server (OpenAI-compatible)
Auto-starts llama-server if configured.
"""

import json
import os
import subprocess
import time
import urllib.request
import urllib.error
from typing import Iterator


class LlamaCppBackend:
    """
    Connects to a running llama.cpp server.
    If auto_server=True and llama_bin is set, will launch the server automatically.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        model: str = "local",
        model_path: str = "",          # full path to GGUF file
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        repeat_penalty: float = 1.1,
        n_ctx: int = 4096,
        llama_bin: str = "",           # path to llama-server binary
        auto_server: bool = False,     # auto-launch llama-server
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.model_path = model_path
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.repeat_penalty = repeat_penalty
        self.n_ctx = n_ctx
        self.llama_bin = llama_bin
        self.auto_server = auto_server
        self._server_proc: subprocess.Popen | None = None

        if auto_server and llama_bin and model_path:
            self._ensure_server()

    # ── Server management ──────────────────────────────────

    def _ensure_server(self):
        """Start llama-server if it isn't running."""
        h = self.health_check()
        if h["status"] == "ok":
            return  # already up

        if not os.path.isfile(self.llama_bin):
            print(f"[LlamaCpp] llama-server not found at: {self.llama_bin}")
            return

        if not os.path.isfile(self.model_path):
            print(f"[LlamaCpp] Model file not found: {self.model_path}")
            print(f"[LlamaCpp] Please download the model and place it at that path.")
            return

        import shlex
        port = self.base_url.split(":")[-1] if ":" in self.base_url else "8080"
        cmd = [
            self.llama_bin,
            "-m", self.model_path,
            "--port", port,
            "--ctx-size", str(self.n_ctx),
            "-ngl", "0",        # CPU only — no GPU layers
            "--threads", str(max(1, os.cpu_count() - 1)),
        ]
        print(f"[LlamaCpp] Starting server: {' '.join(cmd)}")
        self._server_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        # Wait up to 30s for server to become ready
        for _ in range(60):
            time.sleep(0.5)
            h = self.health_check()
            if h["status"] == "ok":
                print(f"[LlamaCpp] Server ready at {self.base_url}")
                return
        print(f"[LlamaCpp] Server did not start in time. Check your model path and binary.")

    def stop_server(self):
        if self._server_proc:
            self._server_proc.terminate()
            self._server_proc = None

    # ── HTTP helpers ───────────────────────────────────────

    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"[LlamaCpp] Cannot connect to {self.base_url}.\n"
                f"Make sure llama-server is running.\n"
                f"Error: {e}"
            )

    # ── Inference ──────────────────────────────────────────

    def chat(self, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "repeat_penalty": self.repeat_penalty,
            "stream": False,
        }
        try:
            resp = self._post("/v1/chat/completions", payload)
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            return f"[ERROR] Unexpected response format: {e}"
        except ConnectionError as e:
            return str(e)

    def chat_stream(self, messages: list[dict]) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        url = f"{self.base_url}/v1/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk == "[DONE]":
                            break
                        try:
                            obj = json.loads(chunk)
                            delta = obj["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except (json.JSONDecodeError, KeyError):
                            continue
        except Exception as e:
            yield f"[STREAM ERROR] {e}"

    def completion(self, prompt: str) -> str:
        payload = {
            "prompt": prompt,
            "temperature": self.temperature,
            "n_predict": self.max_tokens,
            "top_p": self.top_p,
            "repeat_penalty": self.repeat_penalty,
            "stop": ["</s>", "User:", "Human:"],
        }
        try:
            resp = self._post("/completion", payload)
            return resp.get("content", "")
        except ConnectionError as e:
            return str(e)

    def health_check(self) -> dict:
        try:
            url = f"{self.base_url}/health"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return {"status": "ok", "server": self.base_url}
        except Exception as e:
            return {"status": "error", "error": str(e), "server": self.base_url}

    def get_model_info(self) -> dict:
        try:
            url = f"{self.base_url}/v1/models"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": str(e)}
