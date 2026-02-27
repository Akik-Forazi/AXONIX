@echo off
:: Axonix Build Script — builds axonix.exe
:: Run from: C:\Users\akikf\programing\nn\
:: Usage: build.bat
setlocal enabledelayedexpansion

set PY=C:\Users\akikf\AppData\Local\Programs\Python\Python313\python.exe
set PIP=%PY% -m pip
set PROJECT=C:\Users\akikf\programing\nn

echo.
echo  ========================================
echo   Axonix Build
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

:: Install runtime deps
%PIP% install ollama llama-cpp-python --quiet

:: ── Step 3: Install axonix package in editable mode ──────
echo.
echo  [3/4] Installing Axonix package...
cd /d %PROJECT%
%PIP% install -e . --quiet
if errorlevel 1 (
    echo  ERROR: Failed to install axonix package.
    pause
    exit /b 1
)

:: ── Step 4: Build .exe ───────────────────────────────────
echo.
echo  [4/4] Building axonix.exe...
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
echo  Executable: %PROJECT%\dist\axonix.exe
echo.
echo  Next: run install.bat to add axonix to your PATH.
echo.
pause
