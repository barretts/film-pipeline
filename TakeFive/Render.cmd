@echo off
setlocal
if "%~1"=="" goto textfilm
if /i "%~x1"==".txt" goto textfilm
set "source=%~f1"
cd /d "%~dp0"
if not defined source set "source=examples\dispatch.txt"
set "reference="
if exist "films\office\render.json" set "reference=--reuse films\office"
python film.py render "%source%" --out output %reference%
set "result=%ERRORLEVEL%"
pause
exit /b %result%
:textfilm
call "%~dp0Make-Film.cmd" %*
exit /b %ERRORLEVEL%
