#!/bin/bash
# Start all services for Agent Orchestration Platform

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "Agent Orchestration Platform - Startup"
echo "=========================================="
echo ""

# Load environment
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found in project root"
    echo "   Please create .env with Databricks credentials"
    exit 1
fi

echo "✅ Loading environment from .env"
source .env

# Start Python orchestration service
echo ""
echo "Starting Python Orchestration Service (port 8001)..."
source venv/bin/activate
nohup python -m orchestration.server > /tmp/orchestration.log 2>&1 &
PYTHON_PID=$!
echo "   PID: $PYTHON_PID"
sleep 4

# Verify Python service
if curl -s http://localhost:8001/databricks/status > /dev/null 2>&1; then
    echo "   ✅ Python service is running"
else
    echo "   ❌ Failed to start Python service. Check /tmp/orchestration.log"
    tail -20 /tmp/orchestration.log
    exit 1
fi

# Start Express frontend
echo ""
echo "Starting Express Frontend (port 3000)..."
nohup npm start > /tmp/express.log 2>&1 &
EXPRESS_PID=$!
echo "   PID: $EXPRESS_PID"
sleep 4

# Verify Express service
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "   ✅ Express service is running"
else
    echo "   ❌ Failed to start Express service. Check /tmp/express.log"
    tail -20 /tmp/express.log
    exit 1
fi

# Display status
echo ""
echo "=========================================="
echo "✅ ALL SERVICES STARTED"
echo "=========================================="
echo ""
echo "📍 Access Points:"
echo "   - Express Frontend:    http://localhost:3000"
echo "   - Orchestration API:   http://localhost:8001"
echo "   - API Settings:        http://localhost:3000/settings"
echo ""
echo "📊 Logs:"
echo "   - Express:      tail -f /tmp/express.log"
echo "   - Orchestration: tail -f /tmp/orchestration.log"
echo ""
echo "🔧 Configuration:"
echo "   - Root Config:   .env"
echo "   - Orchestration: orchestration/.env"
echo ""
echo "Use STOP_SERVICES.sh to stop all services"
echo ""
