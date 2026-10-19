@echo off
rem Builds a standalone dist\Sema\Sema.exe (no Python needed on the target PC).
cd /d "%~dp0"
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\pyinstaller --noconfirm --windowed --name Sema --collect-all edge_tts ^
  --collect-all uiautomation --collect-submodules winrt --hidden-import pystray._win32 run_sema.py
echo Built dist\Sema\Sema.exe
