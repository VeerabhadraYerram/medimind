# Script to switch to enhanced multi-file version

Write-Host "Switching to Enhanced Multi-File Version..." -ForegroundColor Green

# Backup original App.jsx if not already backed up
if (-not (Test-Path "frontend\src\App.original.jsx")) {
    Write-Host "Backing up original App.jsx..." -ForegroundColor Yellow
    Copy-Item "frontend\src\App.jsx" "frontend\src\App.original.jsx"
}

# Copy enhanced version
Write-Host "Installing enhanced frontend..." -ForegroundColor Yellow
Copy-Item "frontend\src\AppEnhanced.jsx" "frontend\src\App.jsx" -Force

Write-Host "`n✓ Enhanced version installed!" -ForegroundColor Green
Write-Host "`nTo use the enhanced version:" -ForegroundColor Cyan
Write-Host "1. Start backend: uvicorn backend.api_enhanced:app --reload --host 0.0.0.0 --port 8000" -ForegroundColor White
Write-Host "2. Start frontend: cd frontend; npm run dev" -ForegroundColor White
Write-Host "`nThe enhanced version supports:" -ForegroundColor Cyan
Write-Host "  - Multiple file uploads" -ForegroundColor White
Write-Host '  - Cross-file analysis and trend detection' -ForegroundColor White
Write-Host '  - File management (view/delete)' -ForegroundColor White
