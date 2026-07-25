param(
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\pyproject.toml")) {
    throw "Copy this script into the full PK232PY project root before running it."
}

function Test-PythonCommand {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    # Missing Python versions write a diagnostic to stderr. Probe them without
    # allowing PowerShell's global Stop policy to turn that expected result into
    # a terminating NativeCommandError.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        & $Command @Arguments -c "import sys; raise SystemExit(0)" *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

# Prefer Python 3.13 for Nuitka. If unavailable, use the normal Python launcher
# default or python.exe. Existing virtual environments are preserved.
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    $created = $false
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue

    if ($PyLauncher -and (Test-PythonCommand -Command "py" -Arguments @("-3.13"))) {
        Write-Host "Creating virtual environment with Python 3.13..."
        & py -3.13 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Python 3.13 could not create the virtual environment." }
        $created = $true
    }
    elseif ($PyLauncher -and (Test-PythonCommand -Command "py" -Arguments @("-3"))) {
        Write-Warning "Python 3.13 is not installed. Using the default Python 3 runtime instead."
        & py -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "The default Python launcher could not create the virtual environment." }
        $created = $true
    }
    else {
        $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($PythonCommand -and (Test-PythonCommand -Command "python" -Arguments @())) {
            Write-Warning "Python 3.13 is not installed. Using python.exe instead."
            & python -m venv .venv
            if ($LASTEXITCODE -ne 0) { throw "python.exe could not create the virtual environment." }
            $created = $true
        }
    }

    if (-not $created) {
        throw "No usable 64-bit Python 3 runtime was found. Install Python 3.13 or another supported Python 3 release."
    }
}

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "The virtual environment was not created correctly: $Python is missing."
}

& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }

# The upstream Nuitka command explicitly includes markdown, although it is not
# declared by the project's pyproject.toml, so install it here.
& $Python -m pip install -e ".[dev]" nuitka markdown
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

if (-not (Test-Path ".\build_windows.ps1")) {
    throw "The official build_windows.ps1 file is missing from the project root."
}

$IconPath = Join-Path $PSScriptRoot "pk232py.ico"
if (-not (Test-Path $IconPath)) {
    throw "Application icon is missing: $IconPath"
}

# Ensure the official Nuitka command actually receives the icon option. The
# upstream line ends with a PowerShell continuation backtick, which the prior
# patch did not recognize.
$OfficialBuild = Join-Path $PSScriptRoot "build_windows.ps1"
$BuildText = Get-Content $OfficialBuild -Raw
$IconOption = '    --windows-icon-from-ico="' + $IconPath + '" `'

if ($BuildText -match '(?m)^\s*--windows-icon-from-ico=.*$') {
    $BuildText = [regex]::Replace(
        $BuildText,
        '(?m)^\s*--windows-icon-from-ico=.*$',
        { param($m) $IconOption },
        1
    )
}
elseif ($BuildText -match '(?m)^(\s*--windows-console-mode=disable\s+`\s*)$') {
    $BuildText = [regex]::Replace(
        $BuildText,
        '(?m)^(\s*--windows-console-mode=disable\s+`\s*)$',
        { param($m) $m.Groups[1].Value + "`r`n" + $IconOption },
        1
    )
}
else {
    throw "Could not locate the Nuitka Windows console option in build_windows.ps1."
}
Set-Content -Path $OfficialBuild -Value $BuildText -Encoding UTF8

# Remove previous build products so Windows cannot continue showing an older
# executable that was compiled before the icon option was present.
if (Test-Path ".\dist\pk232py.exe") {
    Remove-Item ".\dist\pk232py.exe" -Force
}
Get-ChildItem -Path $PSScriptRoot -Directory -Filter "*.build" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path $PSScriptRoot -Directory -Filter "*.dist" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path $PSScriptRoot -Directory -Filter "*.onefile-build" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

Write-Host "Using application icon: $IconPath" -ForegroundColor Cyan
& .\build_windows.ps1 -Version $Version
if ($LASTEXITCODE -ne 0) {
    throw "PK232PY Windows build failed with exit code $LASTEXITCODE."
}
