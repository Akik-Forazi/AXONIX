"""
axonix — Fully Local Super Agentic AI
"""

from axonix.core.agent import Agent
from axonix.core.runner import Runner
from axonix.core.memory import Memory
from axonix.core.loop import LoopEngine
from axonix.core.models import REGISTRY, get as get_model, recommended, by_tag
from axonix.tools.file_tools import FileTools
from axonix.tools.shell_tools import ShellTools
from axonix.tools.web_tools import WebTools
from axonix.tools.code_tools import CodeTools

__version__ = "1.0.0"
__all__ = [
    "Agent", "Runner", "Memory", "LoopEngine",
    "REGISTRY", "get_model", "recommended", "by_tag",
    "FileTools", "ShellTools", "WebTools", "CodeTools",
]
