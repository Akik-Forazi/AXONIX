@echo off
:: DevNet Build Script — builds devnet.exe (Ollama backend)
:: Run from: C:\Users\akikf\programing\nn\
:: Usage: build.bat
setlocal enabledelayedexpansion

set PY=C:\Users\akikf\AppData\Local\Programs\Python\Python313\python.exe
set PIP=%PY% -m pip
set PROJECT=C:\Users\akikf\programing\nn

echo.
echo  ========================================
echo   DevNet Build  ^(Ollama edition^)
echo  ========================================
echo.

:: ── Step 1: Check Python ──────────────────────────────────
echo  [1/4] Checking Python...
%PY% --version
if errorlevel 1 (
    echo  ERROR: Python not found at %PY%
    pause
    exit /b 1
)

:: ── Step 2: Install build dependencies ───────────────────
echo.
echo  [2/4] Installing build dependencies...
%PIP% install pyinstaller --quiet
if errorlevel 1 (
    echo  ERROR: Failed to install PyInstaller.
    pause
    exit /b 1
)

:: Install ollama Python client (only runtime dep)
%PIP% install ollama --quiet

:: ── Step 3: Install devnet package in editable mode ──────
echo.
echo  [3/4] Installing DevNet package...
cd /d %PROJECT%
%PIP% install -e . --quiet
if errorlevel 1 (
    echo  ERROR: Failed to install devnet package.
    pause
    exit /b 1
)

:: ── Step 4: Build .exe ───────────────────────────────────
echo.
echo  [4/4] Building devnet.exe...
cd /d %PROJECT%
%PY% build.py

if errorlevel 1 (
    echo.
    echo  ERROR: Build failed. See errors above.
    pause
    exit /b 1
)

:: ── Done ─────────────────────────────────────────────────
echo.
echo  ========================================
echo   BUILD COMPLETE
echo  ========================================
echo.
echo  Executable: %PROJECT%\dist\devnet.exe
echo.
echo  Next: run install.bat to add devnet to your PATH.
echo.
pause
