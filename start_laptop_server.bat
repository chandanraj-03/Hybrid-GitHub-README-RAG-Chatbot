@echo off
title Laptop Local LLM Service (Port 8000)
color 0E
cls
echo =========================================================
echo    STARTING LOCAL LAPTOP LLM SERVICE (TRANSFORMERS)
echo =========================================================
echo Port: 8000
echo Model: Qwen/Qwen2.5-0.5B-Instruct
echo.
python -m uvicorn laptop.app.main:app --host 0.0.0.0 --port 8000
pause
