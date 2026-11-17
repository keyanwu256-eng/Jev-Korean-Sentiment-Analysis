@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
py -3.11 -m venv .venv
if not errorlevel 1 goto install
if not exist "C:\Users\Public\miniconda3\envs\jev_project\python.exe" goto missing
"C:\Users\Public\miniconda3\envs\jev_project\python.exe" -m venv .venv
if errorlevel 1 goto failed
:install
set "JEV_REQUIREMENTS=requirements.txt"
if exist "requirements-lock.txt" set "JEV_REQUIREMENTS=requirements-lock.txt"
".venv\Scripts\python.exe" -m pip install -r "%JEV_REQUIREMENTS%" --index-url https://pypi.org/simple --only-binary=:all:
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import numpy, onnxruntime, tokenizers, streamlit"
if errorlevel 1 goto failed
echo Setup complete. Double-click Start_Jev.bat.
pause
exit /b 0
:missing
echo Python 3.11 was not found. Install Python 3.11, then run this file again.
:failed
echo Setup failed. Please keep the error above for troubleshooting.
pause
exit /b 1
