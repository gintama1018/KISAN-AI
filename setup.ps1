# ═══════════════════════════════════════════════════════════
# KISAN AI — Quick Setup Script (Windows PowerShell)
# Run this once to install all dependencies
# ═══════════════════════════════════════════════════════════

Write-Host ""
Write-Host "🌾 KISAN AI — Installing Dependencies" -ForegroundColor Green
Write-Host "════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

# Create virtual environment (use .venv if it already exists)
if (-Not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Cyan
    python -m venv .venv
} else {
    Write-Host "Virtual environment .venv already exists." -ForegroundColor Cyan
}

# Activate it
.\.venv\Scripts\Activate.ps1

# Upgrade pip silently
python -m pip install --upgrade pip --quiet

# Install core requirements (skip optional heavy packages for quick start)
Write-Host "Installing packages..." -ForegroundColor Cyan
pip install flask requests python-dotenv numpy pandas scikit-learn folium deep-translator --quiet
Write-Host "  Core packages installed." -ForegroundColor Green

# pathway is optional and Linux-only in many builds — skip silently
Write-Host "  Note: 'pathway' and 'rasterio' require Linux. Skipping on Windows." -ForegroundColor Yellow
Write-Host "  The Flask app works fully without them (direct API mode)." -ForegroundColor Yellow

Write-Host ""
Write-Host "✅ Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Copy .env.example to .env and add API keys (optional)"
Write-Host "  2. Run:  python app.py"
Write-Host "  3. Open: http://localhost:5000"
Write-Host ""
