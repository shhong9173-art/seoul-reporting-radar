@echo off
setlocal
cd /d "%~dp0"
echo NTIS APPROVED-PC TARGETED FOLLOW-UP
echo Scope: 4 technology searches pages 2-3; 7 narrow company+technology searches.
echo Maximum 15 requests. Your NTIS key is hidden and never saved.
echo Official number matches are investigative leads, not exclusive news.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ntis_patent_followup_pc.ps1"
echo.
echo Attach ONLY ntis_patent_followup_pc_latest.json; never send the key.
pause
