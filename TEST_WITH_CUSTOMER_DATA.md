# Working Code: Test agents-db with Your Customer Data

Your agents-db orchestration service is **RUNNING AND HEALTHY** ✅

## Test 1: Health Check (Verify Service Running)

```bash
curl -s http://localhost:8001/health | jq .
```

**Expected Output:**
```json
{
  "status": "healthy",
  "service": "Agent Orchestration Service",
  "version": "2.0.0",
  "phase": "Phase 3 (Databricks Integration)",
  "databricks": "configured"
}
```

---

## Test 2: Design a Solution for Your Customer Data Pipeline

**Your Use Case:**
```
Load customer CSV data into Databricks
Profile the data
Run quality checks
Classify sensitive fields (SSN, credit cards)
Load via Auto Loader
```

**Working Code:**

```bash
curl -X POST http://localhost:8001/orchestration/start \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "mastech-team",
    "query": "Design an agent pipeline to load customer data into Databricks. The data has quality issues (missing fields, invalid emails, future dates, negative loyalty points, PII like SSN and credit cards). I need agents to: 1) Profile the CSV structure and data quality, 2) Run data quality checks, 3) Classify sensitive fields, 4) Load via Auto Loader to retail_dev.bronze.customers"
  }'
```

**What Happens:**
1. ✅ Supervisor analyzes your request
2. ✅ Router decomposes into sub-tasks
3. ✅ RAG searches for best practices
4. ✅ Solution Builder designs agent pipeline
5. ✅ System returns architecture recommendation

**Expected Response:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "planning",
  "current_agent": "supervisor",
  "created_at": "2026-02-23T10:00:00.000000",
  "last_updated": "2026-02-23T10:00:00.000000"
}
```

---

## Test 3: Get the Recommendation

Save the `workflow_id` from above, then:

```bash
curl http://localhost:8001/orchestration/{workflow_id}
```

Replace `{workflow_id}` with your actual ID from Test 2.

**You'll see:**
- ✅ Supervisor analyzed your pipeline
- ✅ Router identified 4 agents needed
- ✅ RAG found patterns for data quality
- ✅ Solution Builder recommends architecture

---

## Test 4: Interview-Based Design (Human-in-the-Loop)

Instead of manual queries, let **Gemini interview you** to understand your needs:

```bash
# Start interview
curl -X POST http://localhost:8001/interview/start \
  -H "Content-Type: application/json" \
  -d '{"user_id":"mastech-team"}'
```

**Gemini will ask:** "What business problem are you trying to solve?"

**You respond:**
```bash
INTERVIEW_ID="copy-interview-id-from-above"

curl -X POST http://localhost:8001/interview/$INTERVIEW_ID/answer \
  -H "Content-Type: application/json" \
  -d '{"interview_id":"'$INTERVIEW_ID'","answer":"We need to automate loading customer data into Databricks with quality checks and PII classification"}'
```

**Gemini generates next question automatically** → You answer → Process repeats

After ~5-7 questions, you get **personalized architecture recommendation**.

---

## Test 5: Check Databricks Workspace Integration

```bash
curl http://localhost:8001/databricks/status
```

**Shows:**
- ✅ Workspace connected
- ✅ Tables in Unity Catalog
- ✅ Available endpoints

---

## Full Integration Example (Copy-Paste Ready)

This script tests everything in sequence:

```bash
#!/bin/bash

echo "=== 1. Health Check ==="
curl -s http://localhost:8001/health | jq .

echo ""
echo "=== 2. Start Workflow for Customer Pipeline ==="
RESPONSE=$(curl -s -X POST http://localhost:8001/orchestration/start \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "mastech-team",
    "query": "Design an agent pipeline: 1) Profile customer CSV (5 rows with quality issues), 2) Run data quality checks on email/phone/DOB/loyalty_points, 3) Classify PII (SSN, credit_card_number), 4) Load to retail_dev.bronze.customers via Auto Loader. Target source: abfss://raw-data@mitgenaistorage.dfs.core.windows.net/customers/"
  }')

echo $RESPONSE | jq .

WORKFLOW_ID=$(echo $RESPONSE | grep -o '"workflow_id":"[^"]*' | cut -d'"' -f4)
echo ""
echo "Workflow ID: $WORKFLOW_ID"

