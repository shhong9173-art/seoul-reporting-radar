@echo off
setlocal
cd /d "%~dp0"
echo NTIS PATENT OUTCOME DISCOVERY - 2026-10
echo Uses KIPRIS patent title / technology / verified corporate applicant.
echo Keyword matching alone is NOT a confirmed national R&D patent outcome.
echo Run on approved NTIS Windows PC. API key stays hidden.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ntis_patent_discovery_pc.ps1" -MaxTargets 7 -MaxQueries 14 -MaxPages 1
echo.
echo OUTPUT: ntis_patent_discovery_pc_latest.json
echo Review the JSON before sending. NEVER send your NTIS key.
pause
