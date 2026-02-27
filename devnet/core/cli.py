"""
DevNet CLI — Claude Code / Gemini CLI style terminal experience
Rich, interactive, with live spinner, panels, syntax hints
Pure stdlib + optional 'rich' library for premium output
"""

import sys
import os
import time
import threading
import shutil
import textwrap
import itertools
import json
from typing import Optional


# ── Terminal capability detection ──────────────────────────
def _supports_color() -> bool:
    if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
        return False
    if os.environ.get('NO_COLOR'):
        return False
    return True

HAS_COLOR = _supports_color()
TERM_W, _ = shutil.get_terminal_size((100, 40))


# ── ANSI palette ───────────────────────────────────────────
class C:
    """ANSI color constants. Disabled automatically if no color support."""
    _on = HAS_COLOR

    def _c(code): return f"\033[{code}m" if HAS_COLOR else ""

    RESET   = _c("0")
    BOLD    = _c("1")
    DIM     = _c("2")
    ITALIC  = _c("3")

    # Foregrounds
    WHITE   = _c("97")
    GRAY    = _c("90")
    DGRAY   = _c("38;5;240")
    CYAN    = _c("96")
    BLUE    = _c("94")
    GREEN   = _c("92")
    YELLOW  = _c("93")
    RED     = _c("91")
    PURPLE  = _c("95")
    ORANGE  = _c("38;5;214")

    # Backgrounds
    BG_BLUE = _c("44")
    BG_DARK = _c("40")

    @staticmethod
    def rgb(r, g, b):
        if not HAS_COLOR: return ""
        return f"\033[38;2;{r};{g};{b}m"


# ── Unicode box drawing ────────────────────────────────────
BOX = {
    'tl': '╭', 'tr': '╮', 'bl': '╰', 'br': '╯',
    'h': '─', 'v': '│',
    'ml': '├', 'mr': '┤',
}
HEAVY = {
    'tl': '┌', 'tr': '┐', 'bl': '└', 'br': '┘',
    'h': '─', 'v': '│',
}

# Spinner frames — Gemini-style orbiting
SPINNER_FRAMES = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
SPINNER_BRAILLE = itertools.cycle(SPINNER_FRAMES)


# ── Spinner class ──────────────────────────────────────────
class Spinner:
    def __init__(self, label: str = "Working"):
        self.label = label
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._current_label = label

    def update(self, label: str):
        self._current_label = label

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        frames = itertools.cycle(SPINNER_FRAMES)
        while not self._stop.is_set():
            f = next(frames)
            label = self._current_label
            line = f"  {C.BLUE}{f}{C.RESET} {C.GRAY}{label}{C.RESET}"
            sys.stdout.write(f"\r{line}   ")
            sys.stdout.flush()
            time.sleep(0.08)

    def stop(self, final_msg: str = ""):
        self._stop.set()
        if self._thread:
            self._thread.join()
        sys.stdout.write(f"\r{' ' * (TERM_W - 1)}\r")
        sys.stdout.flush()
        if final_msg:
            print(f"  {C.GREEN}✓{C.RESET} {C.GRAY}{final_msg}{C.RESET}")


# ── Print helpers ──────────────────────────────────────────
def w(n=1): print('\n' * (n-1))

def rule(char='─', color=C.DGRAY):
    print(f"{color}{char * min(TERM_W, 80)}{C.RESET}")

def panel(title: str, content: str, color=C.BLUE, width: int = None):
    """Render a bordered panel like Claude Code output."""
    w = min(TERM_W - 4, width or 78)
    title_str = f" {title} "
    line_len = w - len(title_str) - 2
    top = f"  {color}{BOX['tl']}{BOX['h']}{title_str}{BOX['h'] * line_len}{BOX['tr']}{C.RESET}"
    bot = f"  {color}{BOX['bl']}{BOX['h'] * (w)}{BOX['br']}{C.RESET}"
    print(top)
    for line in content.splitlines():
        wrapped = textwrap.wrap(line, w - 4) or ['']
        for wl in wrapped:
            pad = ' ' * (w - 2 - len(wl))
            print(f"  {color}{BOX['v']}{C.RESET} {wl}{pad} {color}{BOX['v']}{C.RESET}")
    print(bot)

