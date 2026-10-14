@echo off
setlocal
cd /d "%~dp0"
echo NTIS APPROVED-PC COLLECTION
echo Enter your NTIS key only in the hidden PowerShell prompt.
echo The key is never saved or published.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ntis_pc_collect.ps1" -MaxQueries 8
echo.
echo === End of run. Review the result and the JSON file. ===
pause
