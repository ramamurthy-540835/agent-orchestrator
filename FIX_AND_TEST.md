# Fix & Test: Start Endpoints + Run Pipeline

## Problem
All 14 serving endpoints in your Databricks workspace are **STOPPED**.

## Solution
Use agents-db to **start them all at once** + **test your pipeline**.

---

## Step 1: Start All Endpoints (2 minutes)

### Option A: Using Python (Recommended)

```bash
cd /home/appadmin/projects/Ram_Projects/agents-db
source venv/bin/activate

# Start all endpoints
python orchestration/start_endpoints.py
```

**Expected Output:**
```
🚀 Starting all Databricks serving endpoints...
Workspace: https://adb-1377606806062971.11.azuredatabricks.net

Found 14 endpoints:

  ⏸️  STOPPED: agent-migrator_infapc_to_pyspark
  ⏸️  STOPPED: mit_autoloader_agent_endpoint
  ⏸️  STOPPED: mit_autoloader_agent_endpoint_qa
  ... (12 more)

Status: 0 running, 14 stopped

🔄 Starting 14 endpoints...
  ✓ agent-migrator_infapc_to_pyspark - start command sent
  ✓ mit_autoloader_agent_endpoint - start command sent
  ... (12 more)

⏳ Endpoints are starting (takes 2-5 minutes)...
Check Databricks workspace → Serving Endpoints for status
```

### Option B: Using Bash

```bash
# Edit START_ENDPOINTS.sh first
nano START_ENDPOINTS.sh
# Update: DATABRICKS_TOKEN="dapi..." with your actual token

chmod +x START_ENDPOINTS.sh
./START_ENDPOINTS.sh
```

---

## Step 2: Check Endpoint Status (Wait for "READY")

### While Endpoints are Starting

```bash
source venv/bin/activate

# Check status every 30 seconds
python orchestration/start_endpoints.py status
```

**Expected Output:**
```
Endpoint Status:
--------------------------------------------------
✅ agent-migrator_infapc_to_pyspark                     READY
✅ mit_autoloader_agent_endpoint                        READY
✅ mit_autoloader_agent_endpoint_qa                     READY
⏳ mit_data_classifier_endpoint                         PENDING
⏸️  mit_data_classifier_endpoint_qa                     STOPPED
... (9 more)
```

**Wait until all show ✅ READY** (usually 3-5 minutes)

---

## Step 3: Run Your Pipeline

Once endpoints are READY:

### In Mastech UI (Port 3000)
```
1. Go to http://localhost:3000
2. Click "Autonomous Customer Data Load"
3. Click "Execute Pipeline"
4. Should now return SUCCESS instead of "endpoint stopped" errors
```

### Or Test via API

```bash
curl -X POST http://localhost:3000/api/execute-workflow \
  -H "Content-Type: application/json" \
  -d '{
    "solutionId": "autonomous-customer-data-load",
    "input": "Load customer CSV with profiling, quality checks, and classification"
  }'
```

---

## Step 4: Verify Pipeline Execution

Check Mastech UI → "Execution Results"

**Expected:**
```
Step 1: Profiler
SUCCESS ✅
Endpoint: mit_structured_data_profiler_endpoint

Step 2: Data Quality Check
SUCCESS ✅
Endpoint: mit_data_quality_agent_endpoint

Step 3: Auto Loader
SUCCESS ✅
Endpoint: mit_autoloader_agent_endpoint

Step 4: Classifier
SUCCESS ✅
Endpoint: mit_data_classifier_endpoint

Final Output: { "status": "success", "records_loaded": 5 }
```

---

## Step 5: Integrate with agents-db (Optional But Recommended)

Now that endpoints are running, use **agents-db to design future pipelines**:

```bash
# Test agents-db with your customer data
curl -X POST http://localhost:8001/orchestration/start \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "mastech-team",
    "query": "Improve the customer data pipeline. Current pipeline: 1) Profile CSV (mit_structured_data_profiler_endpoint), 2) Quality checks (mit_data_quality_agent_endpoint), 3) Classification (mit_data_classifier_endpoint), 4) Auto Load (mit_autoloader_agent_endpoint). Issues: missing emails, negative loyalty points, PII not masked. Recommend enhancements."
  }' | jq .
```

**agents-db will:**
1. ✅ Analyze your current pipeline
2. ✅ Suggest improvements using Gemini AI
3. ✅ Recommend agent sequence
4. ✅ Help design new agents if needed

---

## Complete Workflow: Start to Finish

### Timeline

| Step | Command | Time | Status |
|------|---------|------|--------|
| 1 | `python orchestration/start_endpoints.py` | 10 sec | Send start commands |
| 2 | Wait & check status | 2-5 min | Endpoints boot up |
| 3 | `python orchestration/start_endpoints.py status` | 10 sec | Verify all READY |
| 4 | Run pipeline (Mastech UI) | 10 sec | Execute workflow |
| 5 | Check results | 10 sec | See SUCCESS |

**Total Time: ~6 minutes** ⏱️

---

## Troubleshooting

### Endpoints won't start
```bash
# Check Databricks credentials
cat orchestration/.env | grep DATABRICKS

# Verify connection
curl -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  https://adb-1377606806062971.11.azuredatabricks.net/api/2.0/serving-endpoints
```

### Still getting "endpoint stopped" errors
```bash
# Wait longer (endpoints take 5-10 minutes sometimes)
# Check Databricks UI → Serving Endpoints
# Look for any errors in endpoint logs
```

### Pipeline returns errors
```bash
# Check individual endpoint responses
curl -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  "https://adb-1377606806062971.11.azuredatabricks.net/api/2.0/serving-endpoints/mit_structured_data_profiler_endpoint"

# Look for "state" and "state_message"
```

---

## What Next?

After your pipeline runs successfully:

### Option 1: Keep Using Mastech UI
- Works now with all endpoints running
- Sequential pipeline execution
- Basic agent management

### Option 2: Enhance with agents-db
- Use Gemini AI to **design** pipelines
- Conduct **interviews** to understand requirements
- Get **intelligent recommendations**
- Deploy with **human-in-the-loop** approval

### Option 3: Full Integration
- Mastech UI (port 3000) calls agents-db (port 8001)
- agents-db designs pipeline → Mastech executes it
- Best of both worlds: AI-designed + Production-tested

---

## Success Checklist

- [ ] Run: `python orchestration/start_endpoints.py`
- [ ] Wait 3-5 minutes
- [ ] Check: `python orchestration/start_endpoints.py status`
- [ ] All endpoints show ✅ READY
- [ ] Go to Mastech UI → Execute Pipeline
- [ ] See all steps: SUCCESS ✅
- [ ] Final Output shows actual results

---

## One-Liner Test (After Endpoints Running)

```bash
# After all endpoints are READY, test your pipeline:
curl http://localhost:3000 | head -5  # Check Mastech is up
curl http://localhost:8001/health | jq .  # Check agents-db is up
# Then go to Mastech UI and click "Execute Pipeline"
```

---

**Ready? Start with:** `python orchestration/start_endpoints.py`

Takes **~6 minutes total** to get your pipeline working! ✅
