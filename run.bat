@echo off
setlocal enabledelayedexpansion
title AI Regulation Engine Launcher
color 0B

echo ================================================================
echo           AI REGULATION ENGINE - DEPLOYMENT LAUNCHER
echo ================================================================
echo.

:: 1. Verify Docker Engine is running
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo [ERROR] Docker Desktop is not running!
    echo Please start Docker Desktop on your machine and run this file again.
    echo.
    pause
    exit /b 1
)

:: 2. Detect Host Local IP address for local network sharing
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.InterfaceAlias -notlike '*vEthernet*' -and $_.IPv4Address -notlike '169.*' }).IPAddress[0]"`) do (
    set LOCAL_IP=%%i
)

echo Detected Local IP Address: %LOCAL_IP%
echo.
echo Choose your deployment mode:
echo   [1] Local Only        - Run on this computer (http://localhost:5000)
echo   [2] Shared Online     - Run locally AND generate a public HTTPS URL (Free Cloudflare Tunnel)
echo   [3] View Service Logs - Tail active container logs
echo   [4] Stop Services     - Clean shutdown of all running containers
echo.
set /p MODE="Select an option (1, 2, 3, or 4): "

cd /d "%~dp0docker"

if "%MODE%"=="1" (
    echo.
    echo [*] Starting containers in Local Mode...
    docker compose up -d --build
    goto StartedLocal
)

if "%MODE%"=="2" (
    echo.
    echo [*] Starting containers with Cloudflare Public Tunnel...
    docker compose --profile tunnel up -d --build
    goto StartedTunnel
)

if "%MODE%"=="3" (
    echo.
    echo [*] Fetching Docker container logs (Press Ctrl+C to exit)...
    docker compose logs -f --tail=100
    exit /b 0
)

if "%MODE%"=="4" (
    echo.
    echo [*] Stopping all running containers...
    docker compose --profile tunnel down
    color 0A
    echo [OK] All services have been stopped.
    pause
    exit /b 0
)

color 0C
echo Invalid selection. Exiting.
pause
exit /b 1

:StartedLocal
color 0A
cls
echo ================================================================
echo           APPLICATION SUCCESSFULLY LAUNCHED (LOCAL)
echo ================================================================
echo.
echo - Access from this PC:            http://localhost:5000
echo - Access from your Local Wi-Fi:   http://%LOCAL_IP%:5000
echo - Langfuse Observability:        http://localhost:3000
echo - FastAPI Interactive Docs:       http://localhost:8000/docs
echo.
echo Keep Docker Desktop running. Press any key to open the app in your browser...
pause >nul
start http://localhost:5000
exit /b 0

:StartedTunnel
color 0A
cls
echo ================================================================
echo         APPLICATION SUCCESSFULLY LAUNCHED (PUBLIC SHARING)
echo ================================================================
echo.
echo [*] Waiting for Cloudflare Tunnel to generate your public URL...

set PUBLIC_URL=
for /L %%i in (1,1,20) do (
    if "!PUBLIC_URL!"=="" (
        timeout /t 1 /nobreak >nul
        for /f "tokens=*" %%a in ('powershell -NoProfile -Command "docker logs cloudflare-tunnel 2>&1 | Select-String -Pattern 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | ForEach-Object { $_.Matches.Value } | Select-Object -Last 1"') do (
            set PUBLIC_URL=%%a
        )
    )
)

echo.
echo - Access from this PC:           http://localhost:5000
echo - Access from your Local Wi-Fi:  http://%LOCAL_IP%:5000
if not "!PUBLIC_URL!"=="" (
    echo.
    echo ================================================================
    echo  SHARE THIS PUBLIC HTTPS URL WITH ANYONE ON ANY NETWORK:
    echo  !PUBLIC_URL!
    echo ================================================================
) else (
    echo [!] Tunnel is still connecting. Run: docker logs cloudflare-tunnel
)
echo.
echo Press any key to open the local interface...
pause >nul
start http://localhost:5000
exit /b 0