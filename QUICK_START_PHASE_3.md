# Quick Start: Phase 3 (Databricks Integration & Deployment)

## Prerequisites
- Python service running (Phase 2) ✅
- Express frontend running ✅
- **Databricks workspace** with credentials

## Get Databricks Credentials (5 minutes)

### 1. Workspace URL
```
Go to your Databricks workspace
Copy from browser: https://adb-XXXXXXXXXXXXX.azuredatabricks.net
```

### 2. Personal Access Token
```
1. Click your profile (top right)
2. Select "User Settings"
3. Go to "Developer" → "Personal access tokens"
4. Click "Generate new token"
5. Copy the token (keep it secret!)
```

### 3. Workspace ID
```
1. Go to "Admin Settings" → "Workspace"
2. Copy the "Workspace ID" (numeric)
3. OR extract from URL: adb-1234567890123456.azuredatabricks.net → 1234567890123456
```

## Configure Phase 3

Edit `orchestration/.env`:

```bash
# Replace with your actual credentials
DATABRICKS_HOST=https://adb-1234567890123456.azuredatabricks.net
DATABRICKS_TOKEN=dapi1234567890abcdefghijklmnopqrst
DATABRICKS_WORKSPACE_ID=1234567890123456
```

**⚠️ NEVER commit this file to git (it has secrets)**

## Restart Services

### Terminal 1: Python Service
```bash
cd /home/appadmin/projects/Ram_Projects/agents-db
source venv/bin/activate
python orchestration/server.py
# Should show: ✅ Databricks clients initialized successfully
```

### Terminal 2: Express Frontend
```bash
cd /home/appadmin/projects/Ram_Projects/agents-db
npm start
```

## Test Databricks Integration

### Test 1: Connectivity Check
```bash
curl http://localhost:8001/databricks/status

# Success response:
{
  "status": "connected",
  "configured": true,
  "host": "https://adb-...",
  "workspace_id": "...",
  "endpoints_available": 3,
  "message": "Databricks connected successfully"
}

# If not configured:
{
  "status": "not_configured",
  "message": "Databricks credentials not set",
  "configured": false
}
```

### Test 2: List Your Tables
```bash
curl "http://localhost:8001/databricks/tables?catalog=main&schema=default"

# You'll see your actual tables!
{
  "catalog": "main",
  "schema": "default",
  "tables": [
    {
      "name": "your_table_1",
      "type": "MANAGED",
      "created_at": 1708600000000
    },
    ...
  ],
  "total": 5
}
```

### Test 3: List Serving Endpoints
```bash
curl http://localhost:8001/databricks/endpoints

# See all your deployed endpoints:
{
  "endpoints": [
    {
      "name": "your-model-endpoint",
      "state": "READY",
      "created_at": 1708500000000
    }
  ],
  "total": 2
}
```

### Test 4: Complete Workflow (with Deployment)
```bash
# 1. Start workflow
curl -X POST http://localhost:8001/orchestration/start \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","query":"I need to deploy a data profiling job to Databricks"}'

# Save the workflow_id from response

# 2. Get status (SQL agent queries your Databricks workspace)
curl http://localhost:8001/orchestration/{workflow_id}

# 3. Approve deployment
curl -X POST http://localhost:8001/orchestration/{workflow_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"workflow_id":"{workflow_id}","status":"approve"}'

# 4. Check deployment status
curl http://localhost:8001/deployment/status/{workflow_id}

# You'll see:
{
  "workflow_id": "...",
  "deployment_status": "success",
  "actions": [
    {
      "type": "create_job",
      "name": "orchestration-job-abc123",
      "job_id": "123456789",
      "status": "created"
    }
  ]
}
```

## What Happens in Phase 3

### When Workflow Starts
```
1. Supervisor analyzes your query (Gemini)
2. Router breaks it down (Gemini)
3. RAG agent finds patterns (Gemini)
4. SQL agent QUERIES YOUR DATABRICKS WORKSPACE ✨
   - Finds your tables
   - Lists your endpoints
   - Gets metadata
5. Solution builder designs solution (Gemini)
6. Synthesizer combines everything (Gemini)
7. Human approves
8. Deployer creates job IN YOUR WORKSPACE ✨
```

