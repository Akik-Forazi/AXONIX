"""
DevNet First-Run Setup
Auto-imports all GGUFs from ~/.devnet/models/ into Ollama.
Runs silently on first launch, or manually via: devnet setup
"""

import os
import sys
import json
import subprocess
import urllib.request
from devnet.core.config import MODELS_DIR, DEVNET_HOME, load_config, save_config
from devnet.core.cli import C, rule, Spinner


# ── Modelfile template ─────────────────────────────────────
# Maps model folder names to known chat templates.
# Ollama needs the right template to format prompts correctly.
TEMPLATE_MAP = {
    "gemma3":        "gemma2",        # gemma3 uses gemma2 template in Ollama
    "gemma":         "gemma2",
    "qwen":          "qwen2.5",
    "deepseek":      "deepseek-v2",
    "phi":           "phi3",
    "llama":         "llama3.2",
    "mistral":       "mistral",
    "llava":         "llava",
    "moondream":     "moondream",
    "nemotron":      "nemotron-mini",
}

def _infer_template(folder_name: str) -> str:
    """Guess the Ollama base template from the model folder name."""
    low = folder_name.lower()
    for key, template in TEMPLATE_MAP.items():
        if key in low:
            return template
    return "llama3.2"  # safe fallback


def _find_gguf(folder_path: str) -> str | None:
    """Find the first .gguf file directly inside a model folder."""
    try:
        for f in os.listdir(folder_path):
            if f.endswith(".gguf"):
                return os.path.join(folder_path, f)
    except Exception:
        pass
    return None


def _ollama_running() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        return True
    except Exception:
        return False


def _ollama_model_exists(name: str) -> bool:
    try:
        data = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        models = json.loads(data.read()).get("models", [])
        names = [m["name"] for m in models]
        return name in names or f"{name}:latest" in names
    except Exception:
        return False


def _create_modelfile(gguf_path: str, template: str, folder_name: str) -> str:
    """Write a Modelfile and return its path."""
    modelfile_path = os.path.join(DEVNET_HOME, f"Modelfile.{folder_name}")
    content = f'FROM "{gguf_path}"\n'
    with open(modelfile_path, "w") as f:
        f.write(content)
    return modelfile_path


def _import_model(folder_name: str, gguf_path: str) -> bool:
    """
    Register a GGUF with Ollama using 'ollama create'.
    Returns True on success.
    """
    template     = _infer_template(folder_name)
    modelfile    = _create_modelfile(gguf_path, template, folder_name)
    ollama_name  = folder_name  # use folder name as the Ollama model name

    try:
        result = subprocess.run(
            ["ollama", "create", ollama_name, "-f", modelfile],
            capture_output=True,
            text=True,
            timeout=300,
        )
        # Clean up Modelfile
        try:
            os.remove(modelfile)
        except Exception:
            pass

        if result.returncode == 0:
            return True
        else:
            print(f"  {C.RED}✗ ollama create failed for {folder_name}:{C.RESET}")
            print(f"  {C.DGRAY}{result.stderr.strip()[:200]}{C.RESET}")
            return False
    except FileNotFoundError:
        print(f"  {C.RED}✗ 'ollama' command not found. Is Ollama installed?{C.RESET}")
        print(f"  {C.CYAN}Download: https://ollama.com/download{C.RESET}")
        return False
    except subprocess.TimeoutExpired:
        print(f"  {C.RED}✗ Timed out importing {folder_name}{C.RESET}")
        return False


def scan_local_models() -> list[dict]:
    """
    Scan ~/.devnet/models/ and return a list of
    {name, gguf_path} dicts for models that have a GGUF file.
    """
    found = []
    if not os.path.isdir(MODELS_DIR):
        return found
    for folder in sorted(os.listdir(MODELS_DIR)):
        folder_path = os.path.join(MODELS_DIR, folder)
        if not os.path.isdir(folder_path):
            continue
        gguf = _find_gguf(folder_path)
        if gguf:
            found.append({"name": folder, "gguf_path": gguf})
    return found


