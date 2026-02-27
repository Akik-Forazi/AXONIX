"""
build.py — Build devnet.exe with PyInstaller (Ollama edition)
Run: python build.py

Output: dist/devnet.exe  (single portable executable)
No llama.cpp, no DLLs, no native deps — just Python + Ollama client.
"""

import subprocess
import sys
import os

ROOT  = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(ROOT, "devnet_main.py")
STATIC = os.path.join(ROOT, "devnet", "web", "static")

# ── Write clean entry-point ────────────────────────────────
with open(ENTRY, "w") as f:
    f.write('from devnet.core.runner import main\nif __name__ == "__main__":\n    main()\n')

# ── Build command ──────────────────────────────────────────
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--console",
    "--name", "devnet",
    "--clean",
    "--noconfirm",
    # Web static assets
    "--add-data", f"{STATIC}{os.pathsep}devnet/web/static",
    # Pull in everything devnet needs
    "--collect-all", "devnet",
    "--collect-all", "ollama",
    # Exclude heavy libs we don't use
    "--exclude-module", "tkinter",
    "--exclude-module", "matplotlib",
    "--exclude-module", "PIL",
    "--exclude-module", "cv2",
    "--exclude-module", "torch",
    "--exclude-module", "tensorflow",
    "--exclude-module", "llama_cpp",
    "--exclude-module", "numpy",
    ENTRY,
]

print("=" * 60)
print("  DevNet — Building devnet.exe")
print("=" * 60)
print()

result = subprocess.run(cmd, cwd=ROOT)

# Cleanup temp entry file
try:
    os.remove(ENTRY)
except Exception:
    pass

if result.returncode == 0:
    exe  = os.path.join(ROOT, "dist", "devnet.exe")
    size = os.path.getsize(exe) // (1024 * 1024)
    print()
    print("=" * 60)
    print(f"  Build successful!")
    print(f"  Executable : dist\\devnet.exe")
    print(f"  Size       : {size} MB")
    print()
    print("  Run install.bat to add devnet to your PATH.")
    print("=" * 60)
else:
    print()
    print("=" * 60)
    print("  Build FAILED. See errors above.")
    print("  Make sure PyInstaller is installed: pip install pyinstaller")
    print("=" * 60)
    sys.exit(1)
