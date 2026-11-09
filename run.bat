@echo off
rem Mở ARAM Helper không kèm cửa sổ dòng lệnh (log ghi vào data\app.log)
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" app.py %*
) else (
  start "" pythonw app.py %*
)
