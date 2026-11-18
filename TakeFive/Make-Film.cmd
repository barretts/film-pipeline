@echo off
setlocal
"%~dp0runtime\inference-env\Scripts\python.exe" -B "%~dp0generation\make_film.py" %*
set "result=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %result%
