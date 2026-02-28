# 🤖 AXONIX-ZERO
### The local Agentic super AI friend of yours.

AXONIX-ZERO is a powerful, fully autonomous AI coding agent designed specifically for Windows. It operates locally using your own LLMs, providing a secure and high-performance development environment.

## 🚀 Key Features
- **Agentic Autonomy:** Rebuilds, debugs, and tests code autonomously using a robust XML-based reasoning/action protocol.
- **Multi-Backend Support:** Works with **Ollama**, **llama-cpp-python**, **LM Studio**, **Groq**, **Anthropic**, and **OpenAI**.
- **Contextual Memory:** Persistent knowledge that is automatically injected into the agent's context.
- **Self-Healing Loop:** Built-in repetition detection and self-correction to prevent infinite loops and improve reliability.
- **Diagnostic Power:** Detailed logging, tracing, and a real-time `StreamParser` for deep transparency.
- **Modern UI:** Premium interactive CLI and a sleek Web Interface with real-time thought visualization.

## 🛠️ Installation
1. **Clone the Repo:**
   ```powershell
   git clone https://github.com/Akik-Forazi/AXONIX.git
   cd AXONIX
   ```
2. **Setup Environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Configure & Run:**
   ```powershell
   python axonix_main.py
   ```

## 🔍 Debugging
To enable diagnostic logging:
```powershell
$env:AXONIX_DEBUG="1"
python axonix_main.py
```

## ⚖️ Licensing
© 2026 AKIK FARAJI | **Fraziym Tech & AI**
Contact: akikfaraji@gmail.com
