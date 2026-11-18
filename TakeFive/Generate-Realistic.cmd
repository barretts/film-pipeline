@echo off
setlocal
cd /d "%~dp0"
set "shot=%~1"
if not defined shot set "shot=manager"
"%~dp0runtime\inference-env\Scripts\python.exe" -B generation\realistic.py render --shot "%shot%"
set "result=%ERRORLEVEL%"
pause
exit /b %result%
