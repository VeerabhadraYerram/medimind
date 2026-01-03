# Script to start both Enhanced Backend and Frontend

Write-Host "Starting Enhanced Backend and Frontend..." -ForegroundColor Green
Write-Host "This will open two separate terminal windows" -ForegroundColor Cyan
Write-Host ""

# Get the current directory
$rootDir = Get-Location

# Start Backend in a new window
Write-Host "Starting Backend in new window..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir'; .\venv\Scripts\Activate.ps1; Write-Host 'Enhanced Backend Starting...' -ForegroundColor Green; uvicorn backend.api_enhanced:app --reload --host 0.0.0.0 --port 8000"

# Wait a moment
Start-Sleep -Seconds 2

# Start Frontend in a new window
Write-Host "Starting Frontend in new window..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootDir\frontend'; Write-Host 'Frontend Starting...' -ForegroundColor Green; npm run dev"

Write-Host ""
Write-Host "✓ Both services are starting in separate windows!" -ForegroundColor Green
Write-Host "Backend will be available at: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend will be available at: http://localhost:5173 (or check the terminal)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to close this window..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

