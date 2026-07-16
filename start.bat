@echo off
title Start Marketing Automation Servers
echo ===================================================
echo   Starting Marketing Automation Servers...
echo ===================================================

echo Starting Backend API Server (Uvicorn)...
start "Backend API Server" cmd /k "cd backend && .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting Frontend Dev Server (Vite)...
start "Frontend Dev Server" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo Both servers have been started in separate command prompt windows!
pause
