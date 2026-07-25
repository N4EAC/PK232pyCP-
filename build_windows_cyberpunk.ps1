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

& .\build_windows.ps1 -Version $Version
if ($LASTEXITCODE -ne 0) {
    throw "PK232PY Windows build failed with exit code $LASTEXITCODE."
}
