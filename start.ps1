# ISRO Lunar Ice Explorer — Quick Start Script
# Starts both backend (FastAPI) and frontend (Next.js) servers
# Usage: .\start.ps1

Write-Host "🚀 ISRO Lunar Ice Explorer — Starting Full Stack..." -ForegroundColor Cyan
Write-Host ""

# Check backend venv
if (-not (Test-Path "backend\venv\Scripts\python.exe")) {
    Write-Host "❌ Backend venv not found. Run setup first:" -ForegroundColor Red
    Write-Host "   cd backend; python -m venv venv; venv\Scripts\pip install -r requirements.txt"
    exit 1
}

# Check frontend node_modules
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "📦 Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location frontend
    npm install
    Set-Location ..
}

Write-Host "▶  Starting Backend (FastAPI) on http://localhost:8000" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\backend'; Write-Host 'Backend Starting...' -ForegroundColor Cyan; venv\Scripts\python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload" -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "▶  Starting Frontend (Next.js) on http://localhost:3000" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\frontend'; Write-Host 'Frontend Starting...' -ForegroundColor Cyan; npm run dev -- --port 3000" -WindowStyle Normal

Start-Sleep -Seconds 5

Write-Host ""
Write-Host "✅ Both servers started!" -ForegroundColor Green
Write-Host ""
Write-Host "   🌐 Frontend:  http://localhost:3000" -ForegroundColor Cyan
Write-Host "   📡 Backend:   http://localhost:8000" -ForegroundColor Cyan
Write-Host "   📚 API Docs:  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "   It takes ~30 seconds for the backend to generate the first scene." -ForegroundColor Yellow
Write-Host "   Refresh the dashboard after the backend is ready." -ForegroundColor Yellow
Write-Host ""