def tag(label: str, text: str, lc=C.BLUE, tc=C.WHITE):
    """[LABEL] text — compact info line."""
    print(f"  {lc}{C.BOLD}[{label}]{C.RESET} {tc}{text}{C.RESET}")

def kv(key: str, val: str, kc=C.GRAY, vc=C.WHITE):
    print(f"  {kc}{key:<14}{C.RESET}{vc}{val}{C.RESET}")

def section(title: str):
    print(f"\n  {C.DGRAY}{title.upper()}{C.RESET}")
    print(f"  {C.DGRAY}{'─' * len(title)}{C.RESET}")

def tool_line(name: str, args_preview: str, status: str = "→", color=C.BLUE):
    arrow = {
        "→": f"{C.BLUE}→{C.RESET}",
        "✓": f"{C.GREEN}✓{C.RESET}",
        "✗": f"{C.RED}✗{C.RESET}",
        "⋯": f"{C.YELLOW}⋯{C.RESET}",
    }.get(status, status)
    name_s = f"{color}{C.BOLD}{name}{C.RESET}"
    args_s = f"{C.DGRAY}{args_preview[:60]}{C.RESET}"
    print(f"   {arrow} {name_s}  {args_s}")

def result_line(text: str, truncate: int = 200):
    preview = text.strip().replace('\n', ' ')
    if len(preview) > truncate:
        preview = preview[:truncate] + '…'
    print(f"   {C.DGRAY}└ {preview}{C.RESET}")

def err_line(text: str):
    print(f"   {C.RED}✗ {text}{C.RESET}")

def step_line(step: int, total: int, label: str = ""):
    bar_w = 16
    filled = int(bar_w * step / max(total, 1))
    bar = f"{C.BLUE}{'█' * filled}{C.DGRAY}{'░' * (bar_w - filled)}{C.RESET}"
    s = f"  {C.DGRAY}step {step}/{total}{C.RESET}  {bar}  {C.GRAY}{label}{C.RESET}"
    print(s)


# ── Banner ────────────────────────────────────────────────
BANNER_ART = r"""
   ██████╗ ███████╗██╗   ██╗███╗   ██╗███████╗████████╗
   ██╔══██╗██╔════╝██║   ██║████╗  ██║██╔════╝╚══██╔══╝
   ██║  ██║█████╗  ██║   ██║██╔██╗ ██║█████╗     ██║
   ██║  ██║██╔══╝  ╚██╗ ██╔╝██║╚██╗██║██╔══╝     ██║
   ██████╔╝███████╗ ╚████╔╝ ██║ ╚████║███████╗   ██║
   ╚═════╝ ╚══════╝  ╚═══╝  ╚═╝  ╚═══╝╚══════╝   ╚═╝
"""

def print_banner(version="1.0.0", model="local", backend="direct", model_path=""):
    if HAS_COLOR:
        art_colored = ""
        for ch in BANNER_ART:
            if ch in "█╗╝╔╚═║":
                art_colored += C.BLUE + ch + C.RESET
            else:
                art_colored += C.GRAY + ch + C.RESET
        print(art_colored)
    else:
        print(BANNER_ART)

    import os
    backend_label = f"{C.GREEN}direct (in-process){C.RESET}" if backend == "direct" else f"{C.YELLOW}server{C.RESET}"
    fname = os.path.basename(model_path) if model_path else "(no model set)"
    print(f"  {C.GRAY}backend    {backend_label}")
    print(f"  {C.GRAY}model      {C.WHITE}{model}{C.RESET}  {C.DGRAY}·{C.RESET}  {C.DGRAY}{fname}{C.RESET}")
    print(f"  {C.GRAY}version    {C.DGRAY}v{version}{C.RESET}")
    print()


