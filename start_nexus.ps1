# NEXUS Multimodal Digital Twin Launcher (PowerShell)
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  NEXUS AI Digital Twin - Automated System Launcher" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 1. Detect Python virtual environment
$PythonExe = "python"
if (Test-Path "backend\venv\Scripts\python.exe") {
    $PythonExe = "$ScriptDir\backend\venv\Scripts\python.exe"
    Write-Host "[OK] Using Python environment: backend\venv" -ForegroundColor Green
} elseif (Test-Path "venv\Scripts\python.exe") {
    $PythonExe = "$ScriptDir\venv\Scripts\python.exe"
    Write-Host "[OK] Using Python environment: venv" -ForegroundColor Green
} else {
    Write-Host "[!] No local virtualenv found. Using system python." -ForegroundColor Yellow
}

# 2. Verify Models
Write-Host "[*] Verifying Deep Learning Vision models..." -ForegroundColor Yellow
& $PythonExe ai/vision/download_models.py

# 3. Hardware check
Write-Host "[*] Checking Laptop Camera and Microphone..." -ForegroundColor Yellow
& $PythonExe verify_hardware.py

# 4. Stop any previous lingering instances and start Backend
Write-Host "[*] Cleaning up any previous NEXUS background instances..." -ForegroundColor Yellow
Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "backend.app.main|ai/audio|ai/vision|iot/emulator" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "[*] Launching NEXUS Backend & AI Services (Port 8000)..." -ForegroundColor Green
Start-Process -FilePath $PythonExe -ArgumentList "-m backend.app.main" -WorkingDirectory $ScriptDir

Start-Sleep -Seconds 3

# 5. Start Frontend
Write-Host "[*] Launching NEXUS 3D Twin Frontend (Port 3000)..." -ForegroundColor Green
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$ScriptDir\frontend'; npm run dev"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  NEXUS is now active!" -ForegroundColor Cyan
Write-Host "  Dashboard : http://localhost:3000" -ForegroundColor White
Write-Host "  API Docs  : http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "===================================================" -ForegroundColor Cyan

Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"
