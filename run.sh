#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# KISAN AI — Linux/Mac Startup Script
# Starts Pathway stream engine + Flask web server
# ═══════════════════════════════════════════════════════════════

echo ""
echo "🌾 KISAN AI — Real-Time Farm Intelligence"
echo "📡 ISRO + NASA Satellite Data + Pathway Streaming"
echo "═══════════════════════════════════════════════════"
echo ""

# Check .env exists
if [ ! -f ".env" ]; then
    echo "INFO: .env not found — copying from .env.example"
    cp .env.example .env
    echo "INFO: Edit .env to add API keys (optional for demo)"
    echo ""
fi

# Export env
export $(grep -v '^#' .env | xargs)
export ALERTS_FILE=${ALERTS_FILE:-/tmp/kisan_alerts.jsonl}

echo "[1/2] Starting Pathway stream engine in background..."
echo "      Polls every hour. Output: $ALERTS_FILE"
python pipeline/stream.py &
PATHWAY_PID=$!
echo "      PID: $PATHWAY_PID"
echo ""

# Brief pause for Pathway to init
sleep 3

echo "[2/2] Starting Flask web server..."
echo ""
echo "  ═══════════════════════════════════════════════"
echo "   Dashboard: http://localhost:5000"
echo "  ═══════════════════════════════════════════════"
echo ""

# On Mac, auto-open browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    sleep 2 && open http://localhost:5000 &
fi

python app.py

# Clean up Pathway on exit
kill $PATHWAY_PID 2>/dev/null
