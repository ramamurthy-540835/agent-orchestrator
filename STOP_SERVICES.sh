#!/bin/bash
# Stop all services for Agent Orchestration Platform

echo "=========================================="
echo "Agent Orchestration Platform - Shutdown"
echo "=========================================="
echo ""

# Kill Express on port 3000
echo "Stopping Express Frontend (port 3000)..."
fuser -k 3000/tcp 2>/dev/null && echo "   ✅ Express stopped" || echo "   ℹ️  Express not running"

# Kill Python on port 8001
echo "Stopping Python Orchestration (port 8001)..."
fuser -k 8001/tcp 2>/dev/null && echo "   ✅ Orchestration stopped" || echo "   ℹ️  Orchestration not running"

echo ""
echo "=========================================="
echo "✅ ALL SERVICES STOPPED"
echo "=========================================="
echo ""
