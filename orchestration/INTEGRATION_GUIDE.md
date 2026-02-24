# Integration Guide: Express + Python Orchestration

This guide shows how to integrate the Python FastAPI orchestration service with your existing Express frontend.

## Architecture

```
Express Frontend (3000)
         ↓ HTTP
Python Service (8001)
         ↓ API calls
Databricks endpoints
```

## Express Integration Examples

### 1. Start a Workflow

In your Express route handler:

```javascript
// routes/api.js
const fetch = require('node-fetch'); // or use axios

router.post('/api/workflow/start', async (req, res) => {
  try {
    const response = await fetch('http://localhost:8001/orchestration/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: req.user?.id || 'guest',
        query: req.body.query,
        context: req.body.context || {}
      })
    });

    const workflow = await response.json();
    res.json(workflow);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});
```

### 2. Check Workflow Status

```javascript
router.get('/api/workflow/:id', async (req, res) => {
  try {
    const response = await fetch(
      `http://localhost:8001/orchestration/${req.params.id}`
    );
    const status = await response.json();
    res.json(status);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});
```

### 3. Submit Human Approval

```javascript
router.post('/api/workflow/:id/approve', async (req, res) => {
  try {
    const response = await fetch(
      `http://localhost:8001/orchestration/${req.params.id}/approve`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_id: req.params.id,
          status: req.body.status, // "approve" | "reject" | "modify"
          feedback: req.body.feedback
        })
      }
    );

    const result = await response.json();
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});
```

### 4. Interview Flow

```javascript
// Start an interview
router.post('/api/interview/start', async (req, res) => {
  try {
    const response = await fetch('http://localhost:8001/interview/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: req.user?.id || 'guest'
      })
    });

    const interview = await response.json();
    res.json(interview);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Submit an answer
router.post('/api/interview/:id/answer', async (req, res) => {
  try {
    const response = await fetch(
      `http://localhost:8001/interview/${req.params.id}/answer`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          interview_id: req.params.id,
          answer: req.body.answer
        })
      }
    );

    const nextQuestion = await response.json();
    res.json(nextQuestion);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});
```

## Frontend (EJS) Examples

### 1. Display Workflow Status

```ejs
<!-- views/workflow.ejs -->
<div id="workflow-status">
  <h2>Workflow Status</h2>
  <p>ID: <%= workflow.workflow_id %></p>
  <p>Status: <span id="status"><%= workflow.status %></span></p>
  <p>Current Agent: <span id="agent"><%= workflow.current_agent %></span></p>

  <% if (workflow.human_checkpoint_pending) { %>
    <div class="approval-panel">
      <h3>Action Required: Please Review</h3>
      <button onclick="approveWorkflow('<%= workflow.workflow_id %>')">
        Approve
      </button>
      <button onclick="rejectWorkflow('<%= workflow.workflow_id %>')">
        Reject
      </button>
    </div>
  <% } %>
</div>

<script>
function approveWorkflow(workflowId) {
  fetch(`/api/workflow/${workflowId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'approve' })
  })
  .then(r => r.json())
  .then(data => {
    console.log('Approved:', data);
    location.reload();
  });
}
</script>
```

### 2. Interview Chat UI

```ejs
<!-- views/interview.ejs -->
<div id="interview-container">
  <h2>Solution Design Interview</h2>

  <div id="questions" class="conversation">
    <!-- Questions will be appended here -->
  </div>

  <div id="input-area">
    <textarea id="answer-input" placeholder="Your answer..."></textarea>
    <button onclick="submitAnswer()">Next</button>
  </div>
</div>

<script>
let interviewId = '<%= interview_id %>';

function submitAnswer() {
  const answer = document.getElementById('answer-input').value;

  fetch(`/api/interview/${interviewId}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer: answer })
  })
  .then(r => r.json())
  .then(data => {
    if (data.status === 'question') {
      addQuestion(data.question, data.phase);
    } else if (data.status === 'complete') {
      showRecommendation(data.recommendation);
    }
    document.getElementById('answer-input').value = '';
  });
}

function addQuestion(question, phase) {
  const div = document.createElement('div');
  div.className = 'question';
  div.innerHTML = `<p><strong>Q (${phase}):</strong> ${question}</p>`;
  document.getElementById('questions').appendChild(div);
}

function showRecommendation(recommendation) {
  document.getElementById('input-area').innerHTML =
    `<div class="recommendation">${recommendation}</div>`;
}
</script>
```

## Polling for Status Updates

Use polling to check workflow status periodically:

```javascript
// In your frontend
let workflowId = null;

async function startWorkflow(query) {
  const res = await fetch('/api/workflow/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  });

  const workflow = await res.json();
  workflowId = workflow.workflow_id;

  // Poll for updates
  pollWorkflowStatus();
}

function pollWorkflowStatus() {
  setInterval(async () => {
    const res = await fetch(`/api/workflow/${workflowId}`);
    const status = await res.json();

    updateUI(status);

    if (status.human_checkpoint_pending) {
      // Stop polling and wait for user action
      clearInterval(this);
    }
  }, 2000); // Check every 2 seconds
}
```

## WebSocket Alternative (for real-time updates)

For real-time updates without polling, you can add WebSocket support:

```javascript
// Python side (in orchestration/server.py)
from fastapi import WebSocket

@app.websocket("/ws/workflow/{workflow_id}")
async def websocket_endpoint(websocket: WebSocket, workflow_id: str):
    await websocket.accept()

    while True:
        workflow = workflows_store.get(workflow_id)
        await websocket.send_json(workflow["state"])
        await asyncio.sleep(1)
```

```javascript
// Express/Frontend side
const ws = new WebSocket(`ws://localhost:8001/ws/workflow/${workflowId}`);

ws.onmessage = (event) => {
  const state = JSON.parse(event.data);
  updateUI(state);
};
```

## Error Handling

Wrap orchestration calls in try-catch:

```javascript
async function callOrchestration(endpoint, options = {}) {
  try {
    const response = await fetch(endpoint, {
      method: options.method || 'GET',
      headers: { 'Content-Type': 'application/json' },
      ...options
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Orchestration error:', error);
    throw error;
  }
}
```

## Environment Setup

Make sure both services are running:

```bash
# Terminal 1: Express frontend
npm start  # Port 3000

# Terminal 2: Python service
source venv/bin/activate
python orchestration/server.py  # Port 8001
```

## Testing the Integration

Use curl or Postman to test:

```bash
# Start workflow
curl -X POST http://localhost:3000/api/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"query":"Design an agent system"}'

# Get workflow status
curl http://localhost:3000/api/workflow/{workflow_id}

# Submit approval
curl -X POST http://localhost:3000/api/workflow/{workflow_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"status":"approve"}'
```

## Troubleshooting

### "Cannot connect to orchestration service"
- Check Python service is running on port 8001: `curl http://localhost:8001/health`
- Check CORS is enabled (it is, for localhost:3000)
- Check firewall isn't blocking port 8001

### "Workflow not found"
- Verify workflow_id matches what was returned from /start
- Check workflows_store hasn't been cleared (in production use Redis)

### "TypeError: json.dumps() error"
- Check all response objects are JSON serializable
- Use Pydantic models in server.py to ensure proper serialization

## Next Steps

After integrating:

1. **Add LLM calls** to agents (Phase 2)
2. **Connect to Databricks** endpoints (Phase 3)
3. **Add persistence** - Replace in-memory dicts with database
4. **Add authentication** - Secure endpoints with API keys
5. **Monitor with MLflow** - Track all workflow executions
