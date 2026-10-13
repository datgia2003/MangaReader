@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if errorlevel 1 goto fallback
start "" pythonw "%~dp0panel_cutter.pyw"
exit /b
:fallback
pyw -3 "%~dp0panel_cutter.pyw"
if errorlevel 1 pause
