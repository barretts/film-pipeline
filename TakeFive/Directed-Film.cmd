@echo off
setlocal
"%~dp0runtime\inference-env\Scripts\python.exe" -B -u "%~dp0generation\directed_film.py" %*
exit /b %ERRORLEVEL%
