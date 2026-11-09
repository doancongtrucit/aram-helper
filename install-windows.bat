@echo off
rem Bấm đúp để cài ARAM Helper (gọi install-windows.ps1, không cần đổi Execution Policy của máy)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1" %*
echo.
pause
