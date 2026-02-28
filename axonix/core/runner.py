"""
Axonix Runner — Unified CLI entry point
"""

import argparse
import sys
import os
import time
import threading
from axonix.core.config import load_config, save_config, AXONIX_HOME, MODELS_DIR
from axonix.core.cli import CLI, print_banner, C, kv, section
from axonix.core.debug import debug, info, warn, error

class Runner:
    """Entry point for Axonix logic."""
    def __init__(self):
        debug("Runner initializing...")
        self.cfg = load_config()
        debug(f"Loaded config from {AXONIX_HOME}")

    def build_agent(self, overrides: dict = None):
        debug("Building agent...")
        cfg = self.cfg.copy()
        if overrides:
            debug(f"Applying overrides: {overrides}")
            cfg.update({k: v for k, v in overrides.items() if v is not None})
        
        # Check if we should use local llamacpp automatically if model exists in models dir
        model_name = cfg.get("model_name", "gemma3-4b")
        from axonix.core.models import get as gm
        m = gm(model_name)
        
        if m:
            gguf_path = os.path.join(MODELS_DIR, m.gguf_name)
            if os.path.exists(gguf_path) and cfg.get("backend") != "ollama":
                debug(f"Found GGUF at {gguf_path}, switching to llamacpp backend.")
                cfg["provider"] = "llamacpp"
                cfg["model_path"] = gguf_path

        from axonix.core.agent import Agent
        return Agent(**cfg)

    def check_backend(self, agent):
        """Ensure backend is ready."""
        debug("Checking backend health...")
        health = agent.health()
        debug(f"Health check result: {health}")
        
        if health["status"] == "ok":
            return True
        
        backend_type = health.get("backend", "unknown")
        if backend_type == "ollama":
            from axonix.core.backend import ollama_running, ollama_model_exists
            if not ollama_running():
                print(f"\n  {C.RED}✗ Ollama is not running.{C.RESET}")
                print(f"  {C.GRAY}Start it:{C.RESET}   {C.CYAN}ollama serve{C.RESET}\n")
                return False
            
            model_name = agent.config.get("model_name", "gemma3-4b")
            if not ollama_model_exists(model_name):
                print(f"  {C.YELLOW}⚠  '{model_name}' not in Ollama — running setup…{C.RESET}")
                from axonix.core.first_run import run_setup
                run_setup()
        
        # Try loading
        debug("Attempting to load model...")
        res = agent.load_model()
        if res != "ok":
            error(f"Model load failed: {res}")
            print(f"  {C.RED}✗ {res}{C.RESET}")
            return False
        
        debug("Model loaded successfully.")
        return True


def _start_web(agent, port: int) -> str:
    from axonix.web.server import WebServer
    ws = WebServer(agent=agent, port=port)
    t  = threading.Thread(target=ws.start, kwargs={"open_browser": True}, daemon=True)
    t.start()
    time.sleep(0.8)
    url = f"http://localhost:{port}"
    print(f"  {C.CYAN}Web UI → {url}{C.RESET}")
    return url


def _make_parser():
    p = argparse.ArgumentParser(prog="axonix", add_help=False)
    p.add_argument("positional", nargs="*")
    p.add_argument("--lc",     action="store_true")
    p.add_argument("--cli",    action="store_true")
    p.add_argument("--web",    "-w", action="store_true")
    p.add_argument("--goal",   type=str, default=None, metavar="GOAL")
    p.add_argument("--model",   dest="model_name",  type=str,   default=None)
    p.add_argument("--url",     dest="base_url",    type=str,   default=None)
    p.add_argument("--steps",   dest="max_steps",   type=int,   default=None)
    p.add_argument("--temp",    dest="temperature", type=float, default=None)
    p.add_argument("--tokens",  dest="max_tokens",  type=int,   default=None)
    p.add_argument("--ctx",     dest="n_ctx",       type=int,   default=None)
    p.add_argument("--workspace", dest="workspace", type=str,   default=None)
    p.add_argument("--port",    type=int, default=7860)
    p.add_argument("--help", "-h", action="store_true")
    p.add_argument("--version", action="store_true")
    return p


def _overrides(args) -> dict:
    ov = {}
    for k in ("model_name", "base_url", "max_steps", "temperature", "max_tokens", "workspace"):
        v = getattr(args, k, None)
        if v is not None:
            ov[k] = v
    if getattr(args, "n_ctx", None) and not args.max_tokens:
        ov["max_tokens"] = args.n_ctx
    return ov


