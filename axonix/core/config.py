"""
This module manages the configuration and environment settings for AXONIX-ZERO.
It handles directory initialization, persistent preferences, and ensures 
consistent behavior across different user environments.
"""

import json
import os

# We establish a central directory in the user's home folder to store all AXONIX-ZERO data.
AXONIX_HOME = os.path.expanduser("~/.axonix")
MODELS_DIR  = os.path.join(AXONIX_HOME, "models")
CONFIG_PATH = os.path.join(AXONIX_HOME, "config.json")
MEMORY_PATH = os.path.join(AXONIX_HOME, "memory.json")
HISTORY_DIR = os.path.join(AXONIX_HOME, "history")

# Ensure necessary directories exist on startup.
os.makedirs(MODELS_DIR,  exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

def model_dir(name: str) -> str:
    """Returns the dedicated path for a specific AI model."""
    return os.path.join(MODELS_DIR, name)

# Standard baseline configuration for a smooth out-of-the-box experience.
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
    """
    Retrieves the user's saved preferences or falls back to defaults.
    This ensures the agent always knows its operating parameters.
    """
    cfg = DEFAULTS.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            # If the config file is corrupted, we prefer safe defaults over crashing.
            pass
    return cfg


def save_config(cfg: dict):
    """Saves the current configuration state to persistent storage."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def show_config():
    """Prints a clean, formatted view of the current settings for the user."""
    cfg = load_config()
    print("\n\033[96m[AXONIX-ZERO Configuration]\033[0m")
    for k, v in cfg.items():
        print(f"  \033[90m{k:<18}\033[0m {v}")
    print(f"\n  Settings file: {CONFIG_PATH}\n")


def set_config(**kwargs):
    """Updates specific settings while keeping others intact."""
    cfg = load_config()
    for k, v in kwargs.items():
        if v is not None:
            cfg[k] = v
    save_config(cfg)
    show_config()


def reset_config():
    """Restores AXONIX-ZERO to its factory-default settings."""
    save_config(DEFAULTS)
    print("\033[93m[Configuration] Reset to default system parameters.\033[0m")
