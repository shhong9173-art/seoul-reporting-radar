@echo off
setlocal
cd /d "%~dp0"
echo NTIS OFFICIAL PROJECT-ID REVERSE LOOKUP - REMAINING 23
echo Pilot 3 official project IDs were already checked on 2026-10-15.
echo Source: validated live positive-control ResultID recovered via TI, BI, TI03.
echo Runs only remaining 23 official project IDs, maximum 46 API requests.
echo Search scope: first 10 rpatent HITs per query; 0 does not prove absence.
echo Output stays separate from prior 3-project pilot record.
echo NTIS approved API key is hidden and never stored.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ntis_project_reverse_pc.ps1" -MaxProjects 26 -SkipFirstProjects 3
echo.
echo OUTPUT: ntis_project_reverse_remaining_23_pc_latest.json
echo Review JSON and attach ONLY this result. Never send your API key.
pause