def print_help():
    print(f"\n  {C.BOLD}{C.WHITE}Commands{C.RESET}")
    cmds = [
        ("agent",          "use tools to complete tasks step-by-step"),
        ("chat",           "direct conversation (no tools)"),
        ("goal",           "moltbot mode: run continuously until goal achieved"),
        ("", ""),
        ("models",         "list all available model variants"),
        ("model use <n>",  "switch active model  e.g. model use qwen-coder"),
        ("model info <n>", "show model details + HuggingFace link"),
        ("", ""),
        ("reset",          "clear conversation history"),
        ("memory",         "show persistent memory"),
        ("health",         "check llama.cpp server"),
        ("config",         "show current configuration"),
        ("tree",           "show workspace file tree"),
        ("!<cmd>",         "run a shell command directly"),
        ("exit",           "quit DevNet"),
    ]
    for cmd, desc in cmds:
        if not cmd:
            print()
            continue
        print(f"  {C.BLUE}{cmd:<20}{C.RESET}{C.GRAY}{desc}{C.RESET}")
    print()


# ── Main interactive CLI ───────────────────────────────────
class CLI:
    """
    Premium interactive CLI — Claude Code / Gemini CLI aesthetic.
    Call CLI(agent).run() from runner.
    """

    PROMPT_CHAT  = f"  {C.DGRAY}╰─{C.RESET} {C.WHITE}"
    PROMPT_AGENT = f"  {C.DGRAY}╰─{C.RESET} {C.BLUE}{C.BOLD}"
    PROMPT_RESET = C.RESET

    def __init__(self, agent, web_url: str = None):
        self.agent = agent
        self.web_url = web_url
        self.mode = "agent"

    def _prompt(self):
        mode_badge = (
            f"{C.BLUE}agent{C.RESET}" if self.mode == "agent"
            else f"{C.GRAY}chat{C.RESET}"
        )
        cwd = os.path.basename(os.path.abspath(self.agent.workspace))
        return (
            f"\n  {C.DGRAY}╭─ {C.RESET}{C.GRAY}{cwd}{C.RESET}"
            f"  {C.DGRAY}[{mode_badge}{C.DGRAY}]{C.RESET}\n"
            f"  {C.DGRAY}╰─{C.RESET} "
        )

    def _print_agent_msg(self, text: str):
        """Pretty-print agent response like Claude Code."""
        if not text:
            return
        print()
        lines = text.split('\n')
        in_code = False
        code_buf = []
        code_lang = ""

        for line in lines:
            if line.startswith('```'):
                if not in_code:
                    in_code = True
                    code_lang = line[3:].strip() or "code"
                    code_buf = []
                else:
                    in_code = False
                    self._print_code_block(code_lang, '\n'.join(code_buf))
                    code_buf = []
                    code_lang = ""
            elif in_code:
                code_buf.append(line)
            else:
                # Inline code
                rendered = self._render_inline(line)
                if rendered.strip():
                    print(f"  {C.WHITE}{rendered}{C.RESET}")
                else:
                    print()

    def _render_inline(self, text: str) -> str:
        """Render inline markdown in text."""
        import re
        # Bold
        text = re.sub(r'\*\*(.*?)\*\*', f'{C.BOLD}\\1{C.RESET}{C.WHITE}', text)
        # Inline code
        text = re.sub(r'`([^`]+)`', f'{C.PURPLE}\\1{C.RESET}{C.WHITE}', text)
        return text

    def _print_code_block(self, lang: str, code: str):
        """Print a syntax-highlighted-ish code block."""
        w = min(TERM_W - 6, 74)
        top_line = f"  {C.DGRAY}┌── {lang} {'─' * (w - len(lang) - 5)}┐{C.RESET}"
        bot_line = f"  {C.DGRAY}└{'─' * (w)}┘{C.RESET}"
        print(top_line)
        for line in code.split('\n'):
            # Very basic keyword colorization
            colored = self._colorize_code(line)
            padding = max(0, w - len(line) - 1)
            print(f"  {C.DGRAY}│{C.RESET}  {colored}{' ' * padding}{C.DGRAY}│{C.RESET}")
        print(bot_line)

    def _colorize_code(self, line: str) -> str:
        """Minimal syntax coloring for code lines."""
        import re
        kw = r'\b(def|class|import|from|return|if|elif|else|for|while|try|except|with|as|pass|break|continue|and|or|not|in|is|True|False|None|async|await|yield|lambda|global|nonlocal)\b'
        # Strings
        s = re.sub(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"]*"|\'[^\']*\')', f'{C.GREEN}\\1{C.RESET}', line)
        # Keywords
        s = re.sub(kw, f'{C.BLUE}\\1{C.RESET}', s)
        # Comments
        if '#' in s:
            idx = s.index('#')
            s = s[:idx] + C.DGRAY + s[idx:] + C.RESET
        return s

    def _print_tool_start(self, name: str, args: dict):
        args_preview = ', '.join(f'{k}={repr(v)[:30]}' for k, v in args.items())
        print(f"\n   {C.BLUE}⟳{C.RESET}  {C.BOLD}{C.BLUE}{name}{C.RESET}  {C.DGRAY}{args_preview}{C.RESET}")

    def _print_tool_done(self, name: str, result: str):
        preview = result.strip().replace('\n', ' ')[:120]
        print(f"   {C.GREEN}✓{C.RESET}  {C.DGRAY}{preview}{C.RESET}")

    def _print_step(self, step: int, total: int):
        bar_w = 14
        filled = int(bar_w * step / max(total, 1))
        bar = f"{C.BLUE}{'▪' * filled}{C.DGRAY}{'·' * (bar_w - filled)}{C.RESET}"
        pct = int(100 * step / max(total, 1))
        print(f"\n  {C.DGRAY}step {step}/{total}  {bar}  {pct}%{C.RESET}")

    def _run_agent(self, task: str):
        """Run agent task with rich CLI output."""
        steps_done = []
        state = {"spinner": Spinner("Thinking…")}
        state["spinner"].start()

        def on_step(s, total):
            state["spinner"].update(f"Step {s}/{total}…")
            steps_done.append(s)

        def on_tool_call(name, args):
            state["spinner"].stop()
            self._print_tool_start(name, args)
            state["spinner"] = Spinner(f"Running {name}…")
            state["spinner"].start()

        def on_tool_result(name, result):
            state["spinner"].stop()
            self._print_tool_done(name, result)
            state["spinner"] = Spinner("Thinking…")
            state["spinner"].start()

        def on_token(token):
            # In agent mode, model sometimes emits text before tool calls
            pass

        self.agent.on_step        = on_step
        self.agent.on_tool_call   = on_tool_call
        self.agent.on_tool_result = on_tool_result
        self.agent.on_token       = on_token
        self.agent.on_done        = None

        try:
            result = self.agent.run(task)
        finally:
            state["spinner"].stop()

        print()
        rule('─', C.DGRAY)
        self._print_agent_msg(result)
        rule('─', C.DGRAY)
        if steps_done:
            print(f"  {C.DGRAY}completed in {len(steps_done)} step(s){C.RESET}")

    def _run_chat(self, message: str):
        """Run chat with spinner then print response."""
        spinner = Spinner("Thinking…")
        spinner.start()
        try:
            response = self.agent.chat(message)
        finally:
            spinner.stop()
        print()
        rule('─', C.DGRAY)
        self._print_agent_msg(response)
        rule('─', C.DGRAY)

    def _run_goal(self, goal: str):
        """Moltbot-style continuous loop until goal achieved."""
        print(f"\n  {C.BLUE}◆{C.RESET} {C.BOLD}{C.WHITE}Goal Mode{C.RESET} {C.DGRAY}— continuous until target reached{C.RESET}\n")
        from devnet.core.loop import LoopEngine
        engine = LoopEngine(
            agent=self.agent,
            max_cycles=5,
            max_retries=3,
            max_steps_per_task=self.agent.max_steps,
            verbose=True,
        )
        result = engine.run_goal(goal)
        print(f"\n  {C.GREEN}◆ {result}{C.RESET}")

    def run(self):
        """Main REPL loop."""
        print(f"  {C.GRAY}Type a task · {C.BLUE}agent{C.GRAY}/{C.GRAY}chat{C.GRAY}/{C.GRAY}goal{C.GRAY} modes · {C.BLUE}models{C.GRAY} to list · {C.GRAY}exit to quit{C.RESET}")
        if self.web_url:
            print(f"  {C.GRAY}Web UI → {C.CYAN}{self.web_url}{C.RESET}")
        print()

        while True:
            try:
                try:
                    text = input(self._prompt()).strip()
                    sys.stdout.write(C.RESET)
                    sys.stdout.flush()
                except EOFError:
                    break

                if not text:
                    continue

                low = text.lower()

                # ── Built-in commands ──
                if low in ('exit', 'quit', 'q', ':q'):
                    print(f"\n  {C.GRAY}Goodbye.{C.RESET}\n")
                    break

                elif low in ('help', '?', 'h'):
                    print_help()

                elif low == 'agent':
                    self.mode = 'agent'
                    print(f"  {C.BLUE}● agent mode{C.RESET} {C.DGRAY}— tools enabled{C.RESET}")

                elif low == 'chat':
                    self.mode = 'chat'
                    print(f"  {C.GRAY}● chat mode{C.RESET} {C.DGRAY}— direct conversation{C.RESET}")

                elif low in ('goal', 'g'):
                    self.mode = 'goal'
                    print(f"  {C.PURPLE}◆ goal mode{C.RESET} {C.DGRAY}— continuous loop until target reached{C.RESET}")

                elif low == 'models':
                    from devnet.core.models import show_table
                    show_table()

                elif low.startswith('model use '):
                    name = text[len('model use '):].strip()
                    result = self.agent.switch_model(name)
                    color = C.GREEN if '[OK]' in result else C.RED
                    print(f"  {color}{result}{C.RESET}")

                elif low.startswith('model info '):
                    name = text[len('model info '):].strip()
                    from devnet.core.models import get as gm
                    m = gm(name)
                    if m:
                        section(f"Model: {m.name}")
                        kv('file', m.gguf_name)
                        kv('repo', m.repo)
                        kv('size', f"{m.size_gb}GB")
                        kv('ram needed', f"{m.ram_gb}GB")
                        kv('context', str(m.ctx))
                        kv('temperature', str(m.temperature))
                        kv('speed', m.speed_toks)
                        kv('tags', ', '.join(m.tags))
                        kv('best for', m.best_for)
                        print(f"\n  {C.CYAN}Download: {m.hf_url}{C.RESET}")
                    else:
                        print(f"  {C.RED}Unknown model '{name}'{C.RESET}")

                elif low == 'reset':
                    self.agent.reset()
                    print(f"  {C.YELLOW}↺{C.RESET} {C.GRAY}Conversation cleared.{C.RESET}")

                elif low == 'memory':
                    mem = self.agent.memory.all()
                    if not mem:
                        print(f"  {C.DGRAY}(empty){C.RESET}")
                    else:
                        section("Memory")
                        for k, v in mem.items():
                            kv(k, str(v)[:80])

                elif low == 'health':
                    h = self.agent.health()
                    ok = h.get('status') == 'ok'
                    color = C.GREEN if ok else C.RED
                    icon  = '●' if ok else '○'
                    model = h.get('model', self.agent.model_name)
                    print(f"  {color}{icon}{C.RESET} Ollama {color}{h.get('status', '?')}{C.RESET}  {C.DGRAY}·{C.RESET} {C.GRAY}{model}{C.RESET}  {C.DGRAY}@{C.RESET} {C.GRAY}{self.agent.base_url}{C.RESET}")

                elif low == 'config':
                    from devnet.core.config import load_config
                    cfg = load_config()
                    section("Configuration")
                    for k, v in cfg.items():
                        kv(k, str(v))

                elif low == 'tree':
                    from devnet.tools.code_tools import CodeTools
                    ct = CodeTools(self.agent.workspace)
                    tree_str = ct.tree(self.agent.workspace)
                    print()
                    for line in tree_str.split('\n'):
                        print(f"  {C.DGRAY}{line}{C.RESET}")

                elif low.startswith('!'):
                    # Shell passthrough
                    cmd = text[1:].strip()
                    from devnet.tools.shell_tools import ShellTools
                    st = ShellTools(self.agent.workspace)
                    result = st.run(cmd)
                    print()
                    for line in result.split('\n'):
                        print(f"  {C.DGRAY}{line}{C.RESET}")

                else:
                    # ── Run task ──
                    if self.mode == 'goal':
                        self._run_goal(text)
                    elif self.mode == 'agent':
                        self._run_agent(text)
                    else:
                        self._run_chat(text)

            except KeyboardInterrupt:
                print(f"\n  {C.YELLOW}Interrupted.{C.RESET} {C.DGRAY}Type 'exit' to quit.{C.RESET}")
            except Exception as e:
                print(f"\n  {C.RED}Error: {e}{C.RESET}")
