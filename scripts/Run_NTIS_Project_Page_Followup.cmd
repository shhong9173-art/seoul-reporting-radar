@echo off
setlocal
cd /d "%~dp0"
echo NTIS OFFICIAL PAGE 2 FOLLOW-UP - PROJECT 1415180715
echo This checks both 10-row pages again, at most 2 official requests.
echo It never proves commercialization, company participation, or an exclusive.
echo Run only on your NTIS-approved Windows PC. Keep your API key private.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ntis_project_page_followup_pc.ps1"
echo.
echo On success attach ONLY ntis_project_page_followup_pc_latest.json
pause
