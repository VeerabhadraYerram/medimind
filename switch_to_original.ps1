# Script to switch back to original version

Write-Host "Switching back to Original Version..." -ForegroundColor Green

if (Test-Path "frontend\src\App.original.jsx") {
    Write-Host "Restoring original App.jsx..." -ForegroundColor Yellow
    Copy-Item "frontend\src\App.original.jsx" "frontend\src\App.jsx" -Force
    Write-Host "`n✓ Original version restored!" -ForegroundColor Green
} else {
    Write-Host "`n✗ Original backup not found!" -ForegroundColor Red
    Write-Host "Please restore manually or re-clone the repository." -ForegroundColor Yellow
}

Write-Host "`nTo use the original version:" -ForegroundColor Cyan
Write-Host "1. Start backend: uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000" -ForegroundColor White
Write-Host "2. Start frontend: cd frontend && npm run dev" -ForegroundColor White

