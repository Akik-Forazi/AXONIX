@echo off
:: install.bat — Copies devnet.exe to %USERPROFILE%\.devnet\bin\ and adds to user PATH
:: Uses PowerShell to safely read/write PATH — will never wipe existing entries.
setlocal

set "INSTALL_DIR=%USERPROFILE%\.devnet\bin"
set "EXE_SRC=%~dp0dist\devnet.exe"

echo.
echo  ============================================================
echo   DevNet Installer
echo  ============================================================
echo.

:: ── Check exe exists ──────────────────────────────────────
if not exist "%EXE_SRC%" (
    echo   ERROR: dist\devnet.exe not found.
    echo   Run build.bat first!
    echo.
    pause
    exit /b 1
)

:: ── Create install dir ────────────────────────────────────
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    echo   Created: %INSTALL_DIR%
)

:: ── Copy exe ──────────────────────────────────────────────
copy /Y "%EXE_SRC%" "%INSTALL_DIR%\devnet.exe" >nul
echo   Installed: %INSTALL_DIR%\devnet.exe

:: ── Add to user PATH safely via PowerShell ────────────────
echo.
echo   Updating PATH safely...

powershell -NoProfile -NonInteractive -Command ^
  "$dir = '%INSTALL_DIR%';" ^
  "$key = 'HKCU:\Environment';" ^
  "$current = (Get-ItemProperty -Path $key -Name PATH -ErrorAction SilentlyContinue).PATH;" ^
  "if (-not $current) { $current = '' };" ^
  "$entries = $current -split ';' | Where-Object { $_ -ne '' };" ^
  "if ($entries -contains $dir) {" ^
  "  Write-Host '  Already in PATH - no changes made.'" ^
  "} else {" ^
  "  $entries += $dir;" ^
  "  $newPath = $entries -join ';';" ^
  "  Set-ItemProperty -Path $key -Name PATH -Value $newPath;" ^
  "  Write-Host '  Added to PATH: %INSTALL_DIR%';" ^
  "  Write-Host '  (Restart your terminal for PATH to take effect)';" ^
  "}"

if errorlevel 1 (
    echo.
    echo   WARNING: Could not update PATH automatically.
    echo   Add this folder to your PATH manually:
    echo   %INSTALL_DIR%
)

:: ── Done ─────────────────────────────────────────────────
echo.
echo  ============================================================
echo   devnet.exe installed successfully!
echo  ============================================================
echo.
echo   Before running DevNet, make sure Ollama is set up:
echo.
echo     1. Install Ollama:   https://ollama.com/download
echo     2. Start Ollama:     ollama serve
echo     3. Import models:    devnet setup
echo     4. Run DevNet:       devnet run --lc
echo.
echo   Open a NEW terminal window, then run: devnet
echo.
pause
