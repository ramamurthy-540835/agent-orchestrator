#!/bin/bash

# Quick Setup Script - Minimal config, no Databricks access needed yet

cd /home/appadmin/projects/Ram_Projects/agents-db

echo "🚀 Quick Setup for agents-db"
echo ""

# 1. Check if services are running
echo "1️⃣  Checking services..."
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "   ✅ Python service (8001) running"
else
    echo "   ⏳ Python service (8001) - not running (start it separately)"
fi

if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "   ✅ Express frontend (3000) running"
else
    echo "   ⏳ Express frontend (3000) - not running (start it separately)"
fi

echo ""
echo "2️⃣  Creating test workspace config..."

# Create test data
mkdir -p data

cat > data/solutions.json << 'EOF'
{
  "solutions": [
    {
      "id": "autonomous-customer-data-load",
      "name": "Autonomous Customer Data Load",
      "description": "Autonomous solution to onboard Customer data into Databricks platform. This solution invokes agents to profile the data, run data quality checks, apply data classification tags and loads the data into the platform.",
      "workspaceId": "default-workspace",
      "steps": [
        {
          "id": "profiler-step",
          "name": "Profiler",
          "endpointName": "mit_structured_data_profiler_endpoint",
          "description": "Profile customer CSV structure and data quality",
          "inputMapping": "messages",
          "order": 0
        },
        {
          "id": "quality-step",
          "name": "Data Quality Check",
          "endpointName": "mit_data_quality_agent_endpoint",
          "description": "Run quality checks on customer data",
          "inputMapping": "messages",
          "order": 1
        },
        {
          "id": "autoloader-step",
          "name": "Auto Loader",
          "endpointName": "mit_autoloader_agent_endpoint",
          "description": "Load customer data via Auto Loader",
          "inputMapping": "messages",
          "order": 2
        },
        {
          "id": "classifier-step",
          "name": "Classifier",
          "endpointName": "mit_data_classifier_endpoint",
          "description": "Classify sensitive fields (PII)",
          "inputMapping": "messages",
          "order": 3
        }
      ],
      "createdAt": "2026-02-23T00:00:00.000Z",
      "updatedAt": "2026-02-23T00:00:00.000Z",
      "status": "active",
      "lastRun": null
    }
  ],
  "workspaces": [
    {
      "id": "default-workspace",
      "name": "MIT Dev Workspace",
      "environment": "dev",
      "workspaceUrl": "https://adb-1377606806062971.11.azuredatabricks.net",
      "token": "dapi_pending_access"
    }
  ],
  "databricksConfig": {
    "workspaceUrl": "https://adb-1377606806062971.11.azuredatabricks.net",
    "token": "dapi_pending_access"
  }
}
EOF

echo "   ✅ Created data/solutions.json with test config"

echo ""
echo "3️⃣  Current setup status:"
echo ""
echo "   Express API Routes:"
echo "     GET  /api/workspaces          - List workspaces"
echo "     POST /api/config              - Save Databricks config (when ready)"
echo "     GET  /api/endpoints           - List endpoints"
echo "     POST /api/solutions           - Create solution"
echo "     POST /api/solutions/:id/execute - Run pipeline"
echo ""
echo "   Python Service (agents-db):"
echo "     http://localhost:8001/health"
echo "     http://localhost:8001/orchestration/start"
echo "     http://localhost:8001/interview/start"
echo ""

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:3000 in browser"
echo "2. Configure workspace + endpoints when you get Databricks access"
echo "3. Click 'Execute Pipeline' to test"
echo ""
