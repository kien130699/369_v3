@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat
python -m pip install --disable-pip-version-check -r requirements.txt || goto :error
if "%PRICE_SERVER%"=="" set PRICE_SERVER=http://127.0.0.1:3333
if "%WEB_PORT%"=="" set WEB_PORT=3690
start "" http://127.0.0.1:%WEB_PORT%
python -m uvicorn app.main:app --host 127.0.0.1 --port %WEB_PORT%
goto :eof
:error
echo.
echo Khong khoi dong duoc 369 V3. Kiem tra Python 3.11+ va server 3333.
pause
exit /b 1
