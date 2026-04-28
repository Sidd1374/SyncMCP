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
::  Step 2: Create global store at C:\AgentMemory
:: ──────────────────────────────────────────────
echo Setting up global store at C:\AgentMemory\ ...
echo.

if not exist "C:\AgentMemory" mkdir "C:\AgentMemory"
if not exist "C:\AgentMemory\agent_settings" mkdir "C:\AgentMemory\agent_settings"
if not exist "C:\AgentMemory\error_index" mkdir "C:\AgentMemory\error_index"

:: Create empty errors.jsonl if it doesn't exist
if not exist "C:\AgentMemory\error_index\errors.jsonl" (
    type nul > "C:\AgentMemory\error_index\errors.jsonl"
)

echo [OK] Directory structure created
echo.

:: ──────────────────────────────────────────────
::  Step 3: Install SyncMCP package
:: ──────────────────────────────────────────────
echo Installing SyncMCP package...
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
echo [OK] SyncMCP installed
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
    echo You may need to add Python Scripts to your PATH:
    echo   set PATH=%%PATH%%;%%USERPROFILE%%\AppData\Local\Programs\Python\Python311\Scripts
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
echo Global store:  C:\AgentMemory\
echo CLI command:   ctx
echo.
echo ── Next Steps ──
echo.
echo 1. Edit your preferences:
echo    notepad C:\AgentMemory\preferences.md
echo.
echo 2. Initialize project context (run inside any project):
echo    ctx init
echo.
echo 3. Connect your agents:
echo.
echo    CLAUDE CODE:
echo      claude mcp add syncmcp -- python -m syncmcp.server
echo.
echo    CURSOR (.cursor/mcp.json):
echo      {
echo        "mcpServers": {
echo          "syncmcp": {
echo            "command": "python",
echo            "args": ["-m", "syncmcp.server"]
echo          }
echo        }
echo      }
echo.
echo    CLAUDE DESKTOP (%APPDATA%\Claude\claude_desktop_config.json):
echo      Same format as Cursor config above.
echo.
echo    WEB AGENTS (ChatGPT, Kimi, etc.):
echo      ctx context --query "what I'm working on" --copy
echo      Then paste from clipboard.
echo.
echo ============================================
echo.
pause
