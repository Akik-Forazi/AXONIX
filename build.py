"""
build.py — Build axonix.exe with PyInstaller
Run: python build.py

Output: dist/axonix.exe  (single portable executable)
"""

import subprocess
import sys
import os

ROOT   = os.path.dirname(os.path.abspath(__file__))
ENTRY  = os.path.join(ROOT, "axonix_main.py")
STATIC = os.path.join(ROOT, "axonix", "web", "static")

# ── Write clean entry-point ────────────────────────────────
with open(ENTRY, "w") as f:
    f.write("from axonix.core.runner import main\nif __name__ == '__main__':\n    main()\n")

# ── Build command ──────────────────────────────────────────
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--console",
    "--name", "axonix",
    "--clean",
    "--noconfirm",
    # Web static assets
    "--add-data", f"{STATIC}{os.pathsep}axonix/web/static",
    # Pull in axonix modules explicitly
    "--hidden-import", "axonix.core.agent",
    "--hidden-import", "axonix.core.runner",
    "--hidden-import", "axonix.core.backend",
    "--hidden-import", "axonix.core.cli",
    "--hidden-import", "axonix.core.config",
    "--hidden-import", "axonix.core.history",
    "--hidden-import", "axonix.core.loop",
    "--hidden-import", "axonix.core.memory",
    "--hidden-import", "axonix.core.models",
    "--hidden-import", "axonix.core.first_run",
    "--hidden-import", "axonix.tools.file_tools",
    "--hidden-import", "axonix.tools.shell_tools",
    "--hidden-import", "axonix.tools.web_tools",
    "--hidden-import", "axonix.tools.code_tools",
    "--hidden-import", "axonix.agents.specialized",
    "--hidden-import", "axonix.web.server",
    "--collect-all", "ollama",
    "--collect-all", "llama_cpp",
    # Exclude heavy / conflicting libs
    "--exclude-module", "tkinter",
    "--exclude-module", "matplotlib",
    "--exclude-module", "PIL",
    "--exclude-module", "cv2",
    "--exclude-module", "torch",
    "--exclude-module", "tensorflow",
    "--exclude-module", "numpy",
    "--exclude-module", "PyQt6",
    "--exclude-module", "PySide6",
    "--exclude-module", "PyQt5",
    "--exclude-module", "PySide2",
    ENTRY,
]

print("=" * 60)
print("  Axonix — Building axonix.exe")
print("=" * 60)
print()

result = subprocess.run(cmd, cwd=ROOT)

# Cleanup temp entry file (optional, but good for cleanliness)
# try:
#     os.remove(ENTRY)
# except Exception:
#     pass

if result.returncode == 0:
    exe  = os.path.join(ROOT, "dist", "axonix.exe")
    size = os.path.getsize(exe) // (1024 * 1024)
    print()
    print("=" * 60)
    print(f"  Build successful!")
    print(f"  Executable : dist\\axonix.exe")
    print(f"  Size       : {size} MB")
    print()
    print("  Run install.bat to add axonix to your PATH.")
    print("=" * 60)
else:
    print()
    print("=" * 60)
    print("  Build FAILED. See errors above.")
    print("  Make sure PyInstaller is installed: pip install pyinstaller")
    print("=" * 60)
    sys.exit(1)
