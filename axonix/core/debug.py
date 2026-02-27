import os
import sys
import json
from datetime import datetime

# Enable debug mode if AXONIX_DEBUG is set to 1, true, or yes
DEBUG_MODE = os.environ.get("AXONIX_DEBUG", "").lower() in ("1", "true", "yes")

class C:
    GRAY   = "\033[90m"
    CYAN   = "\033[96m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    RESET  = "\033[0m"
    BOLD   = "\033[1m"

def log(msg, level="INFO"):
    if not DEBUG_MODE and level == "DEBUG":
        return
    
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    color = C.GRAY
    if level == "DEBUG": color = C.CYAN
    if level == "WARN":  color = C.YELLOW
    if level == "ERROR": color = C.RED
    
    prefix = f"{C.GRAY}[{timestamp}]{C.RESET} {color}{level:<5}{C.RESET} "
    
    # Handle multi-line messages
    lines = str(msg).splitlines()
    if not lines: lines = [""]
    
    print(f"{prefix}{lines[0]}")
    for line in lines[1:]:
        print(f"{' ' * len(f'[{timestamp}] INFO  ')}{line}")

def debug(msg):
    log(msg, "DEBUG")

def info(msg):
    log(msg, "INFO")

def warn(msg):
    log(msg, "WARN")

def error(msg):
    log(msg, "ERROR")

def log_json(data, label="JSON"):
    if not DEBUG_MODE:
        return
    try:
        formatted = json.dumps(data, indent=2)
        debug(f"{label}:
{formatted}")
    except:
        debug(f"{label}: {data}")
