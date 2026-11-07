# Compiles both NEXUS ESP32 sketches so the Wokwi VS Code extension can run them.
#   Lab 02       : iot/firmware/sketch.ino            -> iot/firmware/build/
#   Classroom 01 : iot/wokwi/classroom_01/sketch.ino  -> iot/wokwi/classroom_01/build/
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Cli = Join-Path $Root 'tools\arduino-cli\arduino-cli.exe'
if (-not (Test-Path $Cli)) { throw "arduino-cli not found at $Cli" }

$targets = @(
    @{ Name = 'Lab 02';       Src = 'iot\firmware\sketch.ino';           Out = 'iot\firmware\build' },
    @{ Name = 'Classroom 01'; Src = 'iot\wokwi\classroom_01\sketch.ino'; Out = 'iot\wokwi\classroom_01\build' }
)

foreach ($t in $targets) {
    Write-Host "`n=== Building $($t.Name) ===" -ForegroundColor Cyan
    # arduino-cli requires the .ino to live in a folder of the same name
    $tmp = Join-Path $env:TEMP "nexus_build\sketch"
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $tmp | Out-Null
    Copy-Item (Join-Path $Root $t.Src) (Join-Path $tmp 'sketch.ino')
    $out = Join-Path $Root $t.Out
    New-Item -ItemType Directory -Force $out | Out-Null
    & $Cli compile --fqbn esp32:esp32:esp32 --output-dir $out $tmp
    if ($LASTEXITCODE -ne 0) { throw "Build failed for $($t.Name)" }
    Get-ChildItem $out -Filter 'sketch.ino.*' | Select-Object Name, Length | Format-Table -AutoSize
}
Write-Host "All firmware built. Start the simulations from VS Code (open diagram.json -> Start Simulation)." -ForegroundColor Green

