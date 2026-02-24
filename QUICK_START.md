# Agent Orchestration Platform - Quick Start Guide

## 📋 Overview

The Agent Orchestration Platform is a multi-agent data pipeline system that:
1. **Profiles** data (DataScout Agent)
2. **Validates** data quality (DataGuard Agent)
3. **Classifies** sensitivity and PII (ClassifyGuard Agent)
4. **Generates** Auto Loader pipelines (AutoLoad Agent)

It consists of:
- **Express Frontend** (port 3000) - Web UI and API proxy
- **Python Orchestration Service** (port 8001) - LangGraph workflows
- **Databricks Workspace** - Serving endpoints for agents

---

## 🚀 Starting the Services

### Option 1: Use Startup Script (Recommended)

```bash
cd /home/appadmin/projects/Ram_Projects/agents-db
./START_SERVICES.sh
```

This will:
- ✅ Load environment variables from `.env`
- ✅ Start Python Orchestration Service on port 8001
- ✅ Start Express Frontend on port 3000
- ✅ Verify both services are running
- ✅ Display access points and logs

### Option 2: Manual Start

```bash
# Terminal 1: Python Orchestration Service
cd /home/appadmin/projects/Ram_Projects/agents-db
source venv/bin/activate
python orchestration/server.py

# Terminal 2: Express Frontend
cd /home/appadmin/projects/Ram_Projects/agents-db
npm start
```

---

## 📍 Access Points

After starting services:

| Service | URL | Purpose |
|---------|-----|---------|
| **Web UI** | http://10.100.15.44:3000 | Frontend dashboard |
| **Settings** | http://10.100.15.44:3000/settings | Configure workspaces & solutions |
| **API** | http://10.100.15.44:3000/api | REST API for frontend |
| **Orchestration** | http://10.100.15.44:8001 | Python service (direct access) |
| **Databricks** | https://adb-1377606806062971.11.azuredatabricks.net | Workspace with agents |

---

## 🔧 Configuration

### Environment Variables (.env)

Located in project root:
```
DATABRICKS_HOST=https://adb-1377606806062971.11.azuredatabricks.net
DATABRICKS_TOKEN=dapia0b0cc277253ec27b9dc25426478699d-3
DATABRICKS_WORKSPACE_ID=1377606806062971
PORT=3000
```

### Orchestration Config (orchestration/.env)

```
DATABRICKS_HOST=https://adb-1377606806062971.11.azuredatabricks.net
DATABRICKS_TOKEN=dapia0b0cc277253ec27b9dc25426478699d-3
DATABRICKS_WORKSPACE_ID=1377606806062971
ORCHESTRATION_PORT=8001
```

---

## 🧪 Testing the API

### 1. Check Databricks Connection

```bash
curl http://localhost:3000/api/databricks/status
```

Expected response:
```json
{
  "status": "connected",
  "configured": true,
  "host": "https://adb-1377606806062971.11.azuredatabricks.net",
  "message": "Databricks connected successfully"
}
```

### 2. Start Interview Flow

```bash
curl -X POST http://localhost:3000/api/interview/start \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user123"}'
```

Expected response:
```json
{
  "interview_id": "uuid-here",
  "status": "question",
  "question": "What business problem are you trying to solve with agent orchestration?",
  "phase": "problem"
}
```

### 3. Profile Customer Data

```bash
curl -X POST http://localhost:3000/api/orchestration/profile \
  -H "Content-Type: application/json" \
  -d '{
    "data": "customer_id,name,email\nC001,John,john@example.com\nC002,Jane,jane@example.com"
  }'
```

This will call the profiler agent once it becomes available.

---

## 📊 Monitoring

### View Service Logs

```bash
# Express Frontend logs
tail -f /tmp/express.log

# Python Orchestration logs
tail -f /tmp/orchestration.log
```

### Check Running Processes

```bash
ps aux | grep -E "node|python.*server" | grep -v grep
```

### Verify Port Bindings

```bash
netstat -tuln | grep -E "3000|8001"
```

---

## 🛑 Stopping Services

```bash
./STOP_SERVICES.sh
```

Or manually:
```bash
fuser -k 3000/tcp  # Kill Express
fuser -k 8001/tcp  # Kill Python Orchestration
```

---

## 📦 API Endpoints

### Express Frontend (3000)

```
GET  /api/workspaces              - List configured workspaces
POST /api/workspaces              - Create workspace
GET  /api/endpoints               - List serving endpoints
GET  /api/solutions               - List solutions
POST /api/solutions               - Create solution
POST /api/solutions/:id/execute   - Run workflow

# Orchestration Agents
POST /api/orchestration/profile   - Profile data
POST /api/orchestration/quality   - Validate quality
POST /api/orchestration/classify  - Classify sensitivity
POST /api/orchestration/autoload  - Generate Auto Loader

# Interview Flow
POST /api/interview/start         - Start interview
POST /api/interview/:id/answer    - Submit answer

# Databricks
GET  /api/databricks/status       - Check connection
```

### Python Orchestration (8001)

```
POST /orchestration/start                  - Start workflow
GET  /orchestration/{workflow_id}          - Get workflow status
POST /orchestration/{workflow_id}/approve  - Human approval
POST /interview/start                      - Start interview
GET  /interview/{interview_id}             - Get interview state
POST /interview/{interview_id}/answer      - Submit answer
GET  /databricks/status                    - Check Databricks
```

---

## 🔐 Security Notes

- ⚠️ **NEVER** commit `.env` files to version control
- ✅ `.env` is protected by `.gitignore`
- 🔒 Databricks token is environment-variable based
- 🔐 All API communication is HTTPS with Databricks

---

## 🐛 Troubleshooting

### Port Already in Use

```bash
# Find and kill process on port
lsof -i :3000
kill -9 <PID>
```

### Services Won't Start

Check logs:
```bash
tail -50 /tmp/express.log
tail -50 /tmp/orchestration.log
```

### Databricks Connection Failed

Verify credentials:
```bash
curl -s -H "Authorization: Bearer dapia0b0cc277253ec27b9dc25426478699d-3" \
  https://adb-1377606806062971.11.azuredatabricks.net/api/2.0/serving-endpoints
```

### Python Service Not Responding

Ensure Python venv is activated:
```bash
source venv/bin/activate
python -c "import fastapi; print('✓ FastAPI installed')"
```

---

## 📞 Support

For issues:
1. Check `/tmp/express.log` and `/tmp/orchestration.log`
2. Verify `.env` file has correct credentials
3. Test Databricks connectivity directly
4. Check port availability (`netstat` or `lsof`)

---

## ✅ System Status Checklist

- [ ] Express running on port 3000
- [ ] Python Orchestration running on port 8001
- [ ] `.env` file configured with Databricks token
- [ ] Databricks workspace accessible
- [ ] API endpoints responding (200 status)
- [ ] Interview flow working
- [ ] Settings UI accessible at `/settings`

---

**Last Updated:** 2026-02-24
**Version:** 2.0
**Platform:** Agent Orchestration with LangGraph
