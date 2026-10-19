@echo off
setlocal
cd /d "%~dp0"
echo.
echo  Setting up Sema...
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo  Python is not installed. Install Python 3.12 from https://www.python.org/downloads/
  echo  and tick "Add python.exe to PATH", then run setup.bat again.
  pause
  exit /b 1
)
py -3.12 -c "import sys" >nul 2>nul && (set PY=py -3.12) || (set PY=py -3)
if not exist .venv (
  %PY% -m venv .venv || goto :fail
)
.venv\Scripts\python -m pip install --upgrade pip >nul
.venv\Scripts\python -m pip install -r requirements.txt || goto :fail

rem Start menu + "start with Windows" shortcuts
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell);" ^
  "foreach($dir in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Startup'))){" ^
  " $l=$s.CreateShortcut((Join-Path $dir 'Sema.lnk'));" ^
  " $l.TargetPath='%CD%\.venv\Scripts\pythonw.exe'; $l.Arguments='-m sema'; $l.WorkingDirectory='%CD%';" ^
  " $l.Description='Sema - read anything aloud'; $l.Save() }"

echo.
echo  Done. Sema starts with Windows and is in the Start menu.
echo  Starting it now: look for the Sema icon in the system tray.
start "" .venv\Scripts\pythonw.exe -m sema
exit /b 0

:fail
echo.
echo  Setup failed. See the messages above.
pause
exit /b 1
