@echo off
setlocal
cd /d "%~dp0"
echo NTIS NATIONAL R&D PATENT OUTCOME SCHEMA CHECK
echo The official outcome API may require separate approval.
echo Your key is requested with hidden input, never saved.
echo This tool exports XML FIELD NAMES ONLY - no individual data.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ntis_patent_outcome_probe.ps1"
echo.
echo Please send only ntis_patent_outcome_schema_probe.json - never the key.
pause
