"""
This module serves as the primary entry point for AXONIX-ZERO.
It handles command-line argument parsing, agent initialization, 
and orchestrates the various operating modes (CLI, Web, and Goal mode).
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
    """
    Manages the setup and health of the AXONIX-ZERO operational environment.
    Ensures that backends are responsive and models are correctly loaded.
    """
    def __init__(self):
        debug("Initializing system runner...")
        self.cfg = load_config()
        debug(f"Configuration loaded from: {AXONIX_HOME}")

    def build_agent(self, overrides: dict = None):
        """
        Constructs an Agent instance with the appropriate configuration.
        Applies any runtime overrides provided via the command line.
        """
        debug("Assembling the agent instance...")
        cfg = self.cfg.copy()
        if overrides:
            debug(f"Applying runtime overrides: {overrides}")
            cfg.update({k: v for k, v in overrides.items() if v is not None})
        
        # We automatically detect if a local GGUF model is available to prioritize local performance.
        model_name = cfg.get("model_name", "gemma3-4b")
        from axonix.core.models import get as gm
        m = gm(model_name)
        
        if m:
            gguf_path = os.path.join(MODELS_DIR, m.gguf_name)
            if os.path.exists(gguf_path) and cfg.get("backend") != "ollama":
                debug(f"Local model detected at {gguf_path}. Optimizing for local execution.")
                cfg["provider"] = "llamacpp"
                cfg["model_path"] = gguf_path

        from axonix.core.agent import Agent
        return Agent(**cfg)

    def check_backend(self, agent):
        """
        Verifies that the AI backend is operational and ready for interaction.
        Triggers setup procedures if necessary components are missing.
        """
        debug("Performing backend integrity check...")
        health = agent.health()
        debug(f"Backend status: {health}")
        
        if health["status"] == "ok":
            return True
        
        backend_type = health.get("backend", "unknown")
        if backend_type == "ollama":
            from axonix.core.backend import ollama_running, ollama_model_exists
            if not ollama_running():
                print(f"\n  {C.RED}✗ Connection failed: Ollama service is not active.{C.RESET}")
                print(f"  {C.GRAY}Resolution:{C.RESET} Please execute {C.CYAN}ollama serve{C.RESET} in a new terminal.\n")
                return False
            
            model_name = agent.config.get("model_name", "gemma3-4b")
            if not ollama_model_exists(model_name):
                print(f"  {C.YELLOW}⚠ Model '{model_name}' not found. Initializing setup...{C.RESET}")
                from axonix.core.first_run import run_setup
                run_setup()
        
        # Final attempt to wake up the model.
        debug("Attempting to initialize model memory...")
        res = agent.load_model()
        if res != "ok":
            error(f"Model initialization failed: {res}")
            print(f"  {C.RED}✗ System error: {res}{C.RESET}")
            return False
        
        debug("System ready. All backends are operational.")
        return True


def _start_web(agent, port: int) -> str:
    """Launches the AXONIX-ZERO Web Interface in a background thread."""
    from axonix.web.server import WebServer
    ws = WebServer(agent=agent, port=port)
    t  = threading.Thread(target=ws.start, kwargs={"open_browser": True}, daemon=True)
    t.start()
    time.sleep(0.8)
    url = f"http://localhost:{port}"
    print(f"  {C.CYAN}Web Dashboard accessible at: {url}{C.RESET}")
    return url


def _make_parser():
    """Defines the command-line interface and acceptable parameters."""
    p = argparse.ArgumentParser(prog="axonix", add_help=False)
    p.add_argument("positional", nargs="*")
    p.add_argument("--lc",     action="store_true", help="Start in interactive agent mode.")
    p.add_argument("--cli",    action="store_true", help="Execute a single command via CLI.")
    p.add_argument("--web",    "-w", action="store_true", help="Launch the web-based interface.")
    p.add_argument("--goal",   type=str, default=None, metavar="GOAL", help="Run in continuous Goal Mode.")
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
    """Translates command-line arguments into a configuration override dictionary."""
    ov = {}
    for k in ("model_name", "base_url", "max_steps", "temperature", "max_tokens", "workspace"):
        v = getattr(args, k, None)
        if v is not None:
            ov[k] = v
    if getattr(args, "n_ctx", None) and not args.max_tokens:
        ov["max_tokens"] = args.n_ctx
    return ov


def _print_help(cfg):
    """Displays a clean, professional help manual for AXONIX-ZERO."""
    print_banner(model=cfg.get("model_name", "gemma3-4b"), backend=cfg.get("backend", "ollama"))
    print(f"  {C.BOLD}User Manual{C.RESET}\n")
    sections = [
        ("OPERATING MODES", [
            ("axonix",                                    "Launch interactive agent interface."),
            ("axonix --cli",                              "Execute a direct task from terminal."),
            ("axonix --web",                              "Start the web-based dashboard."),
            ('axonix --goal "<objective>"',               "Autonomous continuous execution mode."),
        ]),
        ("SYSTEM PARAMETERS", [
            ("--model <name>",   "Specify the AI model variant."),
            ("--steps <n>",      "Limit the maximum autonomous steps."),
            ("--temp <value>",   "Adjust response creativity (0.0 to 2.0)."),
            ("--url <endpoint>", "Set the backend API connection string."),
            ("--port <n>",       "Specify the Web UI listening port."),
        ]),
        ("MANAGEMENT COMMANDS", [
            ("axonix model list",             "View available intelligence models."),
            ("axonix config show",            "Inspect current system settings."),
            ("axonix setup",                  "Import local models into the system."),
        ]),
    ]
    for title, cmds in sections:
        print(f"\n  {C.BOLD}{C.WHITE}{title}{C.RESET}")
        print(f"  {C.DGRAY}{'─' * 60}{C.RESET}")
        for cmd, desc in cmds:
            print(f"  {C.BLUE}{cmd:<46}{C.RESET}{C.DGRAY}{desc}{C.RESET}")
    print()


def main():
    """Primary execution logic for the AXONIX-ZERO application."""
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

    # Handle specific management subcommands.
    if pos and pos[0] in ("model", "models"):
        from axonix.core.models import show_table, get as gm
        action = pos[1] if len(pos) > 1 else "list"
        name   = pos[2] if len(pos) > 2 else None
        if action in ("list", "ls", "all"):
            show_table()
        elif action == "use":
            if not name:
                print(f"  {C.RED}Usage: axonix model use <name>{C.RESET}"); return
            m = gm(name)
            if not m:
                print(f"  {C.RED}Error: Intelligence variant '{name}' not found.{C.RESET}"); return
            cfg["model_name"] = m.name; cfg["temperature"] = m.temperature; cfg["max_tokens"] = m.max_tokens
            save_config(cfg)
            print(f"  {C.GREEN}✓ System successfully switched to {m.name}{C.RESET}")
        return

    # Show help if no action is specified.
    if not pos and not args.lc and not args.cli and not args.web and not args.goal:
        _print_help(cfg)
        return

    # Assemble the agent with current settings.
    agent = runner.build_agent(ov)
    merged = agent.config
    
    # Check backend integrity before proceeding.
    if not runner.check_backend(agent):
        sys.exit(1)

    # Launch Web Mode if requested.
    if args.web and not args.lc and not args.cli and not args.goal:
        print(f"  {C.GRAY}Web service active. Press Ctrl+C to terminate.{C.RESET}\n")
        try:
            from axonix.web.server import WebServer
            WebServer(agent=agent, port=args.port).start(open_browser=True)
        except KeyboardInterrupt:
            print(f"\n  {C.GRAY}Service stopped.{C.RESET}")
        return

    # Handle direct one-shot tasks.
    task = None
    if args.cli:
        task = sys.stdin.read().strip() if not sys.stdin.isatty() else input(f"  {C.DGRAY}Command:{C.RESET} ").strip()
    elif pos and pos[0] not in ("run", "web", "config", "memory", "setup"):
        task = " ".join(pos).strip()
    elif pos and pos[0] == "run" and len(pos) > 1:
        task = " ".join(pos[1:]).strip()

    if task:
        CLI(agent)._run_agent(task)
        return

    # Handle autonomous Goal Mode.
    if args.goal:
        CLI(agent)._run_goal(args.goal)
        return

    # Enter standard Interactive Agent Mode.
    web_url = None
    if args.web:
        web_url = _start_web(agent, args.port)
    CLI(agent, web_url=web_url).run()


if __name__ == "__main__":
    main()
