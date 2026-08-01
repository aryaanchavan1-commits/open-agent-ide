@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   Arynox AI - Launcher
echo ============================================
echo   Backend : http://localhost:8000
echo   Frontend: http://localhost:3000
echo ============================================
echo.

if not exist "backend\.venv\Scripts\python.exe" (
    echo [ERROR] Backend venv not found: backend\.venv
    echo         Run:  python -m venv backend\.venv
    echo         Then: backend\.venv\Scripts\pip install -r backend\requirements.txt
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo [WARN] frontend\node_modules not found - run:  npm install  in frontend\
)

echo [run] Checking ports 8000/3000...
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul 2>&1 && echo [WARN] Port 8000 already in use - backend may fail to start
netstat -ano | findstr /R /C:":3000 .*LISTENING" >nul 2>&1 && echo [WARN] Port 3000 already in use - frontend may fail to start

if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    netstat -ano | findstr /R /C:":11434 .*LISTENING" >nul 2>&1
    if errorlevel 1 (
        echo [run] Starting Ollama...
        start "Arynox Ollama" "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
    ) else (
        echo [run] Ollama already running
    )
) else (
    echo [run] Ollama not found at %LOCALAPPDATA%\Programs\Ollama - install from https://ollama.com
)

echo [run] Starting backend...
start "Arynox Backend" /D "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"

echo [run] Starting frontend...
start "Arynox Frontend" /D "%~dp0frontend" cmd /k "set NODE_OPTIONS=--max-old-space-size=4096&& npm run dev"

echo [run] Waiting for services...
timeout /t 10 /nobreak >nul

echo [run] Opening browser at http://localhost:3000 ...
start http://localhost:3000

echo.
echo All services launched in separate windows.
echo Close the "Arynox Backend"/"Arynox Frontend" windows to stop them.
echo.
pause
endlocal
