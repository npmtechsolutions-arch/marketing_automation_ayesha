# PowerShell script to start both Backend and Frontend servers in separate windows

Write-Host "Starting Backend API Server..." -ForegroundColor Magenta
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

Write-Host "Starting Frontend Vite Server..." -ForegroundColor Blue
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "Both servers started in separate terminal windows successfully!" -ForegroundColor Green
