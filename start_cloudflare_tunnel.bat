@echo off
title Cloudflare Quick Tunnel
color 0D
cls
echo =========================================================
echo    STARTING CLOUDFLARE QUICK TUNNEL (FOR RENDER BACKEND)
echo =========================================================
echo.
echo Tunneling localhost:8000 to public HTTPS URL...
echo.
cloudflared tunnel --url http://localhost:8000
pause
