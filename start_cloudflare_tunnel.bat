@echo off
title Cloudflare Quick Tunnel (Port 6036)
color 0D
cls
echo =========================================================
echo    STARTING CLOUDFLARE QUICK TUNNEL (FOR RENDER BACKEND)
echo =========================================================
echo.
echo Tunneling localhost:6036 to public HTTPS URL...
echo.
cloudflared tunnel --url http://localhost:6036
pause
