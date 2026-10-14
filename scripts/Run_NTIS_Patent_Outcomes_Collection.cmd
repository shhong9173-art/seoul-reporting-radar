@echo off
setlocal
cd /d "%~dp0"
echo NTIS PATENT OUTCOME RESEARCH
echo NTIS approved Windows PC and approved patent-outcome API key required.
echo Requests are made to official NTIS over HTTPS.
echo Application-number/project-number matches ONLY; never proven commercialization.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ntis_patent_outcomes_pc_collect.ps1" -MaxTargets 7
echo.
echo Check ntis_patent_outcomes_pc_latest.json before sharing. NEVER share your key.
pause
