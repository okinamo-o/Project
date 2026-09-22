@echo off
title NEXUS Multimodal Digital Twin Launcher
echo ===================================================
echo   NEXUS AI Digital Twin - Automated System Launcher
echo ===================================================

cd /d "%~dp0"

:: 1. Verify / Activate Virtual Environment
if exist "backend\venv\Scripts\activate.bat" (
    echo [OK] Using Python environment: backend\venv
    set "PYTHON_EXE=backend\venv\Scripts\python.exe"
) else if exist "venv\Scripts\activate.bat" (
    echo [OK] Using Python environment: venv
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    echo [!] Virtual environment not found. Using system python.
    set "PYTHON_EXE=python"
)

:: 2. Verify Models
echo [*] Verifying Deep Learning Vision models...
"%PYTHON_EXE%" ai/vision/download_models.py

:: 3. Run Quick Hardware Diagnostic
echo [*] Checking Laptop Camera and Microphone...
"%PYTHON_EXE%" verify_hardware.py

:: 4. Start Backend Server in Background Window
echo [*] Launching NEXUS Backend & AI Services (Port 8000)...
start "NEXUS Backend API & AI Subsystems" "%PYTHON_EXE%" -m backend.app.main

:: Wait 3 seconds for backend to initialize database schema
timeout /t 3 /nobreak >nul

:: 5. Start Frontend Dev Server
echo [*] Launching NEXUS 3D Twin Frontend (Port 3000)...
cd frontend
start "NEXUS Next.js Frontend" cmd /k "npm run dev"
cd ..

echo ===================================================
echo   NEXUS is now running!
echo   Dashboard : http://localhost:3000
echo   API Docs  : http://127.0.0.1:8000/docs
echo ===================================================

:: Open default browser
timeout /t 2 /nobreak >nul
start http://localhost:3000
