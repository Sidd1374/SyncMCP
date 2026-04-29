@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8

echo ============================================
echo   SyncMCP Setup — Agent Memory System
echo ============================================
echo.

:: ──────────────────────────────────────────────
::  Step 1: Check Python
:: ──────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH.
    echo Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

echo [OK] Python found
python --version
echo.

:: ──────────────────────────────────────────────
::  Step 2: Create global store at C:\.agent-memory
:: ──────────────────────────────────────────────
echo Setting up global store at C:\.agent-memory\ ...
echo.

if not exist "C:\.agent-memory" mkdir "C:\.agent-memory"
if not exist "C:\.agent-memory\agent_settings" mkdir "C:\.agent-memory\agent_settings"
if not exist "C:\.agent-memory\error_index" mkdir "C:\.agent-memory\error_index"

:: Create empty errors.jsonl if it doesn't exist
if not exist "C:\.agent-memory\error_index\errors.jsonl" (
    type nul > "C:\.agent-memory\error_index\errors.jsonl"
)

echo [OK] Directory structure created
echo.

:: ──────────────────────────────────────────────
::  Step 3: Install SyncMCP package & Dependencies
:: ──────────────────────────────────────────────
echo Checking and installing dependencies (LiteLLM, Gemini, etc.)...
echo.

:: Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

pip install -e . 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] pip install failed. Trying with --user flag...
    pip install -e . --user 2>&1
)

echo.
echo [OK] SyncMCP and all dependencies installed
echo.

:: ──────────────────────────────────────────────
::  Step 4: Initialize global store (templates + DB)
:: ──────────────────────────────────────────────
echo Initializing global store with templates...
echo.
python -c "from syncmcp.global_store import initialize; print(initialize())"
echo.

:: ──────────────────────────────────────────────
::  Step 5: Verify ctx command
:: ──────────────────────────────────────────────
echo Verifying ctx command...
ctx --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] 'ctx' command not found in PATH.
    echo You may need to add Python Scripts to your PATH.
    echo.
    echo Or run via: python -m syncmcp.cli
) else (
    echo [OK] ctx command is available
)
echo.

:: ──────────────────────────────────────────────
::  Step 6: Print agent config instructions
:: ──────────────────────────────────────────────
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo Global store:  C:\.agent-memory\
echo CLI command:   ctx
echo.
echo ── Next Steps ──
echo.
echo 1. Set your model in .env or system variables:
echo    notepad C:\.agent-memory\preferences.md
echo.
echo 2. Initialize project context (run inside any project):
echo    ctx init
echo.
echo 3. Run a deep scan (AI analysis):
echo    ctx scan --deep
echo.
echo 4. Connect your agents:
echo    See README.md or SETUP.md for detailed connection guides.
echo.
echo ============================================
echo.
pause
