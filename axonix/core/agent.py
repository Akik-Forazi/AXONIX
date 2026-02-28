"""
This is the heart of AXONIX-ZERO. It's where the agent lives, breathes, and figures out
how to help you with your code. It handles the tools, remembers what you've said,
and talks to the AI backends.
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

# This is how we tell the AI how to behave. We want it to be a helpful friend,
# not just a cold machine.
SYSTEM_PROMPT = """Hello! I am AXONIX-ZERO, your local AI coding friend. 
I'm here to help you build, fix, and understand your projects right here on Windows.

I'll think through your problems out loud so you can see what's on my mind, 
and then I'll use my tools to get things done.

How I communicate:
1. When I'm thinking, I'll wrap it in <thought> tags.
2. When I need to use a tool, I'll use an <action> block with a little JSON inside.
3. When I'm all finished and you've got what you need, I'll let you know using <ENDOFOP>.

I'll try my best to use the right tools for the job. If I'm writing files, I'll 
usually use 'file_write' instead of a shell command because it's safer.

Let's build something great together!
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
    """
    Think of this class as the "brain" of our agent. It keeps track of 
    your files, your history, and your local memory.
    """
    def __init__(self, **kwargs):
        # We set everything up here, connecting all our tools and loading our memory.
        self.config      = kwargs
        self.memory      = Memory()
        self.workspace   = os.path.abspath(kwargs.get("workspace", "."))
        self.file_tools  = FileTools(self.workspace)
        self.shell_tools = ShellTools(self.workspace)
        self.web_tools   = WebTools()
        self.code_tools  = CodeTools(self.workspace)
        self.history     = ChatHistory(self.workspace)

        # This map helps us find the right tool when the AI asks for it.
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
        # Time to wake up the backend!
        from axonix.core.backend import get_backend
        # No tool schemas — we use streaming text-based tool parsing
        self.llm = get_backend(self.config, tools=None)
        debug(f"Connected to the {type(self.llm).__name__} backend.")

    def _rebuild_llm(self):
        # Just in case we need to restart the brain.
        self._build_llm()

    def _done(self, result=""):
        # We call this when the mission is accomplished.
        self._finished     = True
        self._final_result = result
        debug(f"Task finished! Result: {result}")
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
        # This is where we actually run the tools the AI asked for.
        if name not in self._tool_map:
            warn(f"I don't know how to use a tool called '{name}'.")
            return f"[ERROR] Unknown tool '{name}'"
        
        debug(f"Running the '{name}' tool...")
        try:
            r = self._tool_map[name](**args)
            result = str(r) if r is not None else "OK"
            debug(f"Tool '{name}' result (first 100 chars): {result[:100]}...")
            return result
        except TypeError as e:
            msg = f"It looks like I got the wrong ingredients for '{name}': {e}"
            error(msg)
            return f"[ERROR] {msg}"
        except Exception as e:
            msg = f"Something went wrong while using '{name}': {e}"
            error(msg)
            import traceback
            debug(traceback.format_exc())
            return f"[ERROR] {msg}"

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
        # We grab everything we've remembered so far and add it to the prompt
        # so the AI doesn't forget who we are or what we're working on.
        mem_data = self.memory.all()
        mem_str = ""
        if mem_data:
            mem_str = "\n\n━━━━━━━━━━ MY MEMORY ━━━━━━━━━━\n"
            for k, v in mem_data.items():
                mem_str += f"{k}: {v}\n"
        
        return SYSTEM_PROMPT + mem_str

    def run(self, task: str):
        """
        This is the main loop where the agent works through a task.
        It listens to the AI, parses its thoughts and actions, 
        and keeps going until the job is done.
        """
        from axonix.core.stream_parser import StreamParser

        debug(f"Starting work on: {task}")
        self._finished     = False
        self._final_result = None

        # Make sure the AI has all its memories before it starts.
        current_system_prompt = self._get_system_prompt()

        messages = [
            {"role": "system",  "content": current_system_prompt},
            {"role": "user",    "content": task},
        ]
        self.history.append("user", task, mode="agent")

        max_steps = int(self.config.get("max_steps", 30))
        action_history = [] # Track (tool, args) to detect loops

        for step in range(1, max_steps + 1):
            debug(f"Working on step {step} of {max_steps}...")
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
                debug("I'm thinking about something...")
                if self.on_thought:
                    self.on_thought(content)

            def on_action(tool, args):
                debug(f"I've decided to use the '{tool}' tool.")
                action_pending.append((tool, args))

            def on_endofop(summary):
                debug("I think I'm finished!")
                endofop_summary.append(summary)

            def on_parse_error(msg):
                warn(f"Had a little trouble parsing: {msg}")

            parser = StreamParser(
                on_text    = on_text,
                on_thought = on_thought,
                on_action  = on_action,
                on_endofop = on_endofop,
                on_error   = on_parse_error,
            )

            # Let's see what the AI has to say.
            try:
                for token in self.llm.stream_text(messages):
                    parser.feed(token)
                    if action_pending or endofop_summary:
                        break # We've got an action or we're done, no need to keep listening for now.
                parser.flush()
            except Exception as e:
                error(f"Lost the connection on step {step}: {e}")
                import traceback
                debug(traceback.format_exc())
                return f"[ERROR] Connection failed: {e}"

            assembled = "".join(full_response)
            self.history.append("assistant", assembled, step=step)

            # Did the AI say it was finished?
            if endofop_summary:
                summary = endofop_summary[0]
                self._finished     = True
                self._final_result = summary
                messages.append({"role": "assistant", "content": assembled})
                if self.on_done: self.on_done(summary)
                info("All done with this task!")
                return summary

            # Did it ask to use a tool?
            if action_pending:
                tool_name, tool_args = action_pending[0]

                # Let's make sure we're not just doing the same thing over and over.
                action_sig = (tool_name, json.dumps(tool_args, sort_keys=True))
                action_history.append(action_sig)
                
                repeat_count = action_history.count(action_sig)
                if repeat_count >= 3:
                    warn(f"Wait, I've already done this {repeat_count} times...")
                    messages.append({
                        "role": "user",
                        "content": "It looks like we're repeating ourselves. Maybe try a different tool?"
                    })
                
                if repeat_count >= 5:
                    error("I'm stuck in a loop. I'd better stop before I make things worse.")
                    return f"[ERROR] Stuck in a loop calling {tool_name}."

                if self.on_tool_call:
                    self.on_tool_call(tool_name, tool_args)

                result = self._exec_tool(tool_name, tool_args)
                self.history.append("tool", f"{tool_name}: {result}", step=step)

                if self.on_tool_result:
                    self.on_tool_result(tool_name, result)

                # Tell the AI what happened and let it continue.
                messages.append({"role": "assistant", "content": assembled})
                messages.append({
                    "role":    "user",
                    "content": f"The '{tool_name}' tool returned:\n{result}",
                })
                debug(f"Result from {tool_name} is in. Moving to step {step + 1}")
                continue

            # If it didn't use a tool or finish, we'll give it a gentle nudge.
            messages.append({"role": "assistant", "content": assembled})
            debug("The AI just talked without acting. I'll nudge it.")
            messages.append({
                "role":    "user",
                "content": "Keep going! Use a tool or let me know if you're finished.",
            })

        warn("I've reached my limit of steps for this task.")
        return "I had to stop because I reached my maximum number of steps."


    def run_goal(self, goal, max_cycles=5, max_retries=3):
        debug(f"Goal mode started: {goal}")
        from axonix.core.loop import LoopEngine
        return LoopEngine(self, max_cycles=max_cycles, max_retries=max_retries).run_goal(goal)
