@echo off
setlocal enabledelayedexpansion
title AI Regulation Engine Launcher
color 0B

echo ================================================================
echo           AI REGULATION ENGINE - UNIFIED DEPLOYER
echo ================================================================
echo.

:: Detect Host Local IP
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.InterfaceAlias -notlike '*vEthernet*' -and $_.IPv4Address -notlike '169.*' }).IPAddress[0]"`) do (
    set LOCAL_IP=%%i
)

echo Detected Local IP: %LOCAL_IP%
echo.
echo ======================== LOCAL RUN =============================
echo   [1] Fast Mode: Local Only     - Run strictly on this PC [localhost:5000]
echo   [2] Fast Mode: Public Online  - Run locally + Open to Internet via Cloudflare Tunnel
echo   [3] Service Logs              - Tail live container logs
echo   [4] Stop Local Services       - Shut down all local containers
echo.
echo ======================== AWS CLOUD =============================
echo   [5] AWS: Deploy Stack         - Creates VPC, Storage, and App on AWS (Public IP)
echo   [6] AWS: Seed Neo4j Knowledge - Import local JSON data into Cloud Neo4j
echo   [7] AWS: Stop Storage Layer   - Pause Storage EC2 to save money
echo   [8] AWS: Start Storage Layer  - Resume Storage EC2
echo   [9] AWS: Clean Destroy        - 100%% Teardown (Zero residual AWS charges)
echo.
set /p MODE="Select an option (1-9): "

if "%MODE%"=="1" goto RunLocalOnly
if "%MODE%"=="2" goto RunLocalTunnel
if "%MODE%"=="3" goto RunLogs
if "%MODE%"=="4" goto RunStopLocal
if "%MODE%"=="5" goto RunAwsDeploy
if "%MODE%"=="6" goto RunAwsSeed
if "%MODE%"=="7" goto RunAwsStopStorage
if "%MODE%"=="8" goto RunAwsStartStorage
if "%MODE%"=="9" goto RunAwsDestroy

color 0C
echo Invalid choice. Exiting.
pause
exit /b 1

:RunLocalOnly
cd /d "%~dp0docker"
echo.
echo [*] Starting Core stack locally (Private)...
docker compose up -d --build
goto StartedLocal

:RunLocalTunnel
cd /d "%~dp0docker"
echo.
echo [*] Starting Core stack with Cloudflare Tunnel (Open to Internet)...
docker compose --profile tunnel up -d --build
goto StartedTunnel

:RunLogs
cd /d "%~dp0docker"
docker compose logs -f --tail=100
exit /b 0

:RunStopLocal
cd /d "%~dp0docker"
echo.
echo [*] Stopping all local containers...
docker compose --profile tunnel down
color 0A
echo [OK] All local services stopped.
pause
exit /b 0

:RunAwsDeploy
echo.
python infra\aws\deploy.py deploy
pause
exit /b 0

:RunAwsSeed
echo.
python infra\aws\deploy.py seed
pause
exit /b 0

:RunAwsStopStorage
echo.
python infra\aws\deploy.py stop-storage
pause
exit /b 0

:RunAwsStartStorage
echo.
python infra\aws\deploy.py start-storage
pause
exit /b 0

:RunAwsDestroy
echo.
python infra\aws\deploy.py destroy
pause
exit /b 0

:StartedLocal
color 0A
cls
echo ================================================================
echo           APPLICATION RUNNING LOCALLY [PRIVATE]
echo ================================================================
echo.
echo - Web Browser:                    http://localhost:5000
echo - Wi-Fi Network Devices:          http://%LOCAL_IP%:5000
echo - API Docs:                       http://localhost:8000/docs
echo.
pause
start http://localhost:5000
exit /b 0

:StartedTunnel
color 0A
cls
echo ================================================================
echo        APPLICATION RUNNING WITH PUBLIC INTERNET ACCESS
echo ================================================================
echo.
echo [*] Generating public Cloudflare URL (Anti-buffering enabled)...

set PUBLIC_URL=
for /L %%i in (1,1,25) do (
    if "!PUBLIC_URL!"=="" (
        timeout /t 1 /nobreak >nul
        for /f "tokens=*" %%a in ('powershell -NoProfile -Command "docker logs cloudflare-tunnel 2>&1 | Select-String -Pattern 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | ForEach-Object { $_.Matches.Value } | Select-Object -Last 1"') do (
            set PUBLIC_URL=%%a
        )
    )
)

echo.
echo - Local UI: http://localhost:5000
if not "!PUBLIC_URL!"=="" (
    echo ================================================================
    echo  SHARE THIS PUBLIC HTTPS LINK WITH ANYONE OVER THE INTERNET:
    echo  !PUBLIC_URL!
    echo ================================================================
) else (
    echo [!] Tunnel is still booting. Run: docker logs cloudflare-tunnel
)
echo.
pause
start http://localhost:5000
exit /b 0