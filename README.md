# axonix — Fully Local Super Agentic AI

```
  ██████╗ ███████╗██╗   ██╗███╗   ██╗███████╗████████╗
  ██╔══██╗██╔════╝██║   ██║████╗  ██║██╔════╝╚══██╔══╝
  ██║  ██║█████╗  ██║   ██║██╔██╗ ██║█████╗     ██║
  ██║  ██║██╔══╝  ╚██╗ ██╔╝██║╚██╗██║██╔══╝     ██║
  ██████╔╝███████╗ ╚████╔╝ ██║ ╚████║███████╗   ██║
  ╚═════╝ ╚══════╝  ╚═══╝  ╚═╝  ╚═══╝╚══════╝   ╚═╝
```

**llama.cpp powered · Fully local · Zero cloud · Zero API keys**

---

## 🚀 Setup in 3 Steps

### Step 1 — Get llama.cpp

Download a prebuilt binary from [llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases) (pick `llama-...-win-x64.zip` on Windows).

Download a GGUF model (e.g. from HuggingFace):
- [Llama 3 8B GGUF](https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF)
- [Mistral 7B GGUF](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF)
- [DeepSeek Coder GGUF](https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF)

### Step 2 — Start llama.cpp server

```bash
# Windows
llama-server.exe -m your_model.gguf --port 8080 --ctx-size 4096 -ngl 99

# Linux / Mac
./llama-server -m your_model.gguf --port 8080 --ctx-size 4096 -ngl 99
```

The server exposes `http://localhost:8080` with OpenAI-compatible `/v1/chat/completions`.

### Step 3 — Install axonix

```bash
cd C:\Users\akikf\programing\nn
python -m pip install -e .
```

---

## 🎮 Run Commands

| Command | Description |
|---------|-------------|
| `axonix run --lc` | Interactive local CLI loop (agent mode) |
| `axonix run --lc --w` | Interactive CLI **+ web UI** at localhost:7860 |
| `axonix run --lc -w --port 8888` | Custom web port |
| `axonix run --cli` | One-shot stdin mode |
| `axonix run agent "your task"` | Run agent on a specific task |
| `axonix web` | Start web UI only |

---

## 🌐 Web UI (`--w` flag)

```bash
axonix run --lc --w
```

Opens a beautiful dark-themed chat interface at **http://localhost:7860** with:

- **Chat mode** — direct conversation with the LLM
- **Agent mode** — full agentic loop with tool use, collapsible tool call explorer
- **Memory sidebar** — see what the agent has remembered
- **Live server status** — shows if llama.cpp is connected
- **Streaming support** — token-by-token output
- **Zero dependencies** — pure Python stdlib HTTP server, no Flask needed

---

## 🛠️ Tools Available to the Agent

| Tool | Description |
|------|-------------|
| `file_read` | Read any file with line numbers |
| `file_write` | Create or overwrite files |
| `file_edit` | Find-and-replace edits |
| `file_delete` | Delete files or folders |
| `file_list` | List directory contents |
| `file_search` | Glob pattern file search |
| `file_append` | Append to a file |
| `shell_run` | Run any terminal command |
| `shell_python` | Execute Python code live |
| `web_get` | Fetch any URL |
| `web_search` | Search the web (DuckDuckGo, no API key) |
| `code_lint` | Lint Python with flake8 |
| `code_format` | Format Python with black |
| `code_tree` | Show project file tree |
| `memory_save` | Persist data between steps |
| `memory_get` | Recall persisted data |
| `memory_list` | List all memory keys |

---

## ⚙️ Configuration

```bash
axonix config show
axonix config set --url http://localhost:8080
axonix config set --model llama3-8b
axonix config set --steps 50 --temp 0.5 --tokens 4096
axonix config reset
```

Config is saved to `~/.axonix_config.json`.

### Per-run overrides

```bash
axonix run --lc --w --url http://localhost:8080 --steps 40 --temp 0.3
axonix run agent "fix main.py" --workspace ./myproject --tokens 4096
```

---

## 🐍 Python API

```python
from axonix import Agent

agent = Agent(
    base_url="http://localhost:8080",   # your llama.cpp server
    model="local",
    workspace="./myproject",
    max_steps=25,
    temperature=0.7,
)

# Full agentic run
result = agent.run("Create a FastAPI app with 3 endpoints and write it to main.py")

# Simple chat
response = agent.chat("What is a GGUF file?")

# Streaming chat
for token in agent.chat_stream("Explain llama.cpp in simple terms"):
    print(token, end="", flush=True)
```

---

## 📁 Project Structure

```
nn/
├── axonix/
│   ├── __init__.py
│   ├── core/
│   │   ├── agent.py          # Agent loop + tool calling
│   │   ├── runner.py         # CLI dispatcher (all run modes)
│   │   ├── llama_backend.py  # llama.cpp HTTP client
│   │   ├── memory.py         # Persistent memory store
│   │   └── config.py         # Config management
│   ├── tools/
│   │   ├── file_tools.py     # File operations
│   │   ├── shell_tools.py    # Shell + Python execution
│   │   ├── web_tools.py      # Fetch + DuckDuckGo search
│   │   └── code_tools.py     # Lint / format / tree
│   ├── agents/
│   │   └── specialized.py    # CoderAgent, ResearchAgent, FileAgent
│   └── web/
│       ├── server.py          # Pure-stdlib HTTP server + REST API
│       └── static/
│           └── index.html     # Full chat web UI
├── setup.py
├── requirements.txt
└── README.md
```

---

## 💡 Example Tasks

```bash
axonix run agent "Read all Python files and summarize what this project does"
axonix run agent "Create a complete Flask REST API with SQLite database"
axonix run agent "Search the web for best GGUF models under 8B parameters"
axonix run agent "Find all TODO comments in the codebase and create a todo.md"
axonix run agent "Write unit tests for every function in utils.py"
axonix run agent "Refactor this code to use dataclasses"
```

---

## CLI Shortcuts (in `--lc` mode)

| Input | Action |
|-------|--------|
| `agent` | Switch to agent mode |
| `chat` | Switch to direct chat mode |
| `reset` | Clear conversation history |
| `memory` | Show memory contents |
| `health` | Check llama.cpp server status |
| `!command` | Run shell command directly |
| `exit` / `quit` | Exit |

---

## Requirements

- Python **3.9+**
- **llama.cpp server** running locally
- **Zero pip dependencies** (stdlib only)
- Optional: `flake8`, `black` for code tools