def _print_help(cfg):
    print_banner(model=cfg.get("model_name", "gemma3-4b"), backend=cfg.get("backend", "ollama"))
    print(f"  {C.BOLD}Usage{C.RESET}\n")
    sections = [
        ("MODES", [
            ("axonix",                                    "interactive agent  (default)"),
            ("axonix --lc",                               "interactive agent  (explicit)"),
            ("axonix --cli",                              "one-shot task from stdin/prompt"),
            ("axonix --web",                              "web UI only  (opens browser)"),
            ("axonix --lc --web",                         "interactive + web UI"),
            ('axonix "<task>"',                           "run one task and exit"),
            ('axonix --goal "<goal>"',                    "continuous goal mode until done"),
        ]),
        ("MODEL / PARAMS", [
            ("--model <n>",      "set model  e.g. --model qwen-coder"),
            ("--steps <n>",      "max agent steps  (default 30)"),
            ("--temp <f>",       "temperature  e.g. --temp 0.1"),
            ("--tokens <n>",     "max tokens  e.g. --tokens 8192"),
            ("--url <url>",      "Ollama URL  (default localhost:11434)"),
            ("--workspace <dir>","workspace directory"),
            ("--port <n>",       "web UI port  (default 7860)"),
        ]),
        ("SUBCOMMANDS", [
            ("axonix model list",             "list all available models"),
            ("axonix model use <n>",          "switch active model"),
            ("axonix config show",            "show current config"),
            ("axonix config reset",           "reset to defaults"),
            ("axonix memory list",            "show agent memory"),
            ("axonix memory clear",           "wipe agent memory"),
            ("axonix setup",                  "import GGUFs → Ollama"),
        ]),
    ]
    for title, cmds in sections:
        print(f"\n  {C.BOLD}{C.WHITE}{title}{C.RESET}")
        print(f"  {C.DGRAY}{'─' * 60}{C.RESET}")
        for cmd, desc in cmds:
            print(f"  {C.BLUE}{cmd:<46}{C.RESET}{C.DGRAY}{desc}{C.RESET}")
    print()


def main():
    p    = _make_parser()
    args = p.parse_args()
    runner = Runner()
    cfg  = runner.cfg
    ov   = _overrides(args)
    pos  = args.positional

    if args.version:
        print("  AXONIX-ZERO v1.0.0")
        return

    if args.help:
        _print_help(cfg)
        return

    # Handle model subcommands
    if pos and pos[0] in ("model", "models"):
        from axonix.core.models import show_table, get as gm
        action = pos[1] if len(pos) > 1 else "list"
        name   = pos[2] if len(pos) > 2 else None
        if action in ("list", "ls", "all"):
            show_table()
        elif action == "use":
            if not name:
                print(f"  {C.RED}Usage: axonix model use <n>{C.RESET}"); return
            m = gm(name)
            if not m:
                print(f"  {C.RED}Unknown model '{name}'{C.RESET}"); return
            cfg["model_name"] = m.name; cfg["temperature"] = m.temperature; cfg["max_tokens"] = m.max_tokens
            save_config(cfg)
            print(f"  {C.GREEN}✓ Switched to {m.name}{C.RESET}")
        return

    # Default to help if no task and not interactive
    if not pos and not args.lc and not args.cli and not args.web and not args.goal:
        _print_help(cfg)
        return

    # Build agent
    agent = runner.build_agent(ov)
    merged = agent.config
    
    # Print banner
    h = agent.health()
    print_banner(model=merged.get("model_name", "gemma3-4b"), backend=h.get("backend", "local"))
    
    # Check backend
    if not runner.check_backend(agent):
        sys.exit(1)

    # Web UI only mode
    if args.web and not args.lc and not args.cli and not args.goal:
        print(f"  {C.DGRAY}Ctrl+C to stop{C.RESET}\n")
        try:
            from axonix.web.server import WebServer
            WebServer(agent=agent, port=args.port).start(open_browser=True)
        except KeyboardInterrupt:
            print(f"\n  {C.GRAY}Stopped.{C.RESET}")
        return

    # One-shot task
    task = None
    if args.cli:
        task = sys.stdin.read().strip() if not sys.stdin.isatty() else input(f"  {C.DGRAY}Task:{C.RESET} ").strip()
    elif pos and pos[0] not in ("run", "web", "config", "memory", "setup"):
        task = " ".join(pos).strip()
    elif pos and pos[0] == "run" and len(pos) > 1:
        task = " ".join(pos[1:]).strip()

    if task:
        CLI(agent)._run_agent(task)
        return

    # Goal mode
    if args.goal:
        CLI(agent)._run_goal(args.goal)
        return

    # Interactive Loop
    web_url = None
    if args.web:
        web_url = _start_web(agent, args.port)
    CLI(agent, web_url=web_url).run()


if __name__ == "__main__":
    main()
