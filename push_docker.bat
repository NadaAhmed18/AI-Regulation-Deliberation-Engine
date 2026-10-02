@echo off
setlocal enabledelayedexpansion
title Push to Docker Hub

echo ================================================================
echo           BUILD AND PUSH IMAGES TO DOCKER HUB
echo ================================================================
echo.

set /p DOCKER_USER="Enter your Docker Hub username: "
if "%DOCKER_USER%"=="" (
    echo Username cannot be empty!
    pause
    exit /b 1
)

echo.
echo [*] Logging into Docker Hub...
docker login
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker login failed.
    pause
    exit /b 1
)

echo.
echo [*] Building and pushing Backend image (linux/amd64)...
docker build --platform linux/amd64 -t %DOCKER_USER%/ai-regulation-backend:latest ./backend
docker push %DOCKER_USER%/ai-regulation-backend:latest

echo.
echo [*] Building and pushing Frontend image (linux/amd64)...
docker build --platform linux/amd64 -t %DOCKER_USER%/ai-regulation-frontend:latest ./frontend
docker push %DOCKER_USER%/ai-regulation-frontend:latest

echo.
echo ================================================================
echo [SUCCESS] Both images successfully pushed to Docker Hub!
echo  - %DOCKER_USER%/ai-regulation-backend:latest
echo  - %DOCKER_USER%/ai-regulation-frontend:latest
echo ================================================================
pause