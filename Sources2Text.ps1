# Sources2Text.ps1
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
#   src/pk232py/**/*.py     All Python source files (production code)
#   src/pk232py/help/*.md   Help files (Markdown)
#   tools/**/*.py           Standalone tools (FAX generator/decoder, etc.)
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
#   tools/                 Standalone tools (FAX WAV generator/decoder, etc.)
#
# Each file is preceded by a separator line:
#   # === <relative path> ===
# =============================================================================

"@

# ---------------------------------------------------------------------------
# Helper: canonical repo-relative path for a file (forward slashes).
#
# Works for any file under the repo root, not just src/pk232py. Earlier the
# path logic special-cased "src/pk232py/..." via regex; tools/ files did not
# match and fell through to a brittle root-trim. This helper strips the repo
# root once and normalises separators, so headers are correct for src/, help/
# and tools/ alike.
# ---------------------------------------------------------------------------

function Get-RelPath {
    param([string] $AbsPath)

    # Normalise both to forward slashes first, then strip the repo root prefix.
    $absNorm  = $AbsPath.Replace("\", "/")
    $rootNorm = $repoRoot.Replace("\", "/").TrimEnd("/")

    if ($absNorm.StartsWith($rootNorm + "/", [System.StringComparison]::OrdinalIgnoreCase)) {
        return $absNorm.Substring($rootNorm.Length + 1)
    }
    # Fallback: keep a recognisable tail if the file is somehow outside the root.
    return $absNorm
}

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

# Scan src/pk232py (production code) AND tools/ (standalone tools).
# Each scanned root is optional: if it does not exist we just skip it.
$pyScanRoots = @("src/pk232py", "tools")

$pyFilesRaw = @()
foreach ($root in $pyScanRoots) {
    if (Test-Path $root) {
        $pyFilesRaw += Get-ChildItem -Path $root -Recurse -Filter "*.py"
    } else {
        Write-Host "INFO: scan root '$root' not found - skipped"
    }
}

$pyFiles = $pyFilesRaw |
    Where-Object {
        # Optionally skip test files
        if ($SkipTests -and $_.FullName -match "[\\/]tests[\\/]") { return $false }
        return $true
    } |
    Sort-Object {
        $rel   = Get-RelPath $_.FullName
        $depth = ($rel.Split("/", [System.StringSplitOptions]::None)).Count
        $prio  = 99
        for ($i = 0; $i -lt $priorityOrder.Count; $i++) {
            if ($_.Name -eq $priorityOrder[$i]) { $prio = $i; break }
        }
        # src/ before tools/ at equal depth: prefix a source-group key so the
        # production code is listed first, tools afterwards.
        $group = if ($rel.StartsWith("src/")) { "0" } else { "1" }
        "{0}_{1:D2}_{2:D2}_{3}" -f $group, $depth, $prio, $rel
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
    $relPath = Get-RelPath $absPath

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
    $relPath = Get-RelPath $absPath

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