@echo off
title Backend API Server (Port 18080)
color 0B
cls
echo =========================================================
echo    STARTING HYBRID RAG BACKEND API SERVER
echo =========================================================
echo Port: 18080
echo Docs: http://localhost:18080/docs
echo.
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 18080
pause
