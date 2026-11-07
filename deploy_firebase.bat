@echo off
title NEXUS Firebase Hosting Deployment
echo ==================================================
echo   NEXUS 3D Digital Twin - Firebase Deployment
echo ==================================================

cd /d "%~dp0"

echo.
echo [1/3] Building Next.js static production export...
cd frontend
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Next.js build failed. Aborting.
    pause
    exit /b %ERRORLEVEL%
)
cd ..

echo.
echo [2/3] Checking Firebase authentication...
call npx --yes firebase-tools login:list 2>nul | findstr /C:"No authorized accounts" >nul
if %ERRORLEVEL% EQU 0 (
    echo [*] Opening browser for Firebase login...
    call npx --yes firebase-tools login
)

echo.
echo [3/3] Deploying to Firebase Hosting...
call npx --yes firebase-tools deploy --only hosting

echo.
echo ==================================================
echo   Deployment completed!
echo   Live URL: https://nexus-7ba7a.web.app
echo ==================================================
pause

