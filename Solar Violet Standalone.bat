@echo off
rem Starts the Solar Violet browsers and download queue without ComfyUI: http://127.0.0.1:8765
rem Uses the ComfyUI Python next to this pack when there is one, otherwise the Python on your PATH.
cd /d "%~dp0"
set "PY=%~dp0..\..\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
start "" http://127.0.0.1:8765/
"%PY%" standalone.py %*
pause
