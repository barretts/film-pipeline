@echo off
setlocal
cd /d "%~dp0"
set "shot=%~1"
if not defined shot set "shot=all"
"%~dp0runtime\inference-env\Scripts\python.exe" -B generation\h3.py render --shot "%shot%"
exit /b %ERRORLEVEL%
