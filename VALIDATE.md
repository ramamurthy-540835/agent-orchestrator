# Simple Validation Steps

## Step 1: Check Python Setup (30 seconds)

```bash
cd /home/appadmin/projects/Ram_Projects/agents-db
source venv/bin/activate
python --version
# Should show: Python 3.12.x
```

✅ **Expected:** Python 3.10+

---

## Step 2: Check Dependencies (30 seconds)

```bash
pip list | grep -E "fastapi|langgraph|google-generativeai"
```

✅ **Expected Output:**
```
fastapi                            0.131.0
google-generativeai                0.8.6
langchain                          1.2.10
langgraph                          1.0.9
```

---

## Step 3: Test Python Files Compile (30 seconds)

```bash
python -m py_compile orchestration/{server,graph,agents,llm,databricks_client,interview}.py
echo "✅ All files compile"
```

✅ **Expected:** `✅ All files compile` (no errors)

---

## Step 4: Start Services (2 terminals)

### Terminal 1: Start Python Service

```bash
source venv/bin/activate
python orchestration/server.py
```

✅ **Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8001
INFO:     Application startup complete
```

### Terminal 2: Start Express Frontend

```bash
npm start
```

✅ **Expected Output:**
```
Agent Orchestration Platform running at http://localhost:3000
```

---

## Step 5: Health Check (30 seconds)

**New Terminal 3:**

```bash
curl http://localhost:8001/health
```

✅ **Expected Response:**
```json
{
  "status": "healthy",
  "service": "Agent Orchestration Service",
  "version": "2.0.0",
  "phase": "Phase 3 (Databricks Integration)",
  "databricks": "not_configured"
}
```

---

## Step 6: Test Service Info (30 seconds)

```bash
curl http://localhost:8001/info
```

✅ **Expected:** See all capabilities listed with Phase 3 features

---

## Step 7: Test Interview Start (1 minute)

```bash
curl -X POST http://localhost:8001/interview/start \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test"}'
```

✅ **Expected Response:**
```json
{
  "interview_id": "...",
  "status": "question",
  "question": "What business problem are you trying to solve...",
  "phase": "problem"
}
```

✅ **Confirms:** Phase 2 (Gemini) working

---

## Step 8: Test Workflow Start (1-2 minutes)

```bash
curl -X POST http://localhost:8001/orchestration/start \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","query":"Design an agent system"}'
```

✅ **Expected Response:**
```json
{
  "workflow_id": "...",
  "status": "planning",
  "current_agent": "supervisor",
  "created_at": "...",
  "last_updated": "..."
}
```

✅ **Confirms:** Phase 1 & 2 working

---

## Step 9: Test Databricks Status (30 seconds)

```bash
curl http://localhost:8001/databricks/status
```

✅ **Expected Response (without credentials):**
```json
{
  "status": "not_configured",
  "message": "Databricks credentials not set",
  "configured": false
}
```

✅ **Confirms:** Phase 3 ready (just needs credentials)

---

## Step 10: (Optional) Add Databricks & Test (5 minutes)

**Edit `orchestration/.env`:**

```bash
# Replace with YOUR values
DATABRICKS_HOST=https://your-workspace.azuredatabricks.net
DATABRICKS_TOKEN=your-personal-access-token
DATABRICKS_WORKSPACE_ID=your-workspace-id
```

**Restart Python service (Ctrl+C, then rerun)**

**Test connection:**

```bash
curl http://localhost:8001/databricks/status
```

✅ **Expected (with valid credentials):**
```json
{
  "status": "connected",
  "configured": true,
  "host": "https://...",
  "workspace_id": "...",
  "endpoints_available": 2,
  "message": "Databricks connected successfully"
}
```

---

## Summary Checklist

Run all steps in order. You should see ✅ at each step:

- [ ] Step 1: Python 3.10+
- [ ] Step 2: Dependencies installed
- [ ] Step 3: Python files compile
- [ ] Step 4a: Python service starts (port 8001)
- [ ] Step 4b: Express frontend starts (port 3000)
- [ ] Step 5: Health check returns healthy
- [ ] Step 6: Service info shows all capabilities
- [ ] Step 7: Interview starts with Gemini question
- [ ] Step 8: Workflow starts successfully
- [ ] Step 9: Databricks status check works
- [ ] Step 10 (Optional): Databricks connected with credentials

---

## If Something Fails

### Python service won't start
```bash
python orchestration/server.py
# Look at error message
# Check: GEMINI_API_KEY in .env
```

### Port 8001 already in use
```bash
# Find process using port 8001
lsof -i :8001
# Kill it: kill -9 <PID>
```

### Port 3000 already in use
```bash
# Find process using port 3000
lsof -i :3000
# Kill it: kill -9 <PID>
```

### Curl commands fail
```bash
# Check both services are running
curl http://localhost:8001/health
curl http://localhost:3000

# If both return data, services are fine
```

### Interview doesn't generate questions
```bash
# Check Gemini API key is set
cat orchestration/.env | grep GEMINI_API_KEY

# Check it's a valid key
# Service will fallback to default questions if invalid
```

---

## Quick Status Command

```bash
# One command to check all services
echo "=== Python Service ===" && \
curl -s http://localhost:8001/health | jq . && \
echo "=== Express Frontend ===" && \
curl -s http://localhost:3000 | head -5 && \
echo "=== Databricks ===" && \
curl -s http://localhost:8001/databricks/status | jq .
```

---

## All Tests Pass? ✅

You have a working **3-phase orchestration system**:
- ✅ **Phase 1:** FastAPI + LangGraph (foundation)
- ✅ **Phase 2:** Gemini API (intelligence)
- ✅ **Phase 3:** Databricks integration (production)

**Next:** Use it for interviews, workflows, and deployments! 🚀
