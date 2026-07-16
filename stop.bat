@echo off
title Stop Marketing Automation Servers
echo ===================================================
echo   Stopping Marketing Automation Servers...
echo ===================================================

echo Stopping process on port 8000 (Backend)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a
)

echo Stopping process on port 5173 (Frontend)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a
)

echo All servers stopped successfully!
pause
