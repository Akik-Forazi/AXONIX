"""
DevNet Runner — Ollama backend
"""

import argparse
import sys
import os
import time
import threading
from devnet.core.config import load_config, save_config
from devnet.core.cli import CLI, print_banner, C, kv, section


def _build_agent(overrides: dict = None):
    cfg = load_config()
    if overrides:
        cfg.update({k: v for k, v in overrides.items() if v is not None})
    from devnet.core.agent import Agent
    return Agent(
        model_name  = cfg.get("model_name",  "gemma3-4b"),
        temperature = float(cfg.get("temperature", 0.2)),
        max_tokens  = int(cfg.get("max_tokens",    4096)),
        max_steps   = int(cfg.get("max_steps",     30)),
        workspace   = cfg.get("workspace",   "."),
        base_url    = cfg.get("base_url",    "http://localhost:11434"),
    )


def _check_ollama(cfg: dict):
    from devnet.core.backend import ollama_running, ollama_model_exists
    model_name = cfg.get("model_name", "gemma3-4b")

    if not ollama_running():
        print(f"\n  {C.RED}✗ Ollama is not running.{C.RESET}")
        print(f"  {C.GRAY}Start it:{C.RESET}   {C.CYAN}ollama serve{C.RESET}")
        print(f"  {C.GRAY}Install:{C.RESET}    {C.CYAN}https://ollama.com/download{C.RESET}\n")
        sys.exit(1)

    if not ollama_model_exists(model_name):
        print(f"  {C.YELLOW}⚠  '{model_name}' not in Ollama — running setup…{C.RESET}")
        from devnet.core.first_run import run_setup
        imported = run_setup()
        if model_name not in imported and f"{model_name}:latest" not in imported:
            print(f"  {C.RED}✗ Could not import '{model_name}'.{C.RESET}")
            print(f"  {C.GRAY}Run: devnet setup{C.RESET}\n")
            sys.exit(1)

    print(f"  {C.GREEN}✓{C.RESET} {C.GRAY}Ollama · {model_name}{C.RESET}")


class Runner:
    def __init__(self):
        self.cfg = load_config()

    def _ov(self, args) -> dict:
        ov = {}
        for k in ("model_name", "base_url", "max_steps", "temperature", "max_tokens", "workspace"):
            v = getattr(args, k, None)
            if v is not None:
                ov[k] = v
        return ov

    def run_local(self, args):
        ov    = self._ov(args)
        cfg   = {**self.cfg, **ov}
        agent = _build_agent(ov)
        print_banner(model=cfg.get("model_name", "gemma3-4b"), backend="ollama", model_path="")
        _check_ollama(cfg)
        web_url = None
        if getattr(args, "web", False):
            port    = getattr(args, "port", 7860)
            web_url = f"http://localhost:{port}"
            self._start_web(agent, port)
        CLI(agent, web_url=web_url).run()

    def run_agent(self, task: str, args):
        ov    = self._ov(args)
        cfg   = {**self.cfg, **ov}
        agent = _build_agent(ov)
        print_banner(model=cfg.get("model_name", "gemma3-4b"), backend="ollama", model_path="")
        _check_ollama(cfg)
        CLI(agent)._run_agent(task)

    def run_cli(self, args):
        ov    = self._ov(args)
        cfg   = {**self.cfg, **ov}
        agent = _build_agent(ov)
        print_banner(model=cfg.get("model_name", "gemma3-4b"), backend="ollama", model_path="")
        _check_ollama(cfg)
        task = sys.stdin.read().strip() if not sys.stdin.isatty() else input(f"  {C.DGRAY}Task:{C.RESET} ").strip()
        if task:
            CLI(agent)._run_agent(task)

    def _start_web(self, agent, port: int):
        from devnet.web.server import WebServer
        ws = WebServer(agent=agent, port=port)
        t  = threading.Thread(target=ws.start, kwargs={"open_browser": True}, daemon=True)
        t.start()
        time.sleep(0.6)
        print(f"  {C.CYAN}Web UI → http://localhost:{port}{C.RESET}")