### After Approval
Check your Databricks workspace:
```
1. Go to "Workflows" → "Jobs"
2. Look for job "orchestration-job-xxx"
3. Should be in CREATED state
4. Can run it immediately or schedule it
```

## Example: Real Workflow

### You Ask:
```
"Design a solution to profile all customer data in our Databricks workspace"
```

### System Does:
```
1. Gemini analyzes the request
2. Routes to RAG + SQL agents
3. SQL agent connects to YOUR DATABRICKS
4. Lists tables: ["customers", "orders", "transactions"]
5. Lists endpoints: ["analytics-model", "ml-model"]
6. RAG finds best practices for data profiling
7. Solution builder recommends:
   - Multi-agent system with:
     - Schema analyzer
     - Quality checker
     - Data profiler
   - Deploy as Databricks job
8. Deployer creates job in YOUR workspace
```

### You See:
```
✅ Tables found: 3
✅ Endpoints found: 2
✅ Recommended architecture: Profiling agents
✅ Job created: orchestration-job-abc123
✅ Ready to execute in Databricks
```

## Troubleshooting

### "Databricks not configured"
```
1. Check .env file exists
2. Verify DATABRICKS_HOST and DATABRICKS_TOKEN are set
3. Check values don't have spaces or quotes
4. Restart Python service
```

### "Connection refused"
```
1. Verify workspace URL is correct
2. Check PAT token is valid (not expired)
3. Check workspace is not in maintenance
4. Try: curl https://your-workspace-url/api/2.1/serving-endpoints
```

### "Invalid workspace ID"
```
1. Get from Databricks: Admin → Workspace → ID
2. Should be just numbers: "1234567890123456"
3. NOT the full URL
4. Update .env and restart
```

### Service shows "simulated" mode
```
This means:
- Service is running OK
- Databricks is not configured
- Will show simulated results
- Jobs won't actually be created
- Fix by adding credentials to .env
```

## Understanding the Service

### Without Databricks Creds
```
- All features work
- Returns simulated/default results
- Gemini still generates intelligent responses
- Deployment shows "simulated" status
```

### With Databricks Creds
```
- Same features, but with REAL DATA
- SQL agent queries your workspace
- Deployer creates REAL jobs
- Full production capability
```

## Production Checklist

- [ ] Databricks credentials added to .env
- [ ] `curl http://localhost:8001/databricks/status` shows "connected"
- [ ] Can list tables: `curl http://localhost:8001/databricks/tables`
- [ ] Can list endpoints: `curl http://localhost:8001/databricks/endpoints`
- [ ] Test workflow completes with "success" status
- [ ] Job appears in Databricks workspace
- [ ] Ready to handle real requests

## Next: Deploy Your Solution

After Phase 3 is working:

### Option 1: Run Workflows
```bash
# Go to your Databricks workspace
# Find the job created by orchestration
# Click "Run now"
# Monitor execution
```

### Option 2: Use Express UI
```
1. Go to http://localhost:3000
2. Use "Solution Designer" or "Interview"
3. Get recommendations
4. Approve
5. Watch job create in Databricks
```

### Option 3: API-Driven
```bash
# Automate workflow creation
# Build custom UI
# Integrate with other systems
```

## Architecture Summary

```
Express Frontend (3000)
         ↓
FastAPI Service (8001)
         ↓
    LangGraph + Gemini
         ↓
    SQL + Deployer Agents ← Phase 3!
         ↓
    DATABRICKS API ← Phase 3!
         ↓
Your Databricks Workspace ← REAL DEPLOYMENT!
```

---

**Phase 3 is ready!** 🚀

With Databricks credentials configured, your orchestration service can now:
- ✅ Query your real workspace metadata
- ✅ List your actual tables and endpoints
- ✅ Deploy jobs to your workspace
- ✅ Handle production workflows

Test it, then deploy with confidence!
