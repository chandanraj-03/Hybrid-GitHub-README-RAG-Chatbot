@echo off
chcp 65001 >nul
title Hybrid GitHub RAG - All-In-One Laptop Bridge
color 0B
cls

:MENU
cls
echo ========================================================================
echo        HYBRID GITHUB RAG CHATBOT - ALL-IN-ONE MASTER CONTROLLER
echo ========================================================================
echo.
echo   [1] ONE-CLICK CONNECT: Start Laptop Server + Tunnel + Sync to Render
echo       (Starts local LLM model and registers public tunnel with Render)
echo.
echo   [2] Start Local Laptop LLM Service Only (Port 16036)
echo   [3] Start Cloudflare Tunnel Only (with Auto-Sync to Render)
echo.
echo   [4] Configure LLM API Keys and Live Sync to Render
echo       (Update Gemini, Grok, OpenRouter keys, Repo URL with 0-downtime)
echo.
echo   [5] Test Health Probe (Laptop, Tunnel, and Remote Render Status)
echo   [6] Launch Interactive Terminal Chatbot
echo   [7] Start Full Local Stack (Laptop 16036 + Backend 18080 + CLI)
echo   [8] Free / Reset Port 16036
echo   [9] Exit
echo.
echo ========================================================================
set /p choice="Select an option [1-9]: "

if "%choice%"=="1" goto ONE_CLICK_CONNECT
if "%choice%"=="2" goto START_LAPTOP_ONLY
if "%choice%"=="3" goto START_TUNNEL_ONLY
if "%choice%"=="4" goto CONFIGURE_KEYS
if "%choice%"=="5" goto TEST_HEALTH
if "%choice%"=="6" goto LAUNCH_CLI
if "%choice%"=="7" goto START_LOCAL_FULL
if "%choice%"=="8" goto KILL_PORT
if "%choice%"=="9" goto EXIT

echo Invalid option, please try again.
timeout /t 2 /nobreak >nul
goto MENU

:ONE_CLICK_CONNECT
cls
echo ========================================================================
echo     STEP 1/2: Preparing and Starting Local Laptop LLM Service...
echo ========================================================================
echo [*] Checking and freeing port 16036 if occupied...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":16036 "') do (
    taskkill /f /pid %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo [*] Starting Local Laptop LLM Service on Port 16036 in new window...
start "Laptop Local LLM (Port 16036)" cmd /k "title Laptop Local LLM (Port 16036) && color 0E && python -m uvicorn laptop.app.main:app --host 0.0.0.0 --port 16036"
echo [+] Laptop server launched in separate window.
echo [*] Waiting 3 seconds for local model to load...
timeout /t 3 /nobreak >nul
echo.
echo ========================================================================
echo     STEP 2/2: Launching Cloudflare Tunnel and Auto-Syncing with Render...
echo ========================================================================
python tunnel_runner.py
pause
goto MENU

:START_LAPTOP_ONLY
cls
echo ========================================================================
echo     Starting Local Laptop LLM Service on Port 16036...
echo ========================================================================
echo [*] Checking and freeing port 16036 if occupied...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":16036 "') do (
    taskkill /f /pid %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul
start "Laptop Local LLM (Port 16036)" cmd /k "title Laptop Local LLM (Port 16036) && color 0E && python -m uvicorn laptop.app.main:app --host 0.0.0.0 --port 16036"
echo [+] Laptop server running in new window.
timeout /t 2 /nobreak >nul
goto MENU

:START_TUNNEL_ONLY
cls
echo ========================================================================
echo     Starting Cloudflare Quick Tunnel with Auto-Sync to Render...
echo ========================================================================
python tunnel_runner.py
pause
goto MENU

:CONFIGURE_KEYS
cls
python settings_manager.py
goto MENU

:TEST_HEALTH
cls
echo ========================================================================
echo     Running Service Health and Connectivity Probe...
echo ========================================================================
python -c "import settings_manager; settings_manager.test_services()"
echo.
pause
goto MENU

:LAUNCH_CLI
cls
echo ========================================================================
echo     Launching Interactive Terminal Chatbot...
echo ========================================================================
python cli_chatbot.py
pause
goto MENU

:START_LOCAL_FULL
cls
echo ========================================================================
echo     Starting Full Local Stack...
echo ========================================================================
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":16036 "') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":18080 "') do taskkill /f /pid %%a >nul 2>&1

echo [*] Starting Laptop LLM (Port 16036)...
start "Laptop LLM (Port 16036)" cmd /k "title Laptop LLM && color 0E && python -m uvicorn laptop.app.main:app --host 0.0.0.0 --port 16036"
timeout /t 3 /nobreak >nul

echo [*] Starting Backend API Server (Port 18080)...
start "Backend API Server (Port 18080)" cmd /k "title Backend API && color 0A && python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 18080"
timeout /t 3 /nobreak >nul

echo [*] Opening Terminal Chatbot...
python cli_chatbot.py
pause
goto MENU

:KILL_PORT
cls
echo ========================================================================
echo     Freeing Port 16036 and Port 18080...
echo ========================================================================
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":16036 "') do (
    echo [+] Terminating process on port 16036 (PID: %%a)
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":18080 "') do (
    echo [+] Terminating process on port 18080 (PID: %%a)
    taskkill /f /pid %%a >nul 2>&1
)
echo [✓] Ports cleared!
timeout /t 2 /nobreak >nul
goto MENU

:EXIT
echo Exiting...
exit
