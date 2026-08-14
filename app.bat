@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0main.py" goto no_entrypoint

where.exe python.exe >nul 2>nul
if errorlevel 1 goto no_python

for /f "usebackq delims=" %%I in (`python.exe -c "import sys; print(sys.executable)"`) do set "PYTHON_EXE=%%I"
if not defined PYTHON_EXE goto no_python
for %%I in ("%PYTHON_EXE%") do set "PYTHONW_EXE=%%~dpIpythonw.exe"

"%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto old_python

"%PYTHON_EXE%" -c "import tkinter" >nul 2>nul
if errorlevel 1 goto no_tkinter

if not exist "%PYTHONW_EXE%" goto no_pythonw

if /i "%~1"=="--check" (
    echo Guitar Wiring Simulator startup check passed.
    "%PYTHON_EXE%" --version
    exit /b 0
)

start "Guitar Wiring Simulator" /D "%~dp0" "%PYTHONW_EXE%" "%~dp0main.py"
exit /b 0

:no_entrypoint
echo main.py was not found in:
echo %~dp0
goto failed

:no_python
echo Python was not found on PATH. Install Python 3.10 or later.
goto failed

:old_python
echo Python 3.10 or later is required.
"%PYTHON_EXE%" --version
goto failed

:no_tkinter
echo Tkinter is not available in this Python installation.
echo Install the standard Windows version of Python from python.org.
goto failed

:no_pythonw
echo pythonw.exe was not found next to:
echo %PYTHON_EXE%
echo Try running: python main.py

:failed
pause
exit /b 1
