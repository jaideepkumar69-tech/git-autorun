@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>&1 || (echo Python 3.10+ not found in PATH & exit /b 1)
where git >nul 2>&1 || (echo git not found in PATH & exit /b 1)

if /i "%~1"=="test" (
  python test_auto_run.py
  exit /b %errorlevel%
)

if "%~1"=="" (
  set /p URL=GitHub URL: 
  set /p RUN=Run command [blank = auto-detect]: 
) else (
  set URL=%~1
  set RUN=%~2
)

if defined RUN (
  python auto_run.py "%URL%" --run "%RUN%"
) else (
  python auto_run.py "%URL%"
)
pause
