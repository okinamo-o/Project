# NEXUS Firebase Hosting Deployment Script
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  NEXUS 3D Digital Twin - Firebase Deployment" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 1. Build Next.js Static Export
Write-Host "`n[1/3] Building Next.js static production export..." -ForegroundColor Yellow
Set-Location "$ScriptDir\frontend"
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Next.js build failed. Aborting deployment." -ForegroundColor Red
    Exit 1
}
Set-Location $ScriptDir

# 2. Check Firebase Authentication
Write-Host "`n[2/3] Checking Firebase authentication..." -ForegroundColor Yellow
$loginCheck = npx --yes firebase-tools login:list 2>&1
if ($loginCheck -match "No authorized accounts") {
    Write-Host "[!] You need to log in to Firebase." -ForegroundColor Yellow
    Write-Host "[*] Launching browser login..." -ForegroundColor Cyan
    npx --yes firebase-tools login
}

# 3. Deploy to Firebase Hosting
Write-Host "`n[3/3] Deploying to Firebase Hosting (nexus-7ba7a)..." -ForegroundColor Yellow
npx --yes firebase-tools deploy --only hosting

Write-Host "`n==================================================" -ForegroundColor Green
Write-Host "  Deployment completed!" -ForegroundColor Green
Write-Host "  Live URL: https://nexus-7ba7a.web.app" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Green

