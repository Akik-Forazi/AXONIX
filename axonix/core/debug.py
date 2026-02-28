"""
This module provides diagnostic and logging capabilities for AXONIX-ZERO.
It helps developers and advanced users understand the internal state of the agent,
trace communication with AI backends, and debug tool executions.
"""

import os
import sys
import json
from datetime import datetime

# Enable verbose diagnostic output if AXONIX_DEBUG is active in the environment.
DEBUG_MODE = os.environ.get("AXONIX_DEBUG", "").lower() in ("1", "true", "yes")

class C:
    """ANSI color escape codes for professional terminal output."""
    GRAY   = "\033[90m"
    CYAN   = "\033[96m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    RESET  = "\033[0m"
    BOLD   = "\033[1m"

def log(msg, level="INFO"):
    """
    Core logging function that formats and prints system messages.
    Includes timestamps and severity levels for precise tracing.
    """
    if not DEBUG_MODE and level == "DEBUG":
        return
    
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    color = C.GRAY
    if level == "DEBUG": color = C.CYAN
    if level == "WARN":  color = C.YELLOW
    if level == "ERROR": color = C.RED
    
    prefix = f"{C.GRAY}[{timestamp}]{C.RESET} {color}{level:<5}{C.RESET} "
    
    # Ensure multi-line messages are formatted with consistent indentation.
    lines = str(msg).splitlines()
    if not lines: lines = [""]
    
    print(f"{prefix}{lines[0]}")
    for line in lines[1:]:
        print(f"{' ' * len(f'[{timestamp}] INFO  ')}{line}")

def debug(msg):
    """Logs a detailed diagnostic message, visible only in debug mode."""
    log(msg, "DEBUG")

def info(msg):
    """Logs a general informational message about system activity."""
    log(msg, "INFO")

def warn(msg):
    """Logs a warning about an unexpected but non-critical condition."""
    log(msg, "WARN")

def error(msg):
    """Logs a critical error that might impact system stability."""
    log(msg, "ERROR")

def log_json(data, label="JSON DATA"):
    """Pretty-prints a data structure for clear inspection during debugging."""
    if not DEBUG_MODE:
        return
    try:
        formatted = json.dumps(data, indent=2)
        debug(f"{label}:\n{formatted}")
    except Exception:
        # Fallback if the data is not JSON serializable.
        debug(f"{label}: {data}")
