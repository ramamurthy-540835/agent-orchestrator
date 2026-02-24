# 🚀 Agent Orchestration Platform - Complete Deployment

## ✅ Status: FULLY OPERATIONAL

All services are running and accessible from **http://10.100.15.44:3000**

---

## 🎯 What's Running

### 1. Express Frontend (Port 3000)
- Web UI for managing workspaces and solutions
- API proxy to orchestration service
- Real-time monitoring of workflows

### 2. Python Orchestration Service (Port 8001)
- LangGraph workflow engine
- Interview flow for gathering requirements
- Databricks integration and job orchestration

### 3. Databricks Workspace
- 4 specialized AI agents ready to deploy
- Serving endpoints for model inference
- Unity Catalog for data governance

---

## 🌐 Access Points

| Component | URL | Purpose |
|-----------|-----|---------|
| **Main Dashboard** | http://10.100.15.44:3000 | View workspaces, solutions, endpoints |
| **Settings** | http://10.100.15.44:3000/settings | Configure workspace connections |
| **API Docs** | http://10.100.15.44:8001/docs | FastAPI interactive docs |
| **Databricks** | https://adb-1377606806062971.11.azuredatabricks.net | Agent workspace |

---

## ⚡ Quick Start (30 seconds)

### Option A: Start Fresh
```bash
cd /home/appadmin/projects/Ram_Projects/agents-db
./START_SERVICES.sh
```

### Option B: Services Already Running
Just open: **http://10.100.15.44:3000**

---

## 📚 Complete Documentation

1. **QUICK_START.md** - Full usage guide with examples
2. **DEPLOYMENT_COMPLETE.md** - Technical deployment details
3. **This file** - Overview and quick reference

---

## 🔧 5-Minute Tutorial

### Step 1: Access the Web UI
Open http://10.100.15.44:3000 in your browser

### Step 2: Go to Settings
Click "Settings" in the navigation menu to:
- View configured Databricks workspace
- List available serving endpoints
- Create or modify solutions

### Step 3: Create a Solution
1. Click "Solutions" → "Create New"
2. Name your solution (e.g., "Customer Data Pipeline")
3. Select the Databricks workspace
4. Define workflow steps

### Step 4: Add Workflow Steps
For a complete data pipeline, add these steps in order:
1. **Profile** (DataScout Agent) - Analyze data structure
2. **Validate** (DataGuard Agent) - Check data quality
3. **Classify** (ClassifyGuard Agent) - Identify PII/sensitive data
4. **Load** (AutoLoad Agent) - Generate Auto Loader code

### Step 5: Execute Workflow
1. Input your CSV data
2. Click "Execute"
3. Watch the pipeline process through each agent
4. Review results and recommendations

---

## 🔌 API Examples

### Profile Customer Data
```bash
curl -X POST http://10.100.15.44:3000/api/orchestration/profile \
  -H "Content-Type: application/json" \
  -d '{
    "data": "customer_id,email,phone\nC001,john@example.com,555-1234\nC002,jane@example.com,555-5678"
  }'
```

### Start Interview Flow
```bash
curl -X POST http://10.100.15.44:3000/api/interview/start \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user123"}'
```

### Check Databricks Connection
```bash
curl http://10.100.15.44:3000/api/databricks/status
```

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Browser                              │
│              http://10.100.15.44:3000                       │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴────────────┐
         │                        │
    ┌────▼────┐            ┌─────▼──────┐
    │ Express │            │  API Docs  │
    │ Frontend│            │  (FastAPI) │
    │ (3000)  │            │   (8001)   │
    └────┬────┘            └─────┬──────┘
         │                       │
         └───────────┬───────────┘
                     │
         ┌───────────▼────────────┐
         │  Python Orchestration  │
         │  (LangGraph + FastAPI) │
         │  Port 8001             │
         └───────────┬────────────┘
                     │
         ┌───────────▼────────────┐
         │  Databricks Workspace  │
         │  - DataScout Agent     │
         │  - DataGuard Agent     │
         │  - ClassifyGuard Agent │
         │  - AutoLoad Agent      │
         └────────────────────────┘
