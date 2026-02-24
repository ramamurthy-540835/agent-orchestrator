# Agent Orchestration Service (LangGraph + FastAPI)

This is the Python backend service that provides multi-agent orchestration capabilities to the agents-db platform. It runs alongside your Express frontend and handles complex workflow coordination using LangGraph.

## Architecture

```
Express Frontend (Port 3000)
           ↓
    HTTP Calls
           ↓
FastAPI Orchestration Service (Port 8001)
           ↓
    LangGraph State Machine
           ↓
    Databricks Endpoints & APIs
```

## Setup

### 1. Create and Activate Virtual Environment

```bash
cd /home/appadmin/projects/Ram_Projects/agents-db
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
cd orchestration
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env with your Databricks credentials
```

### 4. Run the Service

```bash
python server.py
```

The service will start on `http://localhost:8001`

## API Endpoints

### Orchestration Endpoints

#### Start a Workflow
```
POST /orchestration/start
Content-Type: application/json

{
  "user_id": "user123",
  "query": "Design an agent system for data analysis",
  "context": {}
}

Response:
{
  "workflow_id": "uuid",
  "status": "planning",
  "current_agent": "supervisor",
  "created_at": "2026-02-23T...",
  "last_updated": "2026-02-23T..."
}
```

#### Get Workflow Status
```
GET /orchestration/{workflow_id}

Response:
{
  "workflow_id": "uuid",
  "status": "executing",
  "current_agent": "router",
  "human_checkpoint_pending": false,
  "results": {},
  "created_at": "2026-02-23T...",
  "last_updated": "2026-02-23T..."
}
```

#### Submit Approval
```
POST /orchestration/{workflow_id}/approve
Content-Type: application/json

{
  "workflow_id": "uuid",
  "status": "approve",
  "feedback": "Optional feedback"
}
```

### Interview Endpoints

#### Start Interview
```
POST /interview/start
Content-Type: application/json

{
  "user_id": "user123"
}

Response:
{
  "interview_id": "uuid",
  "status": "question",
  "question": "What business problem are you trying to solve?",
  "phase": "problem"
}
```

#### Submit Answer
```
POST /interview/{interview_id}/answer
Content-Type: application/json

{
  "interview_id": "uuid",
  "answer": "We need to automate data pipeline analysis"
}

Response:
{
  "interview_id": "uuid",
  "status": "question",
  "question": "Who are your end users?",
  "phase": "problem"
}
```

#### Get Interview Status
```
GET /interview/{interview_id}

Response:
{
  "interview_id": "uuid",
  "phase": "problem",
  "interview_complete": false,
  "responses_count": 1,
  "created_at": "2026-02-23T..."
}
```

### Health Endpoints

```
GET /health
GET /info
```

## File Structure

```
orchestration/
├── server.py              # FastAPI application
├── graph.py               # LangGraph state machines
├── agents.py              # Agent node definitions
├── interview.py           # Interview flow nodes
├── tools.py               # Databricks integration tools
├── requirements.txt       # Python dependencies
├── .env.example           # Example environment variables
└── README.md              # This file
```

## Integration with Express Frontend

Your Express app can call the orchestration service:

```javascript
// In your Express routes
const response = await fetch('http://localhost:8001/orchestration/start', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_id: req.user.id,
    query: req.body.question,
    context: {}
  })
});

const workflow = await response.json();
res.json(workflow);
```

## Development Notes

### Adding New Agent Nodes

1. Create a new async function in `agents.py`
2. Add it to the graph in `graph.py` with `graph.add_node()`
3. Define routing edges from other nodes

### Custom Tools

Create new tools in `tools.py` and import them in agents.

### Testing Locally

```bash
# Terminal 1: Start Express frontend
cd /home/appadmin/projects/Ram_Projects/agents-db
npm start

# Terminal 2: Start Python service
cd orchestration
source ../venv/bin/activate
python server.py
```

Then visit `http://localhost:3000` and it will call the orchestration service at port 8001.

## Next Steps (Phase 2 & 3)

**Phase 2:** Implement actual LLM calls using Claude API or Databricks Mosaic AI
**Phase 3:** Connect agents to your Databricks serving endpoints

See the main recommendations document for detailed implementation guidance.
