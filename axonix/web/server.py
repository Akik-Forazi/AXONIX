"""
This module implements the AXONIX-ZERO Web Server, providing a modern browser-based 
dashboard for interacting with the AI agent. It utilizes Server-Sent Events (SSE) 
to stream real-time tokens, thoughts, and tool activities directly to the user.
"""

import json
import threading
import webbrowser
import time
import os
import traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from axonix.core.agent import Agent
from axonix.core.config import load_config, save_config, AXONIX_HOME, MODELS_DIR, model_dir


def get_html():
    """Retrieves the primary UI layout from the static index file."""
    p = os.path.join(os.path.dirname(__file__), "static", "index.html")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "<h1>AXONIX-ZERO Intelligence Dashboard — Critical Error: index.html not found.</h1>"


class _QuietServer(ThreadingHTTPServer):
    """
    An optimized HTTP server that suppresses common networking noise
    to provide a cleaner console experience for the user.
    """
    daemon_threads = True

    def handle_error(self, request, client_address):
        # We ignore broken pipe errors which are common in streaming web apps.
        exc = __import__("sys").exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError)):
            return
        print(f"[AXONIX-ZERO Network] {client_address}: {exc}")


class AxonixHandler(BaseHTTPRequestHandler):
    """
    The core request handler for the Web UI. It manages API endpoints,
    file system access, and the SSE streaming backbone.
    """
    agent: Agent = None

    def log_message(self, *_):
        # Disabling standard access logs to keep the terminal focused on agent activities.
        pass

    def _cors(self):
        """Injects necessary headers to permit secure cross-origin requests if needed."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, data, status=200):
        """Sends a structured JSON response to the browser."""
        try:
            body = json.dumps(data, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
            pass

    def _html(self, html):
        """Serves HTML content with appropriate encoding."""
        try:
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
            pass

    def _body(self):
        """Parses the incoming request body as JSON."""
        try:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n)) if n else {}
        except Exception:
            return {}

    def _sse_open(self):
        """Initializes a persistent Server-Sent Events connection."""
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self._cors()
            self.end_headers()
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
            return False

    def _sse(self, ev):
        """Pushes a real-time event through the SSE channel."""
        try:
            self.wfile.write(f"data: {json.dumps(ev, default=str)}\n\n".encode())
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
            return False

    def do_OPTIONS(self):
        """Handles pre-flight CORS requests gracefully."""
        try:
            self.send_response(204)
            self._cors()
            self.end_headers()
        except Exception:
            pass

    def do_GET(self):
        """Routes incoming GET requests to the appropriate handler."""
        try:
            self._get(urlparse(self.path).path)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _get(self, path):
        if path in ("/", "/index.html"):
            return self._html(get_html())

        if path == "/api/health":
            h = self.agent.health() if self.agent else {"status": "inactive"}
            return self._json(h)

        if path == "/api/config":
            cfg = load_config()
            cfg["_home"]       = AXONIX_HOME
            cfg["_models_dir"] = MODELS_DIR
            return self._json(cfg)

        if path == "/api/memory":
            return self._json(self.agent.memory.all() if self.agent else {})

        if path == "/api/history":
            msgs = self.agent.messages if self.agent else []
            return self._json({"messages": [m for m in msgs if m.get("role") != "system"]})

        if path == "/api/sessions":
            if not self.agent:
                return self._json({"error": "Agent initialization pending."}, 500)
            return self._json({"sessions": self.agent.history.get_sessions()})

        if path == "/api/models":
            from axonix.core.models import all_models
            from axonix.core.backend import ollama_model_exists
            cfg    = load_config()
            active = cfg.get("model_name", "")
            out = []
            for m in all_models():
                gguf = os.path.join(model_dir(m.name), m.gguf_name)
                out.append({
                    "name":        m.name,
                    "gguf_name":   m.gguf_name,
                    "size_gb":     m.size_gb,
                    "ram_gb":      m.ram_gb,
                    "ctx":         m.ctx,
                    "description": m.description,
                    "best_for":    m.best_for,
                    "speed_toks":  m.speed_toks,
                    "recommended": m.recommended,
                    "hf_url":      m.hf_url,
                    "downloaded":  os.path.isfile(gguf),
                    "registered":  ollama_model_exists(m.name),
                    "active":      m.name == active,
                })
            return self._json(out)

        if path == "/api/files/list":
            if not self.agent:
                return self._json({"error": "Agent unavailable."}, 500)
            tree = self.agent.code_tools.tree(".", max_depth=2)
            files = []
            for line in tree.split("\n")[1:]:
                line = line.strip()
                if not line: continue
                name   = line.split("── ")[-1]
                is_dir = name.endswith("/")
                files.append({"name": name, "is_dir": is_dir, "path": name.rstrip("/")})
            return self._json(files)

        return self._json({"error": "Resource not found."}, 404)

    def do_POST(self):
        """Routes incoming POST requests to the appropriate handler."""
        try:
            self._post(urlparse(self.path).path)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _post(self, path):
        body = self._body()

        # SSE Streaming for real-time interaction.
        if path == "/api/chat":
            message = body.get("message", "").strip()
            mode    = body.get("mode", "chat")
            if not message:
                return self._json({"error": "Empty message received."}, 400)
            if not self.agent:
                return self._json({"error": "Agent not initialized."}, 500)
            if not self._sse_open():
                return
            try:
                if mode == "agent":
                    self._agent_sse(message)
                elif mode == "goal":
                    self._goal_sse(message)
                else:
                    self._chat_sse(message)
            except Exception as e:
                self._sse({"type": "error", "error": str(e), "trace": traceback.format_exc()})
            finally:
                try:
                    self.wfile.write(b"data: [CLOSE]\n\n")
                    self.wfile.flush()
                except Exception:
                    pass
            return

        if path == "/api/reset":
            if self.agent: self.agent.reset()
            return self._json({"status": "Session reset successful."})

        if path == "/api/config/save":
            cfg = load_config()
            allowed = {"base_url", "model_name", "max_steps", "max_tokens", "temperature", "workspace"}
            for k, v in body.items():
                if k in allowed: cfg[k] = v
            save_config(cfg)
            return self._json({"status": "Settings updated."})

        return self._json({"error": "Endpoint not found."}, 404)

    # ── Real-Time SSE Runners ──────────────────────────────

    def _chat_sse(self, message):
        """Provides a direct chat experience with streaming tokens."""
        for token in self.agent.chat_stream(message):
            if not self._sse({"type": "token", "token": token}):
                return
        self._sse({"type": "done", "response": ""})

    def _agent_sse(self, message):
        """Executes an agent task, emitting thoughts and tool activities live."""
        steps = [0]
        tcs   = []

        def on_step(s, total):
            steps[0] = s
            self._sse({"type": "step", "step": s, "total": total})

        def on_token(token):
            self._sse({"type": "token", "token": token})

        def on_thought(content):
            self._sse({"type": "thought", "content": content})

        def on_tool_call(name, args):
            tcs.append({"tool": name, "args": args})
            self._sse({"type": "tool_call", "tool": name, "args": args})

        def on_tool_result(name, result):
            result_s = str(result)[:2000]
            for tc in reversed(tcs):
                if tc["tool"] == name and "result" not in tc:
                    tc["result"] = result_s
                    break
            self._sse({"type": "tool_result", "tool": name, "result": result_s})

        # Registering real-time callbacks.
        self.agent.on_step        = on_step
        self.agent.on_token       = on_token
        self.agent.on_thought     = on_thought
        self.agent.on_tool_call   = on_tool_call
        self.agent.on_tool_result = on_tool_result

        response = self.agent.run(message)
        self._sse({
            "type":       "done",
            "response":   response,
            "steps":      steps[0],
            "tool_calls": tcs,
        })

    def _goal_sse(self, message):
        """Executes a high-level goal using the autonomous loop engine."""
        self._sse({"type": "status", "msg": "Strategic analysis in progress..."})
        response = self.agent.run_goal(message)
        self._sse({"type": "done", "response": response})


class WebServer:
    """
    Manages the AXONIX-ZERO Web Server lifecycle.
    """
    def __init__(self, agent: Agent, host="localhost", port=7860):
        self.agent = agent
        self.host  = host
        self.port  = port
        AxonixHandler.agent = agent

    def start(self, open_browser=True):
        """Launches the server and optionally opens the browser."""
        server = _QuietServer((self.host, self.port), AxonixHandler)
        url    = f"http://{self.host}:{self.port}"
        print(f"\n\033[96m[AXONIX-ZERO Dashboard]\033[0m -> \033[92m{url}\033[0m (Active)\n")
        
        if open_browser:
            threading.Thread(
                target=lambda: (time.sleep(1.0), webbrowser.open(url)),
                daemon=True,
            ).start()
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
