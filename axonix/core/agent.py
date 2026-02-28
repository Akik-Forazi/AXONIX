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

━━━ RESPONSE FORMAT ━━━
You MUST use these exact XML tags in your responses:

1. THINKING — wrap your reasoning:
<thought>
your reasoning here about what to do next
</thought>

2. TOOL CALL — call a tool:
<action>
{"tool": "tool_name", "args": {"arg1": "value1", "arg2": "value2"}}
</action>

3. TASK COMPLETE — when fully done:
<ENDOFOP>
Brief summary of what was accomplished
</ENDOFOP>

━━━ AVAILABLE TOOLS ━━━
file_read(path)                         — read file with line numbers
file_write(path, content)               — write/overwrite a file
file_edit(path, old, new)               — find and replace text in file
file_append(path, content)              — append text to file
file_delete(path)                       — delete file or directory
file_list(path=".")                     — list directory contents
file_search(path=".", pattern="*")      — find files by glob pattern
shell_run(command)                      — run Windows CMD command
shell_python(code)                      — execute Python code
web_get(url)                            — fetch URL content
web_search(query)                       — search web via DuckDuckGo
code_lint(path)                         — lint Python with flake8
code_format(path)                       — format Python with black
code_tree(path=".")                     — show file tree
code_analyze(path=".")                  — architectural overview of Python code
memory_save(key, value)                 — save to persistent memory
memory_get(key)                         — get from memory
memory_list()                           — list all memory keys

━━━ RULES ━━━
- Always wrap reasoning in <thought> tags first
- One <action> at a time — wait for the result before the next
- Verify your work after writing files or running commands
- Use <ENDOFOP> ONLY when the task is truly and completely done
- Never skip the <ENDOFOP> tag — always close the task
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
            "code_analyze": self.code_tools.analyze,
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

    def _get_system_prompt(self):
        mem_data = self.memory.all()
        mem_str = ""
        if mem_data:
            mem_str = "\n\n━━━━━━━━━━ PERSISTENT MEMORY ━━━━━━━━━━\n"
            for k, v in mem_data.items():
                mem_str += f"{k}: {v}\n"
        
        return SYSTEM_PROMPT + mem_str

    def run(self, task: str):
        """
        Streaming agent loop with real-time tag parsing.
        """
        from axonix.core.stream_parser import StreamParser

        debug(f"Agent starting task: {task}")
        self._finished     = False
        self._final_result = None

        # Inject current memory into the system prompt
        current_system_prompt = self._get_system_prompt()

        messages = [
            {"role": "system",  "content": current_system_prompt},
            {"role": "user",    "content": task},
        ]
        self.history.append("user", task, mode="agent")

        max_steps = int(self.config.get("max_steps", 30))
        action_history = [] # Track (tool, args) to detect loops

        for step in range(1, max_steps + 1):
            debug(f"--- Step {step}/{max_steps} ---")
            if self.on_step:
                self.on_step(step, max_steps)

            # ── Collect full streamed response, firing callbacks mid-stream ──
            full_response   = []   # all tokens accumulated
            action_pending  = []   # set when <action> fires, holds (tool, args)
            endofop_summary = []   # set when <ENDOFOP> fires

            def on_text(token):
                full_response.append(token)
                if self.on_token:
                    self.on_token(token)

            def on_thought(content):
                debug(f"Thought: {content[:120]}")
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
                    parser.feed(token)

                    # If action was detected mid-stream, stop reading and execute
                    if action_pending:
                        break

                    # If ENDOFOP detected, stop reading
                    if endofop_summary:
                        break

                parser.flush()

            except Exception as e:
                error(f"Stream error on step {step}: {e}")
                import traceback
                debug(traceback.format_exc())
                return f"[ERROR] Stream failed: {e}"

            assembled = "".join(full_response)
            self.history.append("assistant", assembled, step=step)

            # ── ENDOFOP — task is done ─────────────────────────────────
            if endofop_summary:
                summary = endofop_summary[0]
                self._finished     = True
                self._final_result = summary
                messages.append({"role": "assistant", "content": assembled})
                if self.on_done:
                    self.on_done(summary)
                info(f"Task completed: {summary[:120]}")
                return summary

            # ── ACTION — execute tool and continue ────────────────────
            if action_pending:
                tool_name, tool_args = action_pending[0]

                # Loop Detection
                action_sig = (tool_name, json.dumps(tool_args, sort_keys=True))
                action_history.append(action_sig)
                
                repeat_count = action_history.count(action_sig)
                if repeat_count >= 3:
                    warn(f"Repetitive action detected: {tool_name}. Count: {repeat_count}")
                    messages.append({
                        "role": "user",
                        "content": f"You have already called {tool_name} with these arguments {repeat_count} times. If the result wasn't what you expected, try a different approach or tool. If you are stuck, think about what's missing."
                    })
                
                if repeat_count >= 5:
                    error("Max repetitions reached. Aborting to prevent loop.")
                    return f"[ERROR] Agent got stuck in a loop calling {tool_name}."

                if self.on_tool_call:
                    self.on_tool_call(tool_name, tool_args)

                result = self._exec_tool(tool_name, tool_args)
                self.history.append("tool", f"{tool_name}: {result}", step=step)

                if self.on_tool_result:
                    self.on_tool_result(tool_name, result)

                # Inject into message history and continue
                messages.append({"role": "assistant", "content": assembled})
                messages.append({
                    "role":    "user",
                    "content": f"[Tool result for {tool_name}]\n{result}",
                })
                debug(f"Tool result injected, continuing to step {step + 1}")
                continue

            # ── No action, no ENDOFOP — model just talked ─────────────
            messages.append({"role": "assistant", "content": assembled})
            debug(f"No action on step {step}. Nudging model.")
            messages.append({
                "role":    "user",
                "content": (
                    "Continue. Use a <action> tool call to make progress, "
                    "or use <ENDOFOP> if the task is fully complete."
                ),
            })

        warn("Max steps reached without ENDOFOP.")
        return "[MAX STEPS] Agent stopped without completing the task."


    def run_goal(self, goal, max_cycles=5, max_retries=3):
        debug(f"Goal mode started: {goal}")
        from axonix.core.loop import LoopEngine
        return LoopEngine(self, max_cycles=max_cycles, max_retries=max_retries).run_goal(goal)
