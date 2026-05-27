param(
    [string]$ProjectRoot = $PSScriptRoot,
    [string]$PythonExe = "python",
    [string]$PyInstallerRoot = "",
    [string]$DistRoot = "",
    [string]$BuildRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
if ([string]::IsNullOrWhiteSpace($BuildRoot)) {
    $BuildRoot = Join-Path $ProjectRoot "build"
}
if ([string]::IsNullOrWhiteSpace($DistRoot)) {
    $DistRoot = Join-Path $ProjectRoot "dist"
}
if ([string]::IsNullOrWhiteSpace($PyInstallerRoot)) {
    $PyInstallerRoot = Join-Path $BuildRoot "pyinstaller-tools"
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python runtime not found: $PythonExe"
}

$MainScript = Join-Path $ProjectRoot "buzzheavier_tool.py"
$IconPath = Join-Path $ProjectRoot "assets\buzzheavier.ico"
$PyInstallerMain = Join-Path $PyInstallerRoot "PyInstaller\__main__.py"
$SpecRoot = Join-Path $BuildRoot "spec"
$PyInstallerWork = Join-Path $BuildRoot "pyinstaller"

Ensure-Directory -Path $PyInstallerRoot
Ensure-Directory -Path $DistRoot
Ensure-Directory -Path $BuildRoot
Ensure-Directory -Path $SpecRoot

if (-not (Test-Path -LiteralPath $PyInstallerMain)) {
    & $PythonExe -m pip install --upgrade --target $PyInstallerRoot pyinstaller requests
}

$env:PYTHONPATH = $PyInstallerRoot

& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name "BuzzheavierTool" `
    --icon $IconPath `
    --distpath $DistRoot `
    --workpath $PyInstallerWork `
    --specpath $SpecRoot `
    --paths $PyInstallerRoot `
    --collect-submodules requests `
    --collect-submodules urllib3 `
    --collect-submodules charset_normalizer `
    --collect-data certifi `
    $MainScript

$ProxyWrapper = Join-Path $DistRoot "BuzzheavierTool-proxy.bat"
@"
@echo off
setlocal
title Buzzheavier Tool [proxy]
"%~dp0BuzzheavierTool.exe" --proxy on %*
echo.
echo Press any key to close...
pause >nul
endlocal
"@ | Set-Content -Path $ProxyWrapper -Encoding ASCII

Write-Host "Built:"
Write-Host "  $DistRoot\BuzzheavierTool.exe"
Write-Host "  $ProxyWrapper"
