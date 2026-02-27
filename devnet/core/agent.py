"""
DevNet Agent - Ollama native tool calling.
Clean agentic loop: complete() -> ToolCallResponse | TextResponse.
All hooks fire correctly for both CLI and Web UI.
"""

import json
import os
from typing import Callable, Iterator, Optional
from devnet.core.memory import Memory
from devnet.tools.file_tools import FileTools
from devnet.tools.shell_tools import ShellTools
from devnet.tools.web_tools import WebTools
from devnet.tools.code_tools import CodeTools
from devnet.core.history import ChatHistory

SYSTEM_PROMPT = """You are DevNet, a fully local AI coding agent running on Windows.
You complete development tasks autonomously using the tools provided to you.

PLATFORM: Windows. Use 'dir' not 'ls', 'type' not 'cat', backslashes or forward slashes both work.
Prefer file_read/file_write over shell commands for file I/O.

RULES:
- Think before acting. Use the right tool.
- Verify your work. Adapt on errors.
- Call done() when the task is fully and completely finished.
- Be concise in tool args. Don't over-explain before acting.
"""

TOOL_SCHEMAS = [
    {"type":"function","function":{"name":"file_read","description":"Read a file with line numbers.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"file_write","description":"Write/overwrite a file.","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"file_edit","description":"Find and replace text in a file.","parameters":{"type":"object","properties":{"path":{"type":"string"},"old":{"type":"string"},"new":{"type":"string"}},"required":["path","old","new"]}}},
    {"type":"function","function":{"name":"file_delete","description":"Delete a file or directory.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"file_list","description":"List directory contents.","parameters":{"type":"object","properties":{"path":{"type":"string","default":"."}},"required":[]}}},
    {"type":"function","function":{"name":"file_search","description":"Find files matching a glob pattern.","parameters":{"type":"object","properties":{"path":{"type":"string"},"pattern":{"type":"string"}},"required":["pattern"]}}},
    {"type":"function","function":{"name":"file_append","description":"Append text to a file.","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"shell_run","description":"Run a Windows CMD command.","parameters":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}},
    {"type":"function","function":{"name":"shell_python","description":"Execute Python code, capture output.","parameters":{"type":"object","properties":{"code":{"type":"string"}},"required":["code"]}}},
    {"type":"function","function":{"name":"web_get","description":"Fetch a URL and return its text content.","parameters":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}},
    {"type":"function","function":{"name":"web_search","description":"Search the web via DuckDuckGo.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"code_lint","description":"Lint a Python file with flake8.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"code_format","description":"Format a Python file with black.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"code_tree","description":"Show file tree of a directory.","parameters":{"type":"object","properties":{"path":{"type":"string","default":"."}},"required":[]}}},
    {"type":"function","function":{"name":"memory_save","description":"Save a key-value pair to persistent memory.","parameters":{"type":"object","properties":{"key":{"type":"string"},"value":{"type":"string"}},"required":["key","value"]}}},
    {"type":"function","function":{"name":"memory_get","description":"Get a value from persistent memory.","parameters":{"type":"object","properties":{"key":{"type":"string"}},"required":["key"]}}},
    {"type":"function","function":{"name":"memory_list","description":"List all keys in memory.","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"done","description":"Mark task complete. Call when fully finished.","parameters":{"type":"object","properties":{"result":{"type":"string","description":"What was accomplished"}},"required":["result"]}}},
]


class Agent:
    def __init__(self, model_name="gemma3-4b", temperature=0.2, max_tokens=4096,
                 max_steps=30, workspace=".", base_url="http://localhost:11434", **kwargs):
        self.model_name  = model_name
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self.max_steps   = max_steps
        self.workspace   = os.path.abspath(workspace)
        self.base_url    = base_url

        # Tools
        self.memory      = Memory()
        self.file_tools  = FileTools(self.workspace)
        self.shell_tools = ShellTools(self.workspace)
        self.web_tools   = WebTools()
        self.code_tools  = CodeTools(self.workspace)
        self.history     = ChatHistory(self.workspace)

        self._tool_map: dict[str, Callable] = {
            "file_read":    self.file_tools.read,
            "file_write":   self.file_tools.write,
            "file_edit":    self.file_tools.edit,
            "file_delete":  self.file_tools.delete,
            "file_list":    self.file_tools.list_dir,
            "file_search":  self.file_tools.search,
            "file_append":  self.file_tools.append,
            "shell_run":    self.shell_tools.run,
            "shell_python": self.shell_tools.run_python,
            "web_get":      self.web_tools.get,
            "web_search":   self.web_tools.search,
            "code_lint":    self.code_tools.lint,
            "code_format":  self.code_tools.format_code,
            "code_tree":    self.code_tools.tree,
            "memory_save":  self.memory.save,
            "memory_get":   self.memory.get,
            "memory_list":  self.memory.list_keys,
            "done":         self._done,
        }

        # Build LLM
        self._build_llm()

        # Conversation state
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._finished     = False
        self._final_result = None

        # Event hooks (set by CLI/Web to receive live events)
        self.on_step:        Optional[Callable] = None  # (step, total)
        self.on_token:       Optional[Callable] = None  # (token_str)
        self.on_tool_call:   Optional[Callable] = None  # (name, args)
        self.on_tool_result: Optional[Callable] = None  # (name, result_str)
        self.on_done:        Optional[Callable] = None  # (result_str)

    def _build_llm(self):
        from devnet.core.backend import OllamaBackend
        self.llm = OllamaBackend(
            model_name  = self.model_name,
            temperature = self.temperature,
            max_tokens  = self.max_tokens,
            base_url    = self.base_url,
            tools       = TOOL_SCHEMAS,
        )

    def _rebuild_llm(self):
        self._build_llm()

    # ── Internal ───────────────────────────────────────────

    def _done(self, result=""):
        self._finished     = True
        self._final_result = result
        return f"[DONE] {result}"

    def _exec_tool(self, name, args):
        if name not in self._tool_map:
            return f"[ERROR] Unknown tool '{name}'"
        try:
            r = self._tool_map[name](**args)
            return str(r) if r is not None else "OK"
        except TypeError as e:
            return f"[ERROR] Bad args for '{name}': {e}"
        except Exception as e:
            return f"[ERROR] Tool '{name}' raised: {e}"

    # ── Public API ─────────────────────────────────────────

    def load_model(self):
        return self.llm.load()

    def health(self):
        return self.llm.health_check()

    def reset(self):
        self.messages      = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._finished     = False
        self._final_result = None

    def switch_model(self, model_name):
        from devnet.core.backend import ollama_model_exists
        if not ollama_model_exists(model_name):
            return f"[ERROR] '{model_name}' not in Ollama. Run: devnet setup"
        self.model_name = model_name
        self._rebuild_llm()
        return f"[OK] Switched to {model_name}"

    def update_model_params(self, params):
        for k, v in params.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self._rebuild_llm()
        return "[OK] Updated."

    def chat(self, message):
        """Plain chat, no tools. Accumulates history. Returns full response."""
        self.messages.append({"role": "user", "content": message})
        from devnet.core.backend import OllamaBackend
        plain = OllamaBackend(self.model_name, self.temperature, self.max_tokens, self.base_url)
        full = ""
        for token in plain.stream_text(self.messages):
            full += token
            if self.on_token:
                self.on_token(token)
        self.messages.append({"role": "assistant", "content": full})
        self.history.append("assistant", full, mode="chat")
        return full

    def chat_stream(self, message) -> Iterator[str]:
        """Streaming plain chat for web UI. Yields tokens."""
        self.messages.append({"role": "user", "content": message})
        from devnet.core.backend import OllamaBackend
        plain = OllamaBackend(self.model_name, self.temperature, self.max_tokens, self.base_url)
        full = ""
        for token in plain.stream_text(self.messages):
            full += token
            yield token
        self.messages.append({"role": "assistant", "content": full})
        self.history.append("assistant", full, mode="chat")

    def run(self, task):
        """
        Full agentic loop.
        Calls complete() (blocking) each step.
        Fires on_step / on_tool_call / on_tool_result / on_token / on_done hooks.
        Returns final answer string.
        """
        from devnet.core.backend import TextResponse, ToolCallResponse

        self._finished     = False
        self._final_result = None
        # Fresh context for this task
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": task},
        ]
        self.history.append("user", task, mode="agent")

        no_action = 0

        for step in range(1, self.max_steps + 1):
            if self.on_step:
                self.on_step(step, self.max_steps)

            resp = self.llm.complete(messages)

            # ── Error ──────────────────────────────────────
            if isinstance(resp, TextResponse) and resp.text.startswith("[ERROR]"):
                return resp.text

            # ── Plain text ─────────────────────────────────
            if isinstance(resp, TextResponse):
                text = resp.text
                messages.append({"role": "assistant", "content": text})
                self.history.append("assistant", text, step=step)
                if self.on_token:
                    self.on_token(text)
                no_action += 1
                if no_action >= 3:
                    messages.append({
                        "role":    "user",
                        "content": (
                            "Use a tool to make progress. "
                            "If fully done, call the done tool with a summary."
                        ),
                    })
                if no_action >= 5:
                    return text
                continue

            # ── Tool calls ─────────────────────────────────
            if isinstance(resp, ToolCallResponse):
                no_action = 0
                calls = resp.calls

                # Record assistant turn with tool_calls list
                messages.append({
                    "role":       "assistant",
                    "content":    "",
                    "tool_calls": [
                        {
                            "id":       f"call_{step}_{i}",
                            "type":     "function",
                            "function": {
                                "name":      c["name"],
                                "arguments": json.dumps(c["args"]),
                            },
                        }
                        for i, c in enumerate(calls)
                    ],
                })

                for i, c in enumerate(calls):
                    name = c["name"]
                    args = c["args"]

                    if self.on_tool_call:
                        self.on_tool_call(name, args)

                    result = self._exec_tool(name, args)
                    self.history.append("tool", f"{name}: {result}", step=step)

                    if self.on_tool_result:
                        self.on_tool_result(name, result)

                    messages.append({
                        "role":          "tool",
                        "tool_call_id":  f"call_{step}_{i}",
                        "content":       result,
                    })

                    if self._finished:
                        break

                if self._finished:
                    if self.on_done:
                        self.on_done(self._final_result)
                    return self._final_result or "Task completed."

        return f"[MAX STEPS={self.max_steps}] Agent stopped. Increase max_steps if needed."

    def run_goal(self, goal, max_cycles=5, max_retries=3):
        from devnet.core.loop import LoopEngine
        return LoopEngine(self, max_cycles=max_cycles, max_retries=max_retries).run_goal(goal)
