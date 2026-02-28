"""
This module serves as the central registry for all AI models supported by AXONIX-ZERO.
It provides detailed metadata for each model variant, including hardware requirements
and performance expectations, ensuring users can select the best "brain" for their tasks.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelVariant:
    """
    Represents a specific AI model configuration.
    Includes technical specifications and human-readable guidance on its intended use.
    """
    name: str                    # A short, memorable identifier (e.g., "qwen-coder").
    gguf_name: str               # The technical filename used for local execution.
    repo: str                    # The source repository on HuggingFace.
    size_gb: float               # Disk space footprint in Gigabytes.
    ram_gb: float                # Minimum system memory required for stable operation.
    ctx: int                     # Maximum context window (token limit).
    temperature: float           # The optimized creativity setting for this model.
    max_tokens: int              # Safe upper limit for generated responses.
    tags: list[str]              # Functional categories (e.g., ["coding", "reasoning"]).
    description: str             # A concise summary of the model's architecture.
    best_for: str                # Practical advice on when to use this model.
    speed_toks: str              # Expected performance on standard hardware.
    recommended: bool = False    # Whether this is the primary choice for most users.

    @property
    def hf_url(self) -> str:
        """Returns the direct link to the model's home on HuggingFace."""
        return f"https://huggingface.co/{self.repo}"

    def fits(self, available_ram_gb: float = 14.0) -> bool:
        """Determines if the current system has enough memory to run this model."""
        return self.ram_gb <= available_ram_gb


# ── The Global Model Registry ──────────────────────────────
# These models have been carefully vetted for performance on typical mobile/desktop CPUs.

REGISTRY: dict[str, ModelVariant] = {

    # ── Default Local Selection ─────────────────────────────

    "gemma3-4b": ModelVariant(
        name="gemma3-4b",
        gguf_name="Gemma-3-4B-VL-it-Gemini-Pro-Heretic-Uncensored-Thinking_Q8_0.gguf",
        repo="local",
        size_gb=4.5,
        ram_gb=6.0,
        ctx=8192,
        temperature=0.7,
        max_tokens=4096,
        tags=["local", "general", "multimodal", "vision", "reasoning"],
        description="Gemma 3 4B VL — A versatile multimodal model combining vision and language.",
        best_for="General assistance, visual analysis, and logical reasoning.",
        speed_toks="5–9 tok/s",
        recommended=True,
    ),


    # ── Specialized Coding Models ──────────────────────────

    "qwen-coder": ModelVariant(
        name="qwen-coder",
        gguf_name="qwen2.5-coder-7b-instruct-q6_k.gguf",
        repo="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        size_gb=5.9,
        ram_gb=8.5,
        ctx=8192,
        temperature=0.2,
        max_tokens=4096,
        tags=["coding", "professional", "agentic"],
        description="Qwen2.5-Coder 7B — A state-of-the-art model for software development.",
        best_for="Python, JavaScript, SQL, and complex architectural tasks.",
        speed_toks="3–5 tok/s",
    ),

    "phi35-mini": ModelVariant(
        name="phi35-mini",
        gguf_name="Phi-3.5-mini-instruct-Q4_K_M.gguf",
        repo="bartowski/Phi-3.5-mini-instruct-GGUF",
        size_gb=2.4,
        ram_gb=3.5,
        ctx=8192,
        temperature=0.3,
        max_tokens=2048,
        tags=["fast", "lightweight", "efficient"],
        description="Phi-3.5 Mini — A compact yet surprisingly powerful model from Microsoft.",
        best_for="Low-latency tasks and lightweight coding automation.",
        speed_toks="10–14 tok/s",
    ),

    # ── General Purpose & Lightweight ──────────────────────

    "llama32-3b": ModelVariant(
        name="llama32-3b",
        gguf_name="Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        repo="bartowski/Llama-3.2-3B-Instruct-GGUF",
        size_gb=2.0,
        ram_gb=3.0,
        ctx=4096,
        temperature=0.6,
        max_tokens=2048,
        tags=["fast", "standard", "chat"],
        description="Llama 3.2 3B — Meta's highly efficient model for general interaction.",
        best_for="Quick chat, simple explanations, and high-speed feedback.",
        speed_toks="12–18 tok/s",
    ),
}


def get(name: str) -> Optional[ModelVariant]:
    """Retrieves a model configuration by its registry name."""
    return REGISTRY.get(name)


def recommended() -> ModelVariant:
    """Returns the primary model recommended for AXONIX-ZERO."""
    for m in REGISTRY.values():
        if m.recommended:
            return m
    return list(REGISTRY.values())[0]


def by_tag(tag: str) -> list[ModelVariant]:
    """Filters the registry for models matching a specific capability tag."""
    return [m for m in REGISTRY.values() if tag in m.tags]


def fits_device(ram_gb: float = 14.0) -> list[ModelVariant]:
    """Returns all models that can safely operate within the specified RAM limit."""
    return [m for m in REGISTRY.values() if m.fits(ram_gb)]


def all_models() -> list[ModelVariant]:
    """Provides a complete list of all registered model variants."""
    return list(REGISTRY.values())


def show_table():
    """Renders a professional, color-coded table of available models in the terminal."""
    from axonix.core.cli import C
    rows = []
    for m in REGISTRY.values():
        rec = " ★" if m.recommended else ""
        tag_str = ", ".join(m.tags[:3])
        rows.append((m.name + rec, f"{m.size_gb}GB", m.speed_toks, tag_str, m.best_for[:45]))

    col_w = [20, 8, 14, 22, 46]
    header = ["MODEL", "SIZE", "SPEED (CPU)", "TAGS", "BEST FOR"]

    sep = "  " + "─" * (sum(col_w) + len(col_w) * 2)
    print(f"\n{C.BOLD}{C.WHITE}  Available Intelligence Variants{C.RESET}")
    print(sep)
    h = "  " + "  ".join(f"{C.GRAY}{h:<{w}}{C.RESET}" for h, w in zip(header, col_w))
    print(h)
    print(sep)
    for row in rows:
        colored = []
        for i, (cell, w) in enumerate(zip(row, col_w)):
            if i == 0:
                color = C.BLUE if "★" in cell else C.WHITE
            elif i == 1:
                color = C.GRAY
            elif i == 2:
                color = C.GREEN
            elif i == 3:
                color = C.PURPLE
            else:
                color = C.DGRAY
            colored.append(f"{color}{cell:<{w}}{C.RESET}")
        print("  " + "  ".join(colored))
    print(sep)
    print(f"  {C.DGRAY}★ = Standard Recommendation  ·  Command: axonix model use <name>{C.RESET}\n")
