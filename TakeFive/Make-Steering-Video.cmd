@echo off
setlocal
if not defined TAKEFIVE_RUNTIME set "TAKEFIVE_RUNTIME=%~dp0runtime"
if not exist "%TAKEFIVE_RUNTIME%\inference-env\Scripts\python.exe" if exist "F:\TakeFive\runtime\inference-env\Scripts\python.exe" set "TAKEFIVE_RUNTIME=F:\TakeFive\runtime"
if "%~1"=="" (
  "%TAKEFIVE_RUNTIME%\inference-env\Scripts\python.exe" -B -u "%~dp0steering\film.py" "%~dp0examples\dispatch.txt"
) else (
  "%TAKEFIVE_RUNTIME%\inference-env\Scripts\python.exe" -B -u "%~dp0steering\film.py" %*
)
exit /b %ERRORLEVEL%
