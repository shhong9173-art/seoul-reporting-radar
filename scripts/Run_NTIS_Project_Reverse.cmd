@echo off
setlocal
cd /d "%~dp0"
echo NTIS PROJECT-ID REVERSE PATENT OUTCOME SEARCH
echo 26 unique official project IDs from approved PC.
echo Uses TI (project ID) and documented TI03 fallback on zero primary hits.
echo Maximum 52 official requests, first page only. No scoops are inferred.
echo Your API key is requested privately and never saved.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ntis_project_reverse_pc.ps1" -MaxProjects 26
echo.
echo OUTPUT: ntis_project_reverse_pc_latest.json
echo Review the JSON before sharing. Never send your key or raw request URL.
pause
