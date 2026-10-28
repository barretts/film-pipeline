@echo off
setlocal
cd /d "%~dp0"
if not defined LOCAL_FILM_PORT set "LOCAL_FILM_PORT=8765"
if exist "local-runtime\venv\Scripts\python.exe" (
  set "FILM_PYTHON=%CD%\local-runtime\venv\Scripts\python.exe"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python was not found. See LOCAL_FILM_INSTALL_GUIDE.md.
    pause
    exit /b 1
  )
  set "FILM_PYTHON=python"
)
set "LOCAL_FILM_OPEN_BROWSER=1"
"%FILM_PYTHON%" -m local_film.server
if errorlevel 1 (
  echo The local film server stopped. Check the error above and the installation guide.
  pause
)
endlocal
