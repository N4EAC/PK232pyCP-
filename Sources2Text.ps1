# Export-PK232PySources.ps1
#
# Generates pk232py_sources.txt for upload to the Claude project knowledge base.
# Run from the repository root:
#
#   .\Sources2Text.ps1
#
# Optional parameters:
#   -OutputFile   path to output file    (default: pk232py_sources.txt)
#   -SkipEmpty    skip __init__.py files that contain only comments/whitespace
#   -SkipTests    skip files in tests/ directories
#
# Files included:
#   src/pk232py/**/*.py     All Python source files
#   src/pk232py/help/*.md   Help files (Markdown)
#
# The output file is UTF-8 without BOM, LF line endings, no duplicate files.

param(
    [string] $OutputFile = "pk232py_sources.txt",
    [switch] $SkipEmpty  = $true,
    [switch] $SkipTests  = $false
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Header: repo info and timestamp
# ---------------------------------------------------------------------------

$repoRoot  = (Get-Location).Path.TrimEnd()
$timestamp = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " UTC+0"

# Try to get git info (gracefully skip if git not available)
$gitBranch = ""
$gitHash   = ""
try {
    $gitBranch = & git rev-parse --abbrev-ref HEAD 2>$null
    $gitHash   = & git rev-parse --short HEAD       2>$null
} catch { }

$header = @"
# =============================================================================
# PK232PY - Python source export for Claude project knowledge
# Generated : $timestamp
# Repo root : $repoRoot
$(if ($gitBranch) { "# Branch    : $gitBranch  ($gitHash)" })
# =============================================================================
#
# Structure:
#   src/pk232py/
#     config.py            Application config dataclasses + INI read/write
#     main.py              Entry point
#     mode_manager.py      Mode switching logic
#     comm/                Serial communication, Host Mode protocol, frames
#     modes/               One file per operating mode (backend logic)
#     ui/                  PyQt6 main window and dialogs
#     ui/screens/          Opmode screens (mockup + production)
#     help/                Help files (Markdown, included as-is)
#     log/                 QSO log (SQLite)
#     macros/              Macro system
#     maildrop/            MailDrop (TNC mail box)
#     tests/               Unit tests
#
# Each file is preceded by a separator line:
#   # === <relative path> ===
# =============================================================================

"@

# ---------------------------------------------------------------------------
# Collect Python source files
# ---------------------------------------------------------------------------

# Priority order: important files first, then alphabetical within each group
$priorityOrder = @(
    "config.py",
    "main.py",
    "mode_manager.py",
    "__main__.py"
)

$pyFiles = Get-ChildItem -Path "src/pk232py" -Recurse -Filter "*.py" |
    Where-Object {
        # Optionally skip test files
        if ($SkipTests -and $_.FullName -match "[\\/]tests[\\/]") { return $false }
        return $true
    } |
    Sort-Object {
        $rel   = $_.FullName.Replace($repoRoot, "").TrimStart("\\/")
        $depth = ($rel.Split("[\\/]", [System.StringSplitOptions]::None)).Count
        $prio  = 99
        for ($i = 0; $i -lt $priorityOrder.Count; $i++) {
            if ($_.Name -eq $priorityOrder[$i]) { $prio = $i; break }
        }
        "{0:D2}_{1:D2}_{2}" -f $depth, $prio, $rel
    }

# ---------------------------------------------------------------------------
# Collect Markdown help files (src/pk232py/help/*.md)
# ---------------------------------------------------------------------------

$helpDir = Join-Path "src/pk232py" "help"
$mdFiles = @()
if (Test-Path $helpDir) {
    $mdFiles = @(Get-ChildItem -Path $helpDir -Recurse -Filter "*.md" |
        Sort-Object Name)
} else {
    Write-Host "INFO: help/ directory not found at $helpDir - no .md files included"
}

# ---------------------------------------------------------------------------
# Deduplicate using canonical relative path
# ---------------------------------------------------------------------------

$seen  = @{}
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add($header)

$included = 0
$skipped  = 0

# -- Process Python files -----------------------------------------------------
foreach ($file in $pyFiles) {
    $absPath = $file.FullName

    if ($absPath -match '(src[/\\]pk232py[/\\].+)$') {
        $relPath = $Matches[1].Replace("\", "/")
    } else {
        $relPath = $absPath.Replace($repoRoot + "\", "").Replace("\", "/")
    }

    if ($seen.ContainsKey($relPath)) {
        $skipped++
        continue
    }
    $seen[$relPath] = $true

    $content = (Get-Content $absPath -Raw -Encoding UTF8) -replace "`r`n", "`n" -replace "`r", "`n"

    if ($SkipEmpty -and $file.Name -eq "__init__.py") {
        $stripped = $content -replace "#[^\n]*", "" -replace "\s", ""
        if ($stripped.Length -eq 0) {
            $skipped++
            continue
        }
    }

    $lines.Add("# === $relPath ===")
    $lines.Add($content)
    $lines.Add("")
    $included++
}

# -- Process Markdown help files -----------------------------------------------
foreach ($file in $mdFiles) {
    $absPath = $file.FullName

    if ($absPath -match '(src[/\\]pk232py[/\\].+)$') {
        $relPath = $Matches[1].Replace("\", "/")
    } else {
        $relPath = $absPath.Replace($repoRoot + "\", "").Replace("\", "/")
    }

    if ($seen.ContainsKey($relPath)) {
        $skipped++
        continue
    }
    $seen[$relPath] = $true

    $content = (Get-Content $absPath -Raw -Encoding UTF8) -replace "`r`n", "`n" -replace "`r", "`n"

    $lines.Add("# === $relPath ===")
    $lines.Add($content)
    $lines.Add("")
    $included++
}

# ---------------------------------------------------------------------------
# Footer: summary
# ---------------------------------------------------------------------------

$footer = @"
# =============================================================================
# End of export
# Files included : $included
# Files skipped  : $skipped  (duplicates / empty __init__.py)
# =============================================================================
"@
$lines.Add($footer)

# ---------------------------------------------------------------------------
# Write output - UTF-8 without BOM, LF line endings
# ---------------------------------------------------------------------------

$outputPath = Join-Path $repoRoot $OutputFile
$utf8NoBom  = [System.Text.UTF8Encoding]::new($false)

[System.IO.File]::WriteAllText(
    $outputPath,
    ($lines -join "`n"),
    $utf8NoBom
)

Write-Host "OK  Written to: $outputPath"
Write-Host "    Python files:  $(([array]$pyFiles).Count) found"
Write-Host "    Help files:    $(([array]$mdFiles).Count) found"
Write-Host "    Included:      $included files"
Write-Host "    Skipped:       $skipped files"