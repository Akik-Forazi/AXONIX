"""
DevNet Config
"""

import json
import os

DEVNET_HOME = os.path.expanduser("~/.devnet")
MODELS_DIR  = os.path.join(DEVNET_HOME, "models")
CONFIG_PATH = os.path.join(DEVNET_HOME, "config.json")
MEMORY_PATH = os.path.join(DEVNET_HOME, "memory.json")
HISTORY_DIR = os.path.join(DEVNET_HOME, "history")

os.makedirs(MODELS_DIR,  exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

def model_dir(name: str) -> str:
    return os.path.join(MODELS_DIR, name)

DEFAULTS = {
    "backend":     "ollama",
    "model_name":  "gemma3-4b",
    "base_url":    "http://localhost:11434",
    "temperature": 0.2,
    "max_tokens":  4096,
    "max_steps":   30,
    "workspace":   ".",
    "web_port":    7860,
}


def load_config() -> dict:
    cfg = DEFAULTS.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def show_config():
    cfg = load_config()
    print("\n\033[96m[DevNet Config]\033[0m")
    for k, v in cfg.items():
        print(f"  \033[90m{k:<18}\033[0m {v}")
    print(f"\n  File: {CONFIG_PATH}\n")


def set_config(**kwargs):
    cfg = load_config()
    for k, v in kwargs.items():
        if v is not None:
            cfg[k] = v
    save_config(cfg)
    show_config()


def reset_config():
    save_config(DEFAULTS)
    print("\033[93m[Config] Reset to defaults.\033[0m")