def run_setup(force: bool = False, silent: bool = False) -> list[str]:
    """
    Main setup entry point.
    Scans ~/.devnet/models/, imports any un-registered GGUFs into Ollama.
    Returns list of successfully imported model names.

    Args:
        force:  Re-import even if already registered.
        silent: Suppress output (for background first-run).
    """

    def log(msg):
        if not silent:
            print(msg)

    # ── Check Ollama is running ────────────────────────────
    if not _ollama_running():
        log(f"\n  {C.RED}✗ Ollama is not running.{C.RESET}")
        log(f"  {C.GRAY}Start it with:{C.RESET} {C.CYAN}ollama serve{C.RESET}")
        log(f"  {C.GRAY}Or install from:{C.RESET} {C.CYAN}https://ollama.com/download{C.RESET}\n")
        return []

    # ── Scan local GGUFs ───────────────────────────────────
    models = scan_local_models()
    if not models:
        log(f"  {C.YELLOW}No GGUF models found in {MODELS_DIR}{C.RESET}")
        return []

    log(f"\n  {C.BOLD}{C.WHITE}DevNet Setup{C.RESET}  {C.DGRAY}— importing models into Ollama{C.RESET}")
    log(f"  {C.DGRAY}Found {len(models)} model(s) in {MODELS_DIR}{C.RESET}\n")

    imported = []

    for m in models:
        name      = m["name"]
        gguf_path = m["gguf_path"]
        gguf_name = os.path.basename(gguf_path)
        size_gb   = os.path.getsize(gguf_path) / (1024 ** 3)

        # Skip if already registered
        if not force and _ollama_model_exists(name):
            log(f"  {C.GREEN}✓{C.RESET}  {C.WHITE}{name}{C.RESET}  {C.DGRAY}already registered{C.RESET}")
            imported.append(name)
            continue

        log(f"  {C.BLUE}↑{C.RESET}  {C.WHITE}{name}{C.RESET}  {C.DGRAY}{gguf_name} ({size_gb:.1f} GB){C.RESET}")

        spinner = None
        if not silent:
            spinner = Spinner(f"Importing {name}…")
            spinner.start()

        ok = _import_model(name, gguf_path)

        if spinner:
            spinner.stop()

        if ok:
            log(f"  {C.GREEN}✓{C.RESET}  {C.WHITE}{name}{C.RESET}  {C.DGRAY}imported{C.RESET}")
            imported.append(name)
        else:
            log(f"  {C.RED}✗{C.RESET}  {C.WHITE}{name}{C.RESET}  {C.DGRAY}failed{C.RESET}")

    # ── Update config to use first available model ─────────
    if imported:
        cfg = load_config()
        if not cfg.get("model_name") or cfg.get("model_name") not in imported:
            # prefer gemma3-4b if available, else first imported
            default = "gemma3-4b" if "gemma3-4b" in imported else imported[0]
            cfg["model_name"] = default
            cfg["backend"]    = "ollama"
            save_config(cfg)
            log(f"\n  {C.GREEN}✓{C.RESET} Default model set to {C.BLUE}{default}{C.RESET}")

    log(f"\n  {C.DGRAY}Done. {len(imported)}/{len(models)} model(s) ready.{C.RESET}\n")
    return imported


def ensure_setup_done() -> bool:
    """
    Called on every launch.
    If Ollama has no DevNet models registered at all, runs setup silently.
    Returns True if at least one model is available.
    """
    if not _ollama_running():
        return False

    # Check if any of our models are already in Ollama
    models = scan_local_models()
    if not models:
        return False

    for m in models:
        if _ollama_model_exists(m["name"]):
            return True  # at least one is registered, we're good

    # None registered yet — run setup silently
    imported = run_setup(silent=True)
    return len(imported) > 0
