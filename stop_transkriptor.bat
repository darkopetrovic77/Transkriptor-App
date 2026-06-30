@echo off
taskkill /FI "WINDOWTITLE eq Transkriptor*" /T /F >nul 2>&1
echo Transkriptor gestoppt.
timeout /t 2 /nobreak >nul
