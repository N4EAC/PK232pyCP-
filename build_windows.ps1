# PK232PY — Windows onefile build script
# Requires: .venv with nuitka installed, Python 3.x (CPython official build,
#           NOT the Microsoft Store Python — its sandbox breaks onefile).
# Output:   dist\pk232py.exe  (single self-contained executable)
#
# Usage:    .\build_windows.ps1            # builds v0.1.0
#           .\build_windows.ps1 -Version 0.2.0
#
# The C compiler (MinGW64) is downloaded and cached automatically by Nuitka on
# the first build (%LOCALAPPDATA%\Nuitka\Nuitka\Cache\downloads\gcc\), so no
# manual toolchain install is needed.

param(
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$DistDir  = Join-Path $RepoRoot "dist"

Write-Host "Building PK232PY v$Version for Windows (onefile)..."

# Ensure output directory exists
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

# Activate the project venv (so `python` is the venv interpreter with Nuitka)
$Activate = Join-Path $RepoRoot ".venv\Scripts\Activate.ps1"
. $Activate

# Entry point: src/pk232py/__main__.py  ->  `python -m pk232py`
python -m nuitka `
    --onefile `
    --enable-plugin=pyqt6 `
    --include-qt-plugins=sensible,styles `
    --include-data-dir="src/pk232py/help=pk232py/help" `
    --include-package=serial `
    --include-package=markdown `
    --windows-console-mode=disable `
    --windows-product-name="PK232PY" `
    --windows-product-version="$Version.0" `
    --windows-company-name="OE3GAS" `
    --windows-file-description="Multimode Terminal for AEA PK-232MBX" `
    --output-dir="$DistDir" `
    --output-filename="pk232py.exe" `
    --assume-yes-for-downloads `
    --show-progress `
    src/pk232py/__main__.py

Write-Host ""
$Exe = Join-Path $DistDir "pk232py.exe"
Write-Host "Build complete: $Exe"
$SizeMB = [math]::Round((Get-Item $Exe).Length / 1MB, 1)
Write-Host "File size: $SizeMB MB"
