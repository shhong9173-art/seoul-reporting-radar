@echo off
setlocal
cd /d "%~dp0"
echo NTIS PATENT OUTCOME PROJECT-ID SEARCH FIELD CHECK
echo Previous approved-PC 3-project pilot: 6 successful requests, zero indexed HITs.
echo This is a small POSITIVE CONTROL to test TI / BI / TI03 indexing.
echo At most 6 HTTPS requests; first 10 results only.
echo No unrelated ProjectID, ResultID, or raw HIT rows are exported.
echo The NTIS approved key is entered privately and never stored.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ntis_project_field_control_pc.ps1"
echo.
echo Attach ONLY ntis_project_field_probe_pc_latest.json to the conversation.
echo If there is an error, copy only RESULT and DIAGNOSTIC lines. Never send the key.
pause
