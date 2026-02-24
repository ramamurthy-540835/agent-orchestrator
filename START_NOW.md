# 🚀 Start Now - 3 Simple Commands

Your system is **ready to use**. Just start the two services:

---

## Terminal 1: Start Python Service

```bash
cd ~/projects/Ram_Projects/agents-db
source venv/bin/activate
python orchestration/server.py
```

**Wait for:**
```
INFO:     Uvicorn running on http://0.0.0.0:8001
INFO:     Application startup complete
```

---

## Terminal 2: Start Express Frontend

```bash
cd ~/projects/Ram_Projects/agents-db
npm start
```

**Wait for:**
```
Agent Orchestration Platform running at http://localhost:3000
```

---

## Terminal 3: Open in Browser

```
http://localhost:3000
```

You should see:
- ✅ Mastech Agent Orchestration Platform
- ✅ Your "Autonomous Customer Data Load" solution
- ✅ 4 agent steps configured (Profiler, Quality Check, Auto Loader, Classifier)

---

## Status

### What's Working Now ✅
- Express frontend (port 3000)
- Python orchestration service (port 8001)
- Gemini AI integration
- Interview flow
- Workflow design

### What Needs Databricks Access 🔄
- Actual endpoint execution
- Workspace queries

### What to Do When You Get Databricks Access:
1. Contact your admin to enable login
2. Go to Databricks workspace
3. Get your Personal Access Token (User Settings → Developer → Personal access tokens)
4. Come back and add token to: `orchestration/.env`
   ```
   DATABRICKS_HOST=https://adb-1377606806062971.11.azuredatabricks.net
   DATABRICKS_TOKEN=dapi...
   DATABRICKS_WORKSPACE_ID=1377606806062971
   ```
5. Then start endpoints:
   ```bash
   python orchestration/start_endpoints.py
   ```
6. Your pipeline will execute

---

## Quick Tests (No Databricks Needed)

### Test 1: Health Check
```bash
curl http://localhost:8001/health
```

### Test 2: Design a Solution with AI
```bash
curl -X POST http://localhost:8001/orchestration/start \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","query":"Design an agent pipeline to load customer data"}'
```

### Test 3: Interactive Interview
```bash
curl -X POST http://localhost:8001/interview/start \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test"}'
```

Gemini will ask you questions about your needs!

---

## Summary

✅ **Everything is set up and running**
✅ **Gemini AI is working**
✅ **Your pipeline is configured**
⏳ **Just need Databricks access to execute endpoints**

**Start the services and visit http://localhost:3000 now!**