echo ""
echo "=== 3. Check Workflow Status ==="
curl -s http://localhost:8001/orchestration/$WORKFLOW_ID | jq .

echo ""
echo "=== 4. Check Databricks Connection ==="
curl -s http://localhost:8001/databricks/status | jq .

echo ""
echo "=== 5. List Databricks Tables ==="
curl -s http://localhost:8001/databricks/tables | jq '.tables[0:3]'

echo ""
echo "✅ All tests complete!"
```

**Save as:** `test_customer_pipeline.sh`

**Run:**
```bash
chmod +x test_customer_pipeline.sh
./test_customer_pipeline.sh
```

---

## What agents-db Does vs Your Mastech Platform

| Feature | Mastech (port 3000) | agents-db (port 8001) |
|---------|-------|---------|
| **Pipeline** | Sequential (step 1→2→3→4) | Graph-based (LangGraph) |
| **Agent Design** | Manual config | **AI-designed (Gemini)** ✨ |
| **Human Input** | None | **Adaptive interview** ✨ |
| **Error Handling** | Endpoint errors | Graceful fallbacks |
| **Intelligence** | Fixed logic | **AI reasoning** ✨ |

---

## How to Use agents-db to Design Your Mastech Pipelines

### Current Flow (Mastech):
```
You → Manually create pipeline → Configure 4 endpoints → Execute
```

### With agents-db (New):
```
You → Interview (Gemini asks questions) →
Gemini designs optimal pipeline →
agents-db recommends agent sequence & configuration →
You approve → Deploy to Databricks
```

---

## Next: Integrate with Express UI

Your Express app (port 3000) can call agents-db (port 8001):

```javascript
// In your Express route (server.js or routes/)

async function designPipeline(req, res) {
  const { userQuery } = req.body;

  // Call agents-db orchestration
  const response = await fetch('http://localhost:8001/orchestration/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: req.user?.id || 'guest',
      query: userQuery
    })
  });

  const { workflow_id, status } = await response.json();
  res.json({ workflow_id, status });
}
```

---

## Your Customer Data (Ready to Test)

Save this as `test_data.csv`:

```csv
customer_id,first_name,last_name,email,phone,date_of_birth,loyalty_points,is_active,ssn,credit_card_number
CUST001,John,Smith,john.smith@gmail.com,+1-555-0101,1985-03-15,2500,true,123-45-6789,4111111111111111
CUST002,María,García,maria@invalid,,1990-07-22,-500,yes,,
CUST003, Wei ,Zhang,,+86-10-12345678,2028-11-03,3200,TRUE,,
CUST004,Priya,Sharma,priya@.com,555-0104,1975/12/30,4100,1,456-78-9012,4222222222222
CUST005,,Johnson,robert@gmail.com,+1-555-0105,1992-06-25,0,false,,378282246310005
```

**Quality Issues (for agents to catch):**
- ✅ CUST002: Invalid email (maria@invalid), missing phone, negative loyalty_points
- ✅ CUST003: Leading whitespace in name, missing email, future DOB (2028)
- ✅ CUST004: Invalid email (priya@.com), mixed date format (1975/12/30), contains SSN & CC
- ✅ CUST005: Missing first_name, contains CC number

**agents-db will help design agents that:**
1. Detect these issues
2. Classify SSN & CC as PII
3. Build data quality checks
4. Create Auto Loader config

---

## Run Now

**In Terminal 3:**
```bash
cd /home/appadmin/projects/Ram_Projects/agents-db

# Quick test
curl http://localhost:8001/health

# Full test with customer pipeline
curl -X POST http://localhost:8001/orchestration/start \
  -H "Content-Type: application/json" \
  -d '{"user_id":"mastech","query":"Design an agent to profile and quality-check customer CSV with PII (SSN, credit cards) and load to Databricks"}'
```

---

## Success Criteria ✅

If you see:
- ✅ Health check returns `"status": "healthy"`
- ✅ Workflow returns `workflow_id`
- ✅ Databricks status shows connected
- ✅ Interview generates questions

**Then agents-db is fully integrated and ready to design your Mastech pipelines!** 🚀
