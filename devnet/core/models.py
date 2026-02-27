"""
DevNet Model Registry
All recommended GGUF models for your device (i5-8350U, 16GB RAM, CPU-only)
Switch models with: devnet model use <name>
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelVariant:
    name: str                    # short alias e.g. "qwen-coder"
    gguf_name: str               # actual filename on HuggingFace
    repo: str                    # HuggingFace repo
    size_gb: float               # approximate GGUF size
    ram_gb: float                # RAM needed to run
    ctx: int                     # recommended context size
    temperature: float           # best temperature for this model's use case
    max_tokens: int              # safe max tokens
    tags: list[str]              # e.g. ["coding", "fast", "multimodal"]
    description: str
    best_for: str
    speed_toks: str              # expected tok/s on i5-8350U
    recommended: bool = False    # is this THE recommended pick

    @property
    def hf_url(self) -> str:
        return f"https://huggingface.co/{self.repo}"

    def fits(self, available_ram_gb: float = 14.0) -> bool:
        return self.ram_gb <= available_ram_gb


# ══════════════════════════════════════════════════════════════
#  MODEL REGISTRY
#  Tuned for: Intel i5-8350U · 16GB RAM · CPU-only · Windows 11
# ══════════════════════════════════════════════════════════════

REGISTRY: dict[str, ModelVariant] = {

    # ── LOCAL / CUSTOM (already downloaded) ───────────────────

    "gemma3-4b": ModelVariant(
        name="gemma3-4b",
        gguf_name="Gemma-3-4B-VL-it-Gemini-Pro-Heretic-Uncensored-Thinking_Q8_0.gguf",
        repo="local",
        size_gb=4.5,
        ram_gb=6.0,
        ctx=8192,
        temperature=0.7,
        max_tokens=4096,
        tags=["local", "general", "multimodal", "vision", "reasoning", "uncensored"],
        description="Gemma 3 4B VL — vision+language, Gemini-Pro style, Q8 quality",
        best_for="General assistant, vision tasks, reasoning, uncensored responses",
        speed_toks="5–9 tok/s",
        recommended=True,
    ),


    # ── CODING (Primary dev work) ──────────────────────────────

    "qwen-coder": ModelVariant(
        name="qwen-coder",
        gguf_name="qwen2.5-coder-7b-instruct-q6_k.gguf",
        repo="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        size_gb=5.9,
        ram_gb=8.5,
        ctx=8192,
        temperature=0.2,        # lower = more deterministic code
        max_tokens=4096,
        tags=["coding", "best", "fast", "agentic"],
        description="Qwen2.5-Coder 7B Instruct Q6_K — state-of-the-art 7B coder, superior quality",
        best_for="Python, JS, HTML, SQL, shell scripts, code review, debugging, DevNet agent tasks",
        speed_toks="3–5 tok/s",
    ),

    "qwen-coder-q8": ModelVariant(
        name="qwen-coder-q8",
        gguf_name="Qwen2.5-Coder-7B-Instruct-Q8_0.gguf",
        repo="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        size_gb=7.9,
        ram_gb=9.5,
        ctx=8192,
        temperature=0.2,
        max_tokens=4096,
        tags=["coding", "quality", "slower"],
        description="Qwen2.5-Coder 7B Q8 — higher quality than Q4, uses more RAM but still fits",
        best_for="When you want maximum code quality and can wait a bit longer",
        speed_toks="2–4 tok/s",
    ),

    "deepseek-coder": ModelVariant(
        name="deepseek-coder",
        gguf_name="deepseek-coder-6.7b-instruct.Q4_K_M.gguf",
        repo="TheBloke/deepseek-coder-6.7B-instruct-GGUF",
        size_gb=4.1,
        ram_gb=5.8,
        ctx=4096,
        temperature=0.0,        # DeepSeek-Coder works best at temp=0
        max_tokens=2048,
        tags=["coding", "fast", "lightweight"],
        description="DeepSeek-Coder 6.7B Q4 — very fast, solid at code completion and infilling",
        best_for="Quick code completions, boilerplate, filling in functions",
        speed_toks="5–7 tok/s",
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
        tags=["fast", "lightweight", "general", "coding"],
        description="Phi-3.5 Mini 3.8B Q4 — Microsoft's tiny but surprisingly capable model",
        best_for="Quick questions, fast responses, low-stakes coding tasks",
        speed_toks="10–14 tok/s",
    ),

    # ── GENERAL / CHAT ─────────────────────────────────────────

    "qwen25-general": ModelVariant(
        name="qwen25-general",
        gguf_name="Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        repo="Qwen/Qwen2.5-7B-Instruct-GGUF",
        size_gb=4.7,
        ram_gb=6.5,
        ctx=8192,
        temperature=0.7,
        max_tokens=4096,
        tags=["general", "chat", "reasoning", "coding"],
        description="Qwen2.5 7B Instruct Q4 — best general-purpose 7B, great reasoning + coding",
        best_for="General chat, planning, reasoning, mixed coding+writing tasks",
        speed_toks="4–6 tok/s",
    ),

    "llama32-3b": ModelVariant(
        name="llama32-3b",
        gguf_name="Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        repo="bartowski/Llama-3.2-3B-Instruct-GGUF",
        size_gb=2.0,
        ram_gb=3.0,
        ctx=4096,
        temperature=0.6,
        max_tokens=2048,
        tags=["fast", "lightweight", "general"],
        description="Llama 3.2 3B Q4 — Meta's tiny but capable model, very fast on CPU",
        best_for="Fast responses, simple tasks, when speed matters more than quality",
        speed_toks="12–18 tok/s",
    ),

    "mistral-7b": ModelVariant(
        name="mistral-7b",
        gguf_name="Mistral-7B-Instruct-v0.3.Q4_K_M.gguf",
        repo="MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF",
        size_gb=4.4,
        ram_gb=6.0,
        ctx=8192,
        temperature=0.6,
        max_tokens=4096,
        tags=["general", "chat", "instruction"],
        description="Mistral 7B Instruct v0.3 Q4 — reliable, well-rounded general model",
        best_for="General assistant tasks, writing, analysis",
        speed_toks="4–7 tok/s",
    ),

    # ── MULTIMODAL (vision + text) ─────────────────────────────

    "llava-mistral": ModelVariant(
        name="llava-mistral",
        gguf_name="llava-v1.6-mistral-7b.Q4_K_M.gguf",
        repo="cjpais/llava-1.6-mistral-7b-gguf",
        size_gb=4.5,
        ram_gb=6.5,
        ctx=4096,
        temperature=0.4,
        max_tokens=2048,
        tags=["multimodal", "vision", "coding", "image"],
        description="LLaVA 1.6 Mistral 7B Q4 — best multimodal for your device, image+text",
        best_for="Reading screenshots, understanding diagrams, UI feedback, image analysis",
        speed_toks="3–5 tok/s",
    ),

    "moondream": ModelVariant(
        name="moondream",
        gguf_name="moondream2-text-model-f16.gguf",
        repo="vikhyatk/moondream2",
        size_gb=1.7,
        ram_gb=2.5,
        ctx=2048,
        temperature=0.3,
        max_tokens=1024,
        tags=["multimodal", "vision", "tiny", "fast"],
        description="Moondream2 — ultra-tiny vision model, very fast image understanding",
        best_for="Quick image descriptions, OCR-like tasks, fast vision queries",
        speed_toks="8–12 tok/s",
    ),

    # ── REASONING / MATH ───────────────────────────────────────

    "qwen25-math": ModelVariant(
        name="qwen25-math",
        gguf_name="Qwen2.5-Math-7B-Instruct-Q4_K_M.gguf",
        repo="bartowski/Qwen2.5-Math-7B-Instruct-GGUF",
        size_gb=4.7,
        ram_gb=6.5,
        ctx=4096,
        temperature=0.0,
        max_tokens=2048,
        tags=["math", "reasoning", "science"],
        description="Qwen2.5-Math 7B — specialized for math, equations, scientific reasoning",
        best_for="Algorithms, complexity analysis, math problems, data science",
        speed_toks="4–6 tok/s",
    ),

    "nemotron-mini": ModelVariant(
        name="nemotron-mini",
        gguf_name="Nemotron-Mini-4B-Instruct-Q4_K_M.gguf",
        repo="bartowski/Nemotron-Mini-4B-Instruct-GGUF",
        size_gb=2.6,
        ram_gb=4.0,
        ctx=4096,
        temperature=0.3,
        max_tokens=2048,
        tags=["reasoning", "fast", "general"],
        description="NVIDIA Nemotron Mini 4B — strong reasoning for its tiny size",
        best_for="Step-by-step reasoning, structured outputs, agentic planning",
        speed_toks="8–11 tok/s",
    ),
}


def get(name: str) -> Optional[ModelVariant]:
    return REGISTRY.get(name)


def recommended() -> ModelVariant:
    for m in REGISTRY.values():
        if m.recommended:
            return m
    return list(REGISTRY.values())[0]


def by_tag(tag: str) -> list[ModelVariant]:
    return [m for m in REGISTRY.values() if tag in m.tags]


def fits_device(ram_gb: float = 14.0) -> list[ModelVariant]:
    return [m for m in REGISTRY.values() if m.fits(ram_gb)]


def all_models() -> list[ModelVariant]:
    return list(REGISTRY.values())


def show_table():
    """Print a formatted table of all models."""
    from devnet.core.cli import C
    rows = []
    for m in REGISTRY.values():
        rec = " ★" if m.recommended else ""
        tag_str = ", ".join(m.tags[:3])
        rows.append((m.name + rec, f"{m.size_gb}GB", m.speed_toks, tag_str, m.best_for[:45]))

    col_w = [20, 8, 14, 22, 46]
    header = ["MODEL", "SIZE", "SPEED (CPU)", "TAGS", "BEST FOR"]

    sep = "  " + "─" * (sum(col_w) + len(col_w) * 2)
    print(f"\n{C.BOLD}{C.WHITE}  Available Models{C.RESET}  {C.DGRAY}(your device: i5-8350U · 16GB · CPU-only){C.RESET}")
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
    print(f"  {C.DGRAY}★ = recommended  ·  use: devnet model use <name>{C.RESET}\n")
