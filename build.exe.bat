@echo off
setlocal
cd /d "%~dp0"
title PK232PY Cyberpunk Windows Builder

echo ============================================================
echo   PK232PY Cyberpunk + MFJ-1278 Windows Build
echo ============================================================
echo.

where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo ERROR: Windows PowerShell was not found.
  pause
  exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows_cyberpunk.ps1"
set ERR=%ERRORLEVEL%

if not "%ERR%"=="0" (
  echo.
  echo BUILD FAILED with exit code %ERR%.
  pause
  exit /b %ERR%
)

echo.
echo BUILD COMPLETED.
echo Executable: dist\pk232py.exe
pause
exit /b 0
