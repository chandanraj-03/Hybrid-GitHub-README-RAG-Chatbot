@echo off
title Backend API Server (Port 8080)
color 0B
cls
echo =========================================================
echo    STARTING HYBRID RAG BACKEND API SERVER
echo =========================================================
echo Port: 8080
echo Docs: http://localhost:8080/docs
echo.
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8080
pause
