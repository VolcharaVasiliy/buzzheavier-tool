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

function Test-Command {
    param([string]$Command)
    if (Test-Path -LiteralPath $Command) {
        return $true
    }
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

if (-not (Test-Command -Command $PythonExe)) {
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

$LegacyProxyWrapper = Join-Path $DistRoot "BuzzheavierTool-proxy.bat"
if (Test-Path -LiteralPath $LegacyProxyWrapper) {
    Remove-Item -LiteralPath $LegacyProxyWrapper -Force
}

if (-not (Test-Path -LiteralPath $PyInstallerMain)) {
    & $PythonExe -m pip install --upgrade --target $PyInstallerRoot pyinstaller requests curl_cffi
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
    --collect-submodules curl_cffi `
    --collect-binaries curl_cffi `
    --collect-submodules urllib3 `
    --collect-submodules charset_normalizer `
    --collect-data certifi `
    $MainScript

Write-Host "Built:"
Write-Host "  $DistRoot\BuzzheavierTool.exe"