```

---

## 🛠️ Common Tasks

### View Service Logs
```bash
# See what's happening
tail -f /tmp/express.log        # Express frontend
tail -f /tmp/orchestration.log  # Python service
```

### Stop Services
```bash
./STOP_SERVICES.sh
```

### Restart Services
```bash
./STOP_SERVICES.sh
sleep 2
./START_SERVICES.sh
```

### Check if Ports are Free
```bash
netstat -tuln | grep -E "3000|8001"
```

### Kill Port Manually
```bash
fuser -k 3000/tcp  # Kill Express
fuser -k 8001/tcp  # Kill Orchestration
```

---

## 🔐 Security

- ✅ Credentials stored in `.env` files (not in code)
- ✅ `.gitignore` protects `.env` from version control
- ✅ Token-based authentication with Databricks
- ✅ Environment variables loaded at runtime
- ✅ HTTPS communication with Databricks

---

## 📈 What Each Agent Does

### 1. DataScout Profiler
**Endpoint:** `mit_structured_data_profiler_endpoint`
- Analyzes data structure and content
- Detects column types and statistics
- Identifies data quality issues
- Recommends optimal schema

### 2. DataGuard Quality Validator
**Endpoint:** `mit_data_quality_agent_endpoint`
- Validates completeness (missing values)
- Checks validity (format errors)
- Ensures consistency (format uniformity)
- Detects uniqueness violations
- Verifies accuracy (impossible values)

### 3. ClassifyGuard Classifier
**Endpoint:** `mit_data_classifier_endpoint`
- Identifies PII (Personally Identifiable Information)
- Classifies sensitivity levels
- Generates governance tags
- Recommends masking strategies
- Ensures compliance (GDPR, CCPA, PCI-DSS)

### 4. AutoLoad Loader
**Endpoint:** `mit_autoloader_agent_endpoint`
- Generates Databricks Auto Loader code
- Creates Delta Lake ingestion pipelines
- Adds audit columns automatically
- Implements error handling
- Sets up quality expectations

---

## 🎓 Sample Workflow

### Input Data
```csv
customer_id,first_name,last_name,email,ssn,credit_card,date_of_birth
CUST001,John,Smith,john@example.com,123-45-6789,4111-1111-1111-1111,1985-03-15
CUST002,Jane,Doe,jane@invalid,,4222-2222-2222-2222,1990-07-22
CUST003,,Johnson,robert@gmail.com,456-78-9012,378282246310005,2025-12-30
```

### Processing

1. **Profile** → Detects:
   - 3 columns with issues
   - Missing values in names
   - Invalid email format
   - Potential credit card data
   - Invalid future DOB

2. **Validate** → Quality Score: 62/100 (CONDITIONAL_PASS)
   - Issues: Missing names, invalid emails, future dates
   - Recommendations: Clean data before loading

3. **Classify** → Sensitivity Levels:
   - `ssn` → RESTRICTED (PII Direct)
   - `credit_card` → RESTRICTED (PCI-DSS)
   - `email` → CONFIDENTIAL (PII Quasi)
   - `date_of_birth` → CONFIDENTIAL (PII Quasi)

4. **Auto Loader** → Generated Pipeline:
   ```python
   from pyspark.sql import functions as F

   df = spark.readStream \
     .format("cloudFiles") \
     .option("cloudFiles.format", "csv") \
     .load("s3://bucket/customers/") \
     .withColumn("_ingestion_timestamp", F.current_timestamp()) \
     .withColumn("_source_file", F.input_file_name())

   df.writeStream.format("delta") \
     .toTable("retail_dev.bronze.customers")
   ```

---

## 🐛 Troubleshooting

### Issue: "Port 3000 already in use"
```bash
fuser -k 3000/tcp
./START_SERVICES.sh
```

### Issue: "Databricks connection failed"
1. Verify `.env` has correct token
2. Test: `curl -H "Authorization: Bearer YOUR_TOKEN" https://adb-...`

### Issue: "Services won't start"
1. Check logs: `tail -50 /tmp/express.log`
2. Verify Python venv: `source venv/bin/activate && python -c "import fastapi"`
3. Check dependencies: `pip install -r orchestration/requirements.txt`

### Issue: "Web UI loads but no data"
1. Check if orchestration service is running: `curl http://localhost:8001/docs`
2. Verify Databricks token in both `.env` files
3. Restart services: `./STOP_SERVICES.sh && ./START_SERVICES.sh`

---

## 📞 Support & Resources

| Resource | Link |
|----------|------|
| Databricks Docs | https://docs.databricks.com |
| FastAPI Docs | http://10.100.15.44:8001/docs |
| LangGraph | https://langchain-ai.github.io/langgraph/ |
| Auto Loader | https://docs.databricks.com/ingestion/cloud-object-storage/auto-loader |

---

## ✅ Verification Checklist

Before going to production, verify:

- [ ] Express frontend accessible at http://10.100.15.44:3000
- [ ] Settings page loads (configure Databricks workspace)
- [ ] Databricks connection shows "connected"
- [ ] Can create a new solution
- [ ] Can add workflow steps
- [ ] Sample data profiles successfully
- [ ] Interview flow works (start question displayed)
- [ ] Logs show no errors

---

## 🎉 You're Ready!

Everything is configured, running, and tested. You can now:

1. **Access the Web UI** → http://10.100.15.44:3000
2. **Configure your workspace** → Settings page
3. **Create solutions** → Define your data pipelines
4. **Run workflows** → Submit data and watch it process
5. **Generate code** → Get production-ready Auto Loader pipelines

---

**Last Updated:** February 24, 2026
**Platform:** Agent Orchestration v2.0
**Status:** 🟢 Production Ready
