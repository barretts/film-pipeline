@echo off
setlocal
cd /d "%~dp0"
set "shot=%~1"
if not defined shot set "shot=all"
"%~dp0runtime\inference-env\Scripts\python.exe" -B generation\h3.py render --shot "%shot%" --bundle films\signal-in-the-snow --looks films\signal-in-the-snow\looks --direction generation\h3-snow.json --out output\signal-in-the-snow
exit /b %ERRORLEVEL%
