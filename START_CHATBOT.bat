@echo off
title Hybrid GitHub README RAG - Master Launcher
color 0B
cls

:MENU
cls
echo ===================================================================
echo         HYBRID GITHUB README RAG - WINDOWS CONTROL PANEL
echo ===================================================================
echo.
echo   [1] Start Full Stack & Open Terminal Chatbot (Recommended)
echo   [2] Launch Interactive Terminal Chatbot
echo   [3] Start Local Laptop LLM Service (Port 6036)
echo   [4] Start Backend API Server (Port 8080)
echo   [5] Expose Laptop via Cloudflare Quick Tunnel (for Render)
echo   [6] Configure Settings & API Keys
echo   [7] Run Automated Pytest Suite
echo   [8] Exit
echo.
echo ===================================================================
set /p choice="Select an option [1-8]: "

if "%choice%"=="1" goto START_ALL
if "%choice%"=="2" goto LAUNCH_CLI
if "%choice%"=="3" goto START_LAPTOP
if "%choice%"=="4" goto START_BACKEND
if "%choice%"=="5" goto START_TUNNEL
if "%choice%"=="6" goto SETTINGS
if "%choice%"=="7" goto RUN_TESTS
if "%choice%"=="8" goto EXIT

echo Invalid option, please try again.
pause
goto MENU

:START_ALL
echo.
echo [*] Starting Local Laptop LLM Service on port 6036 in new window...
start "Laptop LLM Service (Port 6036)" cmd /k "title Laptop LLM Service && python -m uvicorn laptop.app.main:app --host 0.0.0.0 --port 6036"
timeout /t 3 /nobreak >nul

echo [*] Starting Backend API Server on port 8080 in new window...
start "Backend API Server (Port 8080)" cmd /k "title Backend API Server && python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8080"
timeout /t 4 /nobreak >nul

echo [*] Launching Interactive Terminal Chatbot...
python cli_chatbot.py
pause
goto MENU

:LAUNCH_CLI
echo.
echo [*] Launching Terminal Chatbot...
python cli_chatbot.py
pause
goto MENU

:START_LAPTOP
echo.
echo [*] Starting Local Laptop LLM Service on port 6036 in new window...
start "Laptop LLM Service (Port 6036)" cmd /k "title Laptop LLM Service && python -m uvicorn laptop.app.main:app --host 0.0.0.0 --port 6036"
goto MENU

:START_BACKEND
echo.
echo [*] Starting Backend API Server on port 8080 in new window...
start "Backend API Server (Port 8080)" cmd /k "title Backend API Server && python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8080"
goto MENU

:START_TUNNEL
echo.
echo [*] Starting Cloudflare Quick Tunnel for port 6036...
start "Cloudflare Quick Tunnel" cmd /k "title Cloudflare Tunnel && cloudflared tunnel --url http://localhost:6036"
goto MENU

:SETTINGS
python settings_manager.py
goto MENU

:RUN_TESTS
echo.
echo [*] Running automated tests...
python -m pytest backend/tests laptop/tests -v
pause
goto MENU

:EXIT
echo Exiting...
exit
