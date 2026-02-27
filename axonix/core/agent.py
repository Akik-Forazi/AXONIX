"""
Axonix Agent - Multi-provider tool calling.
Clean agentic loop: complete() -> ToolCallResponse | TextResponse.
"""

import json
import os
import re
from typing import Callable, Iterator, Optional
from axonix.core.memory import Memory
from axonix.tools.file_tools import FileTools
from axonix.tools.shell_tools import ShellTools
from axonix.tools.web_tools import WebTools
from axonix.tools.code_tools import CodeTools
from axonix.core.history import ChatHistory
from axonix.core.debug import debug, info, warn, error, log_json

SYSTEM_PROMPT = """You are Axonix, a fully local AI coding agent running on Windows.
You complete development tasks autonomously using the tools available to you.

PLATFORM: Windows. Use 'dir' not 'ls', 'type' not 'cat'. Backslashes or forward slashes both work.
Prefer file_read/file_write over shell commands for file operations.

━━━ CRITICAL: YOU MUST USE THESE EXACT XML TAGS ━━━

To think, use:
<thought>
your reasoning here
</thought>

To call a tool, use:
<action>
{"tool": "tool_name", "args": {"arg1": "value1"}}
</action>

When the task is fully done, use:
<ENDOFOP>
summary of what was done
</ENDOFOP>

DO NOT write tool calls as plain text. ALWAYS wrap them in <action> tags.
DO NOT say "I will use the web_search tool". JUST USE IT with the tags.

━━━ EXAMPLE ━━━
User: Search for Python news

Your response:
<thought>
I need to search the web for Python news.
</thought>
<action>
{"tool": "web_search", "args": {"query": "Python programming news 2024"}}
</action>

[you will receive the result, then continue]
<thought>
I got results. I will now summarize them for the user.
</thought>
<ENDOFOP>
Found Python news: [summary here]
</ENDOFOP>

━━━ AVAILABLE TOOLS ━━━
file_read(path)
file_write(path, content)
file_edit(path, old, new)
file_append(path, content)
file_delete(path)
file_list(path=".")
file_search(path=".", pattern="*")
shell_run(command)
shell_python(code)
web_get(url)
web_search(query)
code_lint(path)
code_format(path)
code_tree(path=".")
memory_save(key, value)
memory_get(key)
memory_list()

━━━ RULES ━━━
- ALWAYS use <thought> before acting
- ALWAYS use <action> tags — never write JSON tool calls as plain text
- ONE <action> per turn — wait for result before next action
- End EVERY task with <ENDOFOP> — never leave a task open
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
    def __init__(self, **kwargs):
        self.config      = kwargs
        self.memory      = Memory()
        self.workspace   = os.path.abspath(kwargs.get("workspace", "."))
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

        self._build_llm()

        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._finished     = False
        self._final_result = None

        self.on_step:        Optional[Callable] = None
        self.on_token:       Optional[Callable] = None
        self.on_thought:     Optional[Callable] = None
        self.on_tool_call:   Optional[Callable] = None
        self.on_tool_result: Optional[Callable] = None
        self.on_done:        Optional[Callable] = None

        debug(f"Agent initialized in {self.workspace}")
        log_json(self.config, "Config")

    def _build_llm(self):
        from axonix.core.backend import get_backend
        # No tool schemas — we use streaming text-based tool parsing
        self.llm = get_backend(self.config, tools=None)
        debug(f"LLM backend built: {type(self.llm).__name__}")

    def _rebuild_llm(self):
        self._build_llm()

    def _done(self, result=""):
        self._finished     = True
        self._final_result = result
        debug(f"Agent called 'done' with result: {result}")
        return f"[DONE] {result}"

    def _extract_bare_json_tool(self, text: str):
        """
        Fallback: detect when model writes a raw JSON tool call without <action> tags.
        Looks for {"tool": "...", "args": {...}} anywhere in the text.
        Returns (tool_name, args) or None.
        """
        for m in re.finditer(r'\{[^{}]*"tool"\s*:\s*"([^"]+)"[^{}]*\}', text, re.DOTALL):
            raw = m.group(0)
            try:
                obj = json.loads(raw)
                tool = obj.get("tool") or obj.get("name")
                args = obj.get("args") or obj.get("arguments") or {}
                if tool:
                    return str(tool), dict(args)
            except Exception:
                pass
        return None

    def _parse_text_tool_calls(self, text: str):
        """Parse <tool>{...}</tool> blocks from model text output."""
        calls = []
        for m in re.finditer(r'<tool>(.*?)</tool>', text, re.DOTALL):
            raw = m.group(1).strip()
            debug(f"Found potential tool call in text: {raw}")
            try:
                obj = json.loads(raw)
                name = obj.get("name", "")
                args = obj.get("args", {})
                if name:
                    calls.append({"name": name, "args": args})
                    debug(f"Parsed tool call: {name}")
            except Exception as e:
                error(f"Failed to parse tool call JSON: {e}\nRaw: {raw}")
        return calls

    def _exec_tool(self, name, args):
        if name not in self._tool_map:
            warn(f"Unknown tool called: {name}")
            return f"[ERROR] Unknown tool '{name}'"
        
        debug(f"Executing tool '{name}' with args: {args}")
        try:
            r = self._tool_map[name](**args)
            result = str(r) if r is not None else "OK"
            debug(f"Tool '{name}' result (first 100 chars): {result[:100]}...")
            return result
        except TypeError as e:
            msg = f"[ERROR] Bad args for '{name}': {e}"
            error(msg)
            return msg
        except Exception as e:
            msg = f"[ERROR] Tool '{name}' raised: {e}"
            error(f"Tool execution failed: {e}")
            import traceback
            debug(traceback.format_exc())
            return msg

    def load_model(self):
        debug("Loading model...")
        return self.llm.load()

    def health(self):
        return self.llm.health_check()

    def reset(self):
        debug("Resetting agent state.")
        self.messages      = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._finished     = False
        self._final_result = None

    def switch_model(self, model_name):
        self.config["model_name"] = model_name
        self._rebuild_llm()
        debug(f"Switched model to: {model_name}")
        return f"[OK] Switched to {model_name}"

    def update_model_params(self, params):
        self.config.update(params)
        self._rebuild_llm()
        debug(f"Updated model params: {params}")
        return "[OK] Updated."

    def chat(self, message):
        debug(f"Chat: {message}")
        self.messages.append({"role": "user", "content": message})
        full = ""
        for token in self.llm.stream_text(self.messages):
            full += token
            if self.on_token:
                self.on_token(token)
        self.messages.append({"role": "assistant", "content": full})
        self.history.append("assistant", full, mode="chat")
        debug(f"Assistant: {full[:100]}...")
        return full

    def chat_stream(self, message) -> Iterator[str]:
        debug(f"Chat stream: {message}")
        self.messages.append({"role": "user", "content": message})
        full = ""
        for token in self.llm.stream_text(self.messages):
            full += token
            yield token
        self.messages.append({"role": "assistant", "content": full})
        self.history.append("assistant", full, mode="chat")

    def run(self, task: str):
        """
        Streaming agent loop with real-time tag parsing.
        
        Flow per step:
          1. Stream tokens from LLM
          2. StreamParser watches for <thought>, <action>, <ENDOFOP> mid-stream
          3. On <action>: pause stream, execute tool, inject result, resume
          4. On <ENDOFOP>: stop loop, return summary
        """
        from axonix.core.stream_parser import StreamParser

        debug(f"Agent starting task: {task}")
        self._finished     = False
        self._final_result = None

        messages = [
            {"role": "system",  "content": SYSTEM_PROMPT},
            {"role": "user",    "content": task},
        ]
        self.history.append("user", task, mode="agent")

        max_steps = int(self.config.get("max_steps", 30))

        for step in range(1, max_steps + 1):
            debug(f"--- Step {step}/{max_steps} ---")
            if self.on_step:
                self.on_step(step, max_steps)

            # ── Collect full streamed response, firing callbacks mid-stream ──
            raw_chunks      = []   # EVERY token including inside tags
            full_response   = []   # only text tokens (outside tags) for display
            action_pending  = []   # set when <action> fires, holds (tool, args)
            endofop_summary = []   # set when <ENDOFOP> fires
            last_thought    = []   # most recent thought content

            def on_text(token):
                full_response.append(token)
                if self.on_token:
                    self.on_token(token)

            def on_thought(content):
                debug(f"Thought: {content[:120]}")
                last_thought.clear()
                last_thought.append(content)
                if self.on_thought:
                    self.on_thought(content)

            def on_action(tool, args):
                debug(f"Action detected: {tool} {args}")
                action_pending.append((tool, args))

            def on_endofop(summary):
                debug(f"ENDOFOP: {summary[:120]}")
                endofop_summary.append(summary)

            def on_parse_error(msg):
                warn(f"Parser error: {msg}")

            parser = StreamParser(
                on_text    = on_text,
                on_thought = on_thought,
                on_action  = on_action,
                on_endofop = on_endofop,
                on_error   = on_parse_error,
            )

            # ── Stream tokens through the parser ──────────────────────
            try:
                for token in self.llm.stream_text(messages):
                    raw_chunks.append(token)   # capture everything
                    parser.feed(token)

                    if action_pending:
                        break
                    if endofop_summary:
                        break

                parser.flush()

            except Exception as e:
                error(f"Stream error on step {step}: {e}")
                import traceback
                debug(traceback.format_exc())
                return f"[ERROR] Stream failed: {e}"

            # raw_assembled = full streamed text INCLUDING tags (what model actually said)
            # display_text  = only text outside tags (what user sees)
            raw_assembled = "".join(raw_chunks)
            display_text  = "".join(full_response)
            self.history.append("assistant", display_text or raw_assembled, step=step)

            # ── ENDOFOP — task is done ─────────────────────────────────
            if endofop_summary:
                summary = endofop_summary[0]
                self._finished     = True
                self._final_result = summary
                messages.append({"role": "assistant", "content": raw_assembled})
                if self.on_done:
                    self.on_done(summary)
                info(f"Task completed: {summary[:120]}")
                return summary

            # ── ACTION — execute tool and continue ────────────────────
            if action_pending:
                tool_name, tool_args = action_pending[0]

                if self.on_tool_call:
                    self.on_tool_call(tool_name, tool_args)

                result = self._exec_tool(tool_name, tool_args)
                self.history.append("tool", f"{tool_name}: {result}", step=step)

                if self.on_tool_result:
                    self.on_tool_result(tool_name, result)

                # Save full raw response so model remembers its reasoning
                messages.append({"role": "assistant", "content": raw_assembled})
                messages.append({
                    "role":    "user",
                    "content": f"[Tool result for {tool_name}]\n{result}",
                })
                debug(f"Tool result injected, continuing to step {step + 1}")
                continue

            # ── No action, no ENDOFOP — model just talked ─────────────
            messages.append({"role": "assistant", "content": raw_assembled})
            debug(f"No action on step {step}. Nudging model.")
            messages.append({
                "role":    "user",
                "content": (
                    "Continue. Use an <action> tool call to make progress, "
                    "or use <ENDOFOP> if the task is fully complete."
                ),
            })

        warn("Max steps reached without ENDOFOP.")
        return "[MAX STEPS] Agent stopped without completing the task."

    def run_goal(self, goal, max_cycles=5, max_retries=3):
        debug(f"Goal mode started: {goal}")
        from axonix.core.loop import LoopEngine
        return LoopEngine(self, max_cycles=max_cycles, max_retries=max_retries).run_goal(goal)
