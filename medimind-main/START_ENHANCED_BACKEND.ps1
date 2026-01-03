# Script to start the Enhanced Backend

Write-Host "Starting Enhanced Multi-File Backend..." -ForegroundColor Green
Write-Host "Make sure to stop any existing backend first (Ctrl+C in that terminal)" -ForegroundColor Yellow
Write-Host ""

# Activate virtual environment and start enhanced backend
.\venv\Scripts\Activate.ps1
uvicorn backend.api_enhanced:app --reload --host 0.0.0.0 --port 8000