# ═══════════════════════════════════════════════════════════
#  CLI ENTRY
# ═══════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(prog="devnet", add_help=False)
    p.add_argument("--help", "-h", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    def add_common(sp):
        sp.add_argument("--model",     dest="model_name",  type=str,   default=None, help="Ollama model name")
        sp.add_argument("--url",       dest="base_url",    type=str,   default=None, help="Ollama base URL")
        sp.add_argument("--steps",     dest="max_steps",   type=int,   default=None, help="Max agent steps")
        sp.add_argument("--temp",      dest="temperature", type=float, default=None, help="Temperature")
        sp.add_argument("--tokens",    dest="max_tokens",  type=int,   default=None, help="Max tokens")
        sp.add_argument("--workspace", dest="workspace",   type=str,   default=None, help="Workspace directory")
        return sp

    # devnet run
    rp = add_common(sub.add_parser("run", add_help=False))
    rp.add_argument("mode", nargs="?")
    rp.add_argument("task", nargs="?")
    rp.add_argument("--lc",  action="store_true", help="Interactive CLI mode")
    rp.add_argument("--cli", action="store_true", help="One-shot stdin mode")
    rp.add_argument("-w", "--web", action="store_true", help="Also start web UI")
    rp.add_argument("--port", type=int, default=7860)

    # devnet model
    mp = sub.add_parser("model", add_help=False)
    mp.add_argument("action", nargs="?", default="list", choices=["list", "use", "info"])
    mp.add_argument("name",   nargs="?", default=None)

    # devnet config
    cp = sub.add_parser("config", add_help=False)
    cp.add_argument("action",    nargs="?",  default="show", choices=["show", "set", "reset"])
    cp.add_argument("--model",   dest="model_name",  type=str,   default=None)
    cp.add_argument("--url",     dest="base_url",    type=str,   default=None)
    cp.add_argument("--steps",   dest="max_steps",   type=int,   default=None)
    cp.add_argument("--temp",    dest="temperature", type=float, default=None)
    cp.add_argument("--tokens",  dest="max_tokens",  type=int,   default=None)

    # devnet memory
    memp = sub.add_parser("memory", add_help=False)
    memp.add_argument("action", nargs="?", default="list", choices=["list", "clear"])

    # devnet setup
    sub.add_parser("setup", add_help=False)

    # devnet web
    wp = sub.add_parser("web", add_help=False)
    wp.add_argument("--port", type=int, default=7860)

    args   = p.parse_args()
    runner = Runner()

    # ── No command / --help ────────────────────────────────
    if args.help or args.cmd is None:
        cfg = load_config()
        print_banner(model=cfg.get("model_name", "gemma3-4b"), backend="ollama", model_path="")
        print(f"  {C.BOLD}Usage{C.RESET}\n")
        cmds = [
            ("devnet run --lc",                "interactive agent mode"),
            ("devnet run --lc -w",             "interactive + web UI at :7860"),
            ("devnet run --cli",               "one-shot stdin task"),
            ("devnet run agent \"<task>\"",    "run a single task"),
            ("",                               ""),
            ("devnet model list",              "show all models"),
            ("devnet model use <name>",        "switch active model"),
            ("devnet model info <name>",       "show model details"),
            ("",                               ""),
            ("devnet setup",                   "import GGUFs from ~/.devnet/models/ into Ollama"),
            ("devnet config show",             "show current config"),
            ("devnet config set --model <n>",  "set active model"),
            ("devnet memory list",             "show agent memory"),
            ("devnet web",                     "web UI only"),
        ]
        for cmd, desc in cmds:
            if not cmd:
                print()
                continue
            print(f"  {C.BLUE}{cmd:<42}{C.RESET}{C.DGRAY}{desc}{C.RESET}")
        print()
        return

    # ── devnet run ─────────────────────────────────────────
    if args.cmd == "run":
        if getattr(args, "lc", False):
            runner.run_local(args)
        elif getattr(args, "cli", False):
            runner.run_cli(args)
        elif args.mode == "agent" and args.task:
            runner.run_agent(args.task, args)
        elif args.mode and not args.task:
            runner.run_agent(args.mode, args)
        else:
            runner.run_local(args)

    # ── devnet model ───────────────────────────────────────
    elif args.cmd == "model":
        from devnet.core.models import show_table, get as gm
        action = getattr(args, "action", "list")
        name   = getattr(args, "name",   None)

        if action == "list":
            show_table()

        elif action == "use":
            if not name:
                print(f"  {C.RED}Usage: devnet model use <name>{C.RESET}")
            else:
                m = gm(name)
                if not m:
                    print(f"  {C.RED}Unknown model '{name}'. Run: devnet model list{C.RESET}")
                else:
                    from devnet.core.backend import ollama_model_exists
                    cfg = load_config()
                    cfg["model_name"]  = m.name
                    cfg["temperature"] = m.temperature
                    cfg["max_tokens"]  = m.max_tokens
                    save_config(cfg)
                    if ollama_model_exists(m.name):
                        print(f"  {C.GREEN}✓ Switched to {m.name}{C.RESET}")
                    else:
                        print(f"  {C.YELLOW}⚠  '{m.name}' saved as default but not in Ollama yet.{C.RESET}")
                        print(f"  {C.GRAY}Run: devnet setup   to import it.{C.RESET}")

        elif action == "info":
            if not name:
                print(f"  {C.RED}Usage: devnet model info <name>{C.RESET}")
            else:
                m = gm(name)
                if m:
                    section(f"Model: {m.name}")
                    kv("file",     m.gguf_name)
                    kv("size",     f"{m.size_gb} GB")
                    kv("RAM",      f"{m.ram_gb} GB")
                    kv("context",  str(m.ctx))
                    kv("temp",     str(m.temperature))
                    kv("speed",    m.speed_toks)
                    kv("tags",     ", ".join(m.tags))
                    kv("best for", m.best_for)
                    print(f"\n  {C.CYAN}{m.hf_url}{C.RESET}\n")
                else:
                    print(f"  {C.RED}Unknown: {name}{C.RESET}")

    # ── devnet config ──────────────────────────────────────
    elif args.cmd == "config":
        from devnet.core.config import show_config, reset_config
        if args.action == "show":
            show_config()
        elif args.action == "set":
            cfg = load_config()
            for k in ("model_name", "base_url", "max_steps", "temperature", "max_tokens"):
                v = getattr(args, k, None)
                if v is not None:
                    cfg[k] = v
            save_config(cfg)
            show_config()
        elif args.action == "reset":
            reset_config()

    # ── devnet memory ──────────────────────────────────────
    elif args.cmd == "memory":
        from devnet.core.memory import Memory
        mem = Memory()
        if args.action == "list":
            data = mem.all()
            if not data:
                print(f"  {C.DGRAY}(empty){C.RESET}")
            else:
                section("Memory")
                for k, v in data.items():
                    kv(k, str(v)[:80])
        elif args.action == "clear":
            mem.clear()
            print(f"  {C.GREEN}✓ Memory cleared{C.RESET}")

    # ── devnet setup ───────────────────────────────────────
    elif args.cmd == "setup":
        from devnet.core.first_run import run_setup
        run_setup(force=False)

    # ── devnet web ─────────────────────────────────────────
    elif args.cmd == "web":
        cfg   = load_config()
        agent = _build_agent({})
        print_banner(model=cfg.get("model_name", "gemma3-4b"), backend="ollama", model_path="")
        _check_ollama(cfg)
        from devnet.web.server import WebServer
        port = args.port
        print(f"  {C.CYAN}Web UI → http://localhost:{port}{C.RESET}")
        print(f"  {C.DGRAY}Ctrl+C to stop{C.RESET}\n")
        try:
            WebServer(agent=agent, port=port).start(open_browser=True)
        except KeyboardInterrupt:
            print(f"\n  {C.GRAY}Stopped.{C.RESET}")


if __name__ == "__main__":
    main()
