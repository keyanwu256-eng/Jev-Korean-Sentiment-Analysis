@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto setup
".venv\Scripts\python.exe" -c "import numpy, onnxruntime, tokenizers, streamlit"
if errorlevel 1 goto setup
".venv\Scripts\python.exe" -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=2)" >nul 2>&1
if not errorlevel 1 (
    start "" "http://localhost:8501"
    exit /b 0
)
echo Keep this window open while using Jev. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address localhost --server.port 8501
pause
exit /b
:setup
echo The local environment is missing or incomplete. Run Setup_Jev.bat first.
pause
exit /b 1
