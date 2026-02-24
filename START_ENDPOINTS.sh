#!/bin/bash

# Start All Databricks Serving Endpoints
# Script to start all stopped endpoints in your MIT Dev workspace

# Set your Databricks credentials
DATABRICKS_HOST="https://adb-1377606806062971.11.azuredatabricks.net"
DATABRICKS_TOKEN="dapi..."  # Replace with your PAT

# Endpoints to start
ENDPOINTS=(
  "agent-migrator_infapc_to_pyspark"
  "mit_autoloader_agent_endpoint"
  "mit_autoloader_agent_endpoint_qa"
  "mit_data_classifier_endpoint"
  "mit_data_classifier_endpoint_qa"
  "mit_data_modelling_endpoint"
  "mit_data_quality_agent_endpoint"
  "mit_data_quality_agent_endpoint_qa"
  "mit_finops_dashboard_agent_endpoint"
  "mit_structured_data_profiler_endpoint"
  "mit_uc_access_control_orchestrator_endpoint"
  "mit_unstructured_data_profiler_endpoint"
  "mit_user_onboarding_agent_endpoint"
  "mit_user_onboarding_agent_endpoint_qa"
  "rag_demo"
)

echo "Starting Databricks Serving Endpoints..."
echo "Workspace: $DATABRICKS_HOST"
echo "Endpoints to start: ${#ENDPOINTS[@]}"
echo ""

for endpoint in "${ENDPOINTS[@]}"; do
  echo "Starting: $endpoint"

  curl -X POST \
    -H "Authorization: Bearer $DATABRICKS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"served_models":[]}' \
    "$DATABRICKS_HOST/api/2.0/serving-endpoints/$endpoint/start"

  echo " ✓ Command sent"
done

echo ""
echo "All endpoints start commands sent!"
echo "Endpoints will take 2-5 minutes to fully start."
echo ""
echo "To check status, run:"
echo "curl -H 'Authorization: Bearer $DATABRICKS_TOKEN' $DATABRICKS_HOST/api/2.0/serving-endpoints | jq '.endpoints[] | {name, state}'"
