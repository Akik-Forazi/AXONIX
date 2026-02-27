"""
DevNet Web Server - Ollama edition.
SSE streaming for chat and agent modes.
Tool call/result events emitted live during agent loop.
"""

import json
import threading
import webbrowser
import time
import os
import traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from devnet.core.agent import Agent
from devnet.core.config import load_config, save_config, DEVNET_HOME, MODELS_DIR, model_dir


def get_html():
    p = os.path.join(os.path.dirname(__file__), "static", "index.html")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "<h1>DevNet — index.html missing</h1>"


class _QuietServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = __import__("sys").exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError)):
            return
        print(f"[DevNet Web] {client_address}: {exc}")


class DevNetHandler(BaseHTTPRequestHandler):
    agent: Agent = None

    def log_message(self, *_):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, data, status=200):
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
        try:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n)) if n else {}
        except Exception:
            return {}

    def _sse_open(self):
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
        try:
            self.wfile.write(f"data: {json.dumps(ev, default=str)}\n\n".encode())
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
            return False

    def do_OPTIONS(self):
        try:
            self.send_response(204)
            self._cors()
            self.end_headers()
        except Exception:
            pass

    def do_GET(self):
        try:
            self._get(urlparse(self.path).path)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _get(self, path):
        if path in ("/", "/index.html"):
            return self._html(get_html())

        if path == "/api/health":
            h = self.agent.health() if self.agent else {"status": "no_agent"}
            return self._json(h)

        if path == "/api/config":
            cfg = load_config()
            cfg["_home"]       = DEVNET_HOME
            cfg["_models_dir"] = MODELS_DIR
            return self._json(cfg)

        if path == "/api/memory":
            return self._json(self.agent.memory.all() if self.agent else {})

        if path == "/api/history":
            msgs = self.agent.messages if self.agent else []
            return self._json({"messages": [m for m in msgs if m.get("role") != "system"]})

        if path == "/api/sessions":
            if not self.agent:
                return self._json({"error": "No agent"}, 500)
            return self._json({"sessions": self.agent.history.get_sessions()})

        if path == "/api/models":
            from devnet.core.models import all_models
            from devnet.core.backend import ollama_model_exists
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
                    "temperature": m.temperature,
                    "tags":        m.tags,
                    "description": m.description,
                    "best_for":    m.best_for,
                    "speed_toks":  m.speed_toks,
                    "recommended": m.recommended,
                    "hf_url":      m.hf_url,
                    "repo":        m.repo,
                    "downloaded":  os.path.isfile(gguf),
                    "registered":  ollama_model_exists(m.name),
                    "active":      m.name == active,
                })
            return self._json(out)

        if path == "/api/files/list":
            if not self.agent:
                return self._json({"error": "No agent"}, 500)
            tree = self.agent.code_tools.tree(".", max_depth=2)
            files = []
            for line in tree.split("\n")[1:]:
                line = line.strip()
                if not line:
                    continue
                name   = line.split("── ")[-1]
                is_dir = name.endswith("/")
                files.append({"name": name, "is_dir": is_dir, "path": name.rstrip("/")})
            return self._json(files)

        if path == "/api/files/read":
            q = parse_qs(urlparse(self.path).query)
            p = q.get("path", [""])[0]
            if not p:
                return self._json({"error": "No path"}, 400)
            try:
                full = self.agent.file_tools._resolve(p)
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                return self._json({"content": content, "path": p})
            except Exception as e:
                return self._json({"error": str(e)}, 500)

        return self._json({"error": "Not found"}, 404)

    def do_POST(self):
        try:
            self._post(urlparse(self.path).path)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _post(self, path):
        body = self._body()

        # ── /api/chat — SSE streaming ──────────────────────
        if path == "/api/chat":
            message = body.get("message", "").strip()
            mode    = body.get("mode", "chat")
            if not message:
                return self._json({"error": "Empty message"}, 400)
            if not self.agent:
                return self._json({"error": "Agent not initialized"}, 500)
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
            if self.agent:
                self.agent.reset()
            return self._json({"status": "reset"})

        if path == "/api/memory/clear":
            if self.agent:
                self.agent.memory.clear()
            return self._json({"status": "cleared"})

        if path == "/api/memory/save":
            key = body.get("key", "")
            val = body.get("value", "")
            if self.agent and key:
                self.agent.memory.save(key, val)
                return self._json({"status": "saved"})
            return self._json({"error": "key required"}, 400)

        if path == "/api/config/save":
            cfg     = load_config()
            allowed = {"base_url", "model_name", "max_steps", "max_tokens", "temperature", "workspace"}
            for k, v in body.items():
                if k in allowed:
                    cfg[k] = v
            save_config(cfg)
            return self._json({"status": "saved"})

        if path == "/api/model/switch":
            name = body.get("name", "")
            if not name:
                return self._json({"error": "name required"}, 400)
            if not self.agent:
                return self._json({"error": "no agent"}, 500)
            result = self.agent.switch_model(name)
            ok = "[OK]" in result
            if ok:
                cfg = load_config()
                cfg["model_name"] = name
                save_config(cfg)
            return self._json({"ok": ok, "msg": result})

        if path == "/api/setup":
            from devnet.core.first_run import run_setup
            imported = run_setup(silent=True)
            return self._json({"imported": imported})

        return self._json({"error": "Not found"}, 404)

    # ── SSE runners ────────────────────────────────────────

    def _chat_sse(self, message):
        """Plain chat with streaming tokens."""
        for token in self.agent.chat_stream(message):
            if not self._sse({"type": "token", "token": token}):
                return
        self._sse({"type": "done", "response": "", "steps": 0, "tool_calls": []})

    def _agent_sse(self, message):
        """
        Agent loop. Runs agent.run() in current thread.
        Hooks emit SSE events live as they happen.
        """
        steps     = [0]
        tcs       = []
        result_box = [None]

        def on_step(s, total):
            steps[0] = s
            self._sse({"type": "step", "step": s, "total": total})

        def on_token(token):
            self._sse({"type": "token", "token": token})

        def on_tool_call(name, args):
            tcs.append({"tool": name, "args": args})
            self._sse({"type": "tool_call", "tool": name, "args": args})

        def on_tool_result(name, result):
            result_s = str(result)[:2000]
            # Mark last unresolved call for this tool
            for tc in reversed(tcs):
                if tc["tool"] == name and "result" not in tc:
                    tc["result"] = result_s
                    break
            self._sse({"type": "tool_result", "tool": name, "result": result_s})

        self.agent.on_step        = on_step
        self.agent.on_token       = on_token
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
        """Goal mode via LoopEngine."""
        self._sse({"type": "status", "msg": "Planning goal…"})
        response = self.agent.run_goal(message)
        self._sse({"type": "done", "response": response, "steps": 0, "tool_calls": []})


class WebServer:
    def __init__(self, agent: Agent, host="localhost", port=7860):
        self.agent = agent
        self.host  = host
        self.port  = port
        DevNetHandler.agent = agent

    def start(self, open_browser=True):
        server = _QuietServer((self.host, self.port), DevNetHandler)
        url    = f"http://{self.host}:{self.port}"
        print(f"\n\033[96m[DevNet Web]\033[0m → \033[92m{url}\033[0m  (Ctrl+C to stop)\n")
        if open_browser:
            threading.Thread(
                target=lambda: (time.sleep(0.9), webbrowser.open(url)),
                daemon=True,
            ).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
