"""
FastAPI server for LangGraph orchestration.
Provides HTTP endpoints for the Express frontend to call.
Runs on port 8001.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
import json
import asyncio
import threading
from datetime import datetime

from .graph import (
    orchestrator, WorkflowState,
    build_orchestrator_graph
)

# Stub out unused imports for compatibility
def initialize_tools(): pass
def initialize_databricks(): pass

# Initialize FastAPI app
app = FastAPI(
    title="Agent Orchestration Service",
    description="LangGraph-based multi-agent orchestration for Databricks",
    version="1.0.0"
)

# Enable CORS for Express frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize tools and Databricks
initialize_tools()
initialize_databricks()

# In-memory store for workflows (use Redis in production)
workflows_store: Dict[str, Dict[str, Any]] = {}
interviews_store: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class StartWorkflowRequest(BaseModel):
    """Request to start a new orchestration workflow"""
    user_id: str
    input_data: str
    agent_order: Optional[List[str]] = None
    agent_specs: Optional[List[Dict[str, str]]] = None  # Dynamic agents: [{"name": "agent", "endpoint": "endpoint"}]
    context: Optional[Dict[str, Any]] = None


class WorkflowResponse(BaseModel):
    """Response with workflow status"""
    workflow_id: str
    status: str
    current_agent: str
    created_at: str
    last_updated: str


class SubmitApprovalRequest(BaseModel):
    """Submit human approval decision"""
    workflow_id: str
    status: str  # "approve", "reject", "modify"
    feedback: Optional[str] = None


class StartInterviewRequest(BaseModel):
    """Request to start a human interview"""
    user_id: str


class SubmitAnswerRequest(BaseModel):
    """Submit answer to interview question"""
    interview_id: str
    answer: str


class InterviewResponse(BaseModel):
    """Response with interview question or completion"""
    interview_id: str
    status: str  # "question", "complete", "error"
    question: Optional[str] = None
    phase: Optional[str] = None
    recommendation: Optional[str] = None


# ============================================================================
# ORCHESTRATION ENDPOINTS
# ============================================================================

def run_workflow_thread(workflow_id: str, initial_state: dict):
    """Run workflow in a thread, saving state after each node completes"""
    try:
        from orchestration.graph import build_orchestrator_graph
        import time

        graph = build_orchestrator_graph()
        config = {"configurable": {"thread_id": workflow_id}}

        print(f"[WORKFLOW] {workflow_id} starting...")

        # Run the graph synchronously - all nodes execute in sequence
        print(f"[WORKFLOW] {workflow_id} invoking graph.invoke()...")
        final_state = graph.invoke(initial_state, config)

        # Convert to dict and ensure it has all fields
        if hasattr(final_state, 'items'):
            final_state = dict(final_state)
        else:
            final_state = final_state if isinstance(final_state, dict) else {}

        # Debug: print what we got back
        log_count = len(final_state.get('execution_log', []))
        result_count = len(final_state.get('results', {}))
        print(f"[WORKFLOW] {workflow_id} invoke() returned: status={final_state.get('status')}, results={result_count}, logs={log_count}")
        print(f"[WORKFLOW] {workflow_id} final_state keys: {list(final_state.keys())}")

        # Set final status
        final_state["status"] = final_state.get("status", "COMPLETED")

        # Save final state to store
        workflows_store[workflow_id]["state"] = final_state
        workflows_store[workflow_id]["last_updated"] = datetime.now().isoformat()

        print(f"[WORKFLOW] {workflow_id} COMPLETED - Saved state with {result_count} results and {log_count} logs")

    except Exception as e:
        import traceback
        print(f"[WORKFLOW ERROR] {workflow_id}: {str(e)}")
        print(traceback.format_exc())
        if workflow_id in workflows_store:
            workflows_store[workflow_id]["state"]["status"] = "FAILED"
            workflows_store[workflow_id]["state"]["error"] = str(e)
            workflows_store[workflow_id]["last_updated"] = datetime.now().isoformat()


@app.post("/orchestration/start", response_model=WorkflowResponse)
async def start_workflow(request: StartWorkflowRequest):
    """
    Start a new orchestration workflow.
    Takes input data and initiates the multi-agent orchestration pipeline.
    """
    workflow_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()

    # Determine first agent name for entry point
    first_agent = "profiler"
    if request.agent_specs:
        first_agent = request.agent_specs[0]["name"]
    elif request.agent_order:
        first_agent = request.agent_order[0]

    # Initialize orchestration state
    initial_state: WorkflowState = {
        "workflow_id": workflow_id,
        "user_id": request.user_id,
        "input_data": request.input_data,
        "agent_order": request.agent_order or ["profiler", "quality", "classifier", "autoloader"],
        "current_step": 0,
        "current_agent": first_agent,
        "results": {},
        "quality_score": 0.0,
        "pii_detected": [],
        "human_decisions": [],
        "execution_log": [],
        "status": "RUNNING",
        "error": None,
        "human_checkpoint_pending": False,
        "checkpoint_type": None,
        "checkpoint_details": None,
        "supervisor_guidance": None,  # AI-generated guidance for human reviewers
    }

    # Store workflow metadata
    workflows_store[workflow_id] = {
        "state": initial_state,
        "created_at": timestamp,
        "last_updated": timestamp,
        "thread_id": workflow_id,  # For LangGraph checkpointer
        "config": {"configurable": {"thread_id": workflow_id}},
        "agent_specs": request.agent_specs,  # Store for reference
    }

    # Start workflow execution in a background thread using stream()
    thread = threading.Thread(
        target=run_workflow_thread,
        args=(workflow_id, initial_state),
        daemon=True
    )
    thread.daemon = True
    thread.start()

    return WorkflowResponse(
        workflow_id=workflow_id,
        status="RUNNING",
        current_agent="profiler",
        created_at=timestamp,
        last_updated=timestamp,
    )


@app.get("/orchestration/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get current status of a workflow"""
    if workflow_id not in workflows_store:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = workflows_store[workflow_id]
    state = workflow["state"]

    return {
        "workflow_id": workflow_id,
        "status": state.get("status", "RUNNING"),
        "current_agent": state.get("current_agent"),
        "current_step": state.get("current_step", 0),
        "agent_order": state.get("agent_order", []),
        "human_checkpoint_pending": state.get("human_checkpoint_pending"),
        "checkpoint_type": state.get("checkpoint_type"),
        "checkpoint_details": state.get("checkpoint_details"),
        "quality_score": state.get("quality_score", 0),
        "pii_detected": state.get("pii_detected", []),
        "supervisor_guidance": state.get("supervisor_guidance", ""),
        "results_count": len(state.get("results", {})),
        "human_decisions_count": len(state.get("human_decisions", [])),
        "log_entries": len(state.get("execution_log", [])),
        "execution_log": state.get("execution_log", []),
        "results": state.get("results", {}),
        "human_decisions": state.get("human_decisions", []),
        "supervisor_decisions": state.get("supervisor_decisions", []),
        "error": state.get("error"),
        "created_at": workflow["created_at"],
        "last_updated": workflow["last_updated"],
    }


@app.post("/orchestration/{workflow_id}/decision")
async def submit_decision(workflow_id: str, request: SubmitApprovalRequest):
    """Submit human decision for a workflow checkpoint"""
    if workflow_id not in workflows_store:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = workflows_store[workflow_id]
    state = workflow["state"]

    if not state.get("human_checkpoint_pending"):
        raise HTTPException(status_code=400, detail="No pending decision for this workflow")

    # Record the human decision
    decision_record = {
        "checkpoint": state.get("checkpoint_type"),
        "decision": request.status,  # approve, fix, abort, modify, confirm_encryption
        "timestamp": datetime.now().isoformat(),
        "approver": "user",
        "feedback": request.feedback or "",
        "details": state.get("checkpoint_details", {})
    }

    decisions = list(state.get("human_decisions", []))
    decisions.append(decision_record)
    state["human_decisions"] = decisions

    # Resume workflow - the graph will use this decision
    state["human_checkpoint_pending"] = False
    state["status"] = "RUNNING"
    workflow["last_updated"] = datetime.now().isoformat()

    return {
        "workflow_id": workflow_id,
        "status": "resumed",
        "checkpoint": state.get("checkpoint_type"),
        "decision_recorded": request.status,
    }


@app.get("/orchestration/{workflow_id}/results")
async def get_workflow_results(workflow_id: str):
    """Get detailed results for a workflow"""
    if workflow_id not in workflows_store:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = workflows_store[workflow_id]
    state = workflow["state"]

    return {
        "workflow_id": workflow_id,
        "status": state.get("status"),
        "quality_score": state.get("quality_score", 0),
        "pii_detected": state.get("pii_detected", []),
        "results": state.get("results", {}),
        "human_decisions": state.get("human_decisions", []),
        "execution_log": state.get("execution_log", []),
        "error": state.get("error"),
    }


@app.get("/orchestration/{workflow_id}/log")
async def get_workflow_log(workflow_id: str):
    """Get execution log for a workflow"""
    if workflow_id not in workflows_store:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = workflows_store[workflow_id]
    state = workflow["state"]

    return {
        "workflow_id": workflow_id,
        "execution_log": state.get("execution_log", []),
    }


# ============================================================================
# INTERVIEW ENDPOINTS
# ============================================================================

@app.post("/interview/start", response_model=InterviewResponse)
async def start_interview(request: StartInterviewRequest):
    """Start a new solution design interview"""
    interview_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()

    initial_state: InterviewState = {
        "messages": [],
        "interview_responses": [],
        "problem_description": "",
        "user_role": "",
        "data_sources": [],
        "workspaces": [],
        "scale_requirements": {},
        "human_approval": False,
        "current_phase": "problem",
        "interview_complete": False,
    }

    interviews_store[interview_id] = {
        "user_id": request.user_id,
        "state": initial_state,
        "created_at": timestamp,
        "last_updated": timestamp,
        "responses": []
    }

    # Start interview graph
    # TODO: Actually invoke the interview_graph here
    # For now, simulate first question
    first_question = "What business problem are you trying to solve with agent orchestration?"

    return InterviewResponse(
        interview_id=interview_id,
        status="question",
        question=first_question,
        phase="problem",
    )


@app.get("/interview/{interview_id}")
async def get_interview(interview_id: str):
    """Get current state of an interview"""
    if interview_id not in interviews_store:
        raise HTTPException(status_code=404, detail="Interview not found")

    interview = interviews_store[interview_id]
    state = interview["state"]

    return {
        "interview_id": interview_id,
        "phase": state.get("current_phase"),
        "interview_complete": state.get("interview_complete"),
        "responses_count": len(state.get("interview_responses", [])),
        "created_at": interview["created_at"],
    }


@app.post("/interview/{interview_id}/answer", response_model=InterviewResponse)
async def submit_answer(interview_id: str, request: SubmitAnswerRequest):
    """Submit an answer to an interview question"""
    if interview_id not in interviews_store:
        raise HTTPException(status_code=404, detail="Interview not found")

    interview = interviews_store[interview_id]
    state = interview["state"]

    # Record response
    state["interview_responses"].append({
        "phase": state.get("current_phase"),
        "answer": request.answer,
        "timestamp": datetime.now().isoformat()
    })

    # Advance interview phase
    responses_in_phase = len([r for r in state["interview_responses"] if r["phase"] == state["current_phase"]])

    if state["current_phase"] == "problem" and responses_in_phase >= 3:
        state["current_phase"] = "technical"
        next_question = "What Databricks workspaces and serving endpoints do you currently have?"
        phase = "technical"
    elif state["current_phase"] == "technical" and responses_in_phase >= 3:
        state["current_phase"] = "design"
        next_question = "Do you need human-in-the-loop approval at any step?"
        phase = "design"
    elif state["current_phase"] == "design" and responses_in_phase >= 2:
        state["interview_complete"] = True
        recommendation = "Thank you! Your interview is complete. Generating recommendation..."
        return InterviewResponse(
            interview_id=interview_id,
            status="complete",
            recommendation=recommendation,
        )
    else:
        # Continue in same phase
        questions = {
            "problem": [
                "What business problem are you trying to solve?",
                "Who are your end users? (data engineers, analysts, business users)",
                "What data sources are involved? (Delta tables, APIs, documents)"
            ],
            "technical": [
                "What Databricks workspaces and serving endpoints do you have?",
                "Do agents need autonomous decisions or predetermined workflows?",
                "What's your scale? (concurrent users, data volume, latency)"
            ],
            "design": [
                "Do you need human-in-the-loop approval at any step?",
                "Should agents share context/memory across conversations?"
            ]
        }
        next_question = questions[state["current_phase"]][responses_in_phase]
        phase = state["current_phase"]

    interview["last_updated"] = datetime.now().isoformat()

    return InterviewResponse(
        interview_id=interview_id,
        status="question",
        question=next_question,
        phase=phase,
    )


# ============================================================================
# DEPLOYMENT ENDPOINTS (Phase 3)
# ============================================================================

@app.get("/deployment/status/{workflow_id}")
async def get_deployment_status(workflow_id: str):
    """Get deployment status for a workflow"""
    if workflow_id not in workflows_store:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = workflows_store[workflow_id]
    deployment_result = workflow["state"].get("results", {}).get("deployment", {})

    return {
        "workflow_id": workflow_id,
        "deployment_status": deployment_result.get("status", "pending"),
        "actions": deployment_result.get("actions", []),
        "created_at": workflow["created_at"],
    }


@app.get("/databricks/status")
async def get_databricks_status():
    """Check Databricks connectivity and configuration"""
    from .databricks_client import databricks_client

    if not databricks_client or not databricks_client.config.is_configured():
        return {
            "status": "not_configured",
            "message": "Databricks credentials not set",
            "configured": False
        }

    try:
        # Try to list endpoints to verify connectivity
        endpoints = await databricks_client.list_endpoints()
        return {
            "status": "connected",
            "configured": True,
            "host": databricks_client.config.host,
            "workspace_id": databricks_client.config.workspace_id,
            "endpoints_available": len(endpoints),
            "message": "Databricks connected successfully"
        }
    except Exception as e:
        return {
            "status": "error",
            "configured": True,
            "message": f"Connection failed: {str(e)}"
        }


@app.get("/databricks/tables")
async def list_databricks_tables(catalog: str = "main", schema: str = "default"):
    """List available tables in Databricks"""
    from .databricks_client import databricks_client

    if not databricks_client or not databricks_client.config.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Databricks not configured"
        )

    try:
        tables = await databricks_client.list_tables(catalog, schema)
        return {
            "catalog": catalog,
            "schema": schema,
            "tables": [
                {
                    "name": t.get("name"),
                    "type": t.get("object_type"),
                    "created_at": t.get("created_timestamp")
                }
                for t in tables
            ],
            "total": len(tables)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing tables: {str(e)}")


@app.get("/databricks/endpoints")
async def list_serving_endpoints():
    """List serving endpoints in Databricks"""
    from .databricks_client import databricks_client

    if not databricks_client or not databricks_client.config.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Databricks not configured"
        )

    try:
        endpoints = await databricks_client.list_endpoints()
        return {
            "endpoints": [
                {
                    "name": e.get("name"),
                    "state": e.get("state"),
                    "created_at": e.get("creation_timestamp")
                }
                for e in endpoints
            ],
            "total": len(endpoints)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing endpoints: {str(e)}")


# ============================================================================
# HEALTH & INFO ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from .databricks_client import databricks_client

    databricks_status = "not_configured"
    if databricks_client and databricks_client.config.is_configured():
        databricks_status = "configured"

    return {
        "status": "healthy",
        "service": "Agent Orchestration Service",
        "version": "2.0.0",
        "phase": "Phase 3 (Databricks Integration)",
        "databricks": databricks_status
    }


@app.get("/info")
async def service_info():
    """Service information and capabilities"""
    from .databricks_client import databricks_client

    databricks_info = {
        "configured": False,
        "host": None,
        "workspace_id": None
    }

    if databricks_client and databricks_client.config.is_configured():
        databricks_info = {
            "configured": True,
            "host": databricks_client.config.host,
            "workspace_id": databricks_client.config.workspace_id
        }

    return {
        "service": "Agent Orchestration Service",
        "version": "2.0.0",
        "phase": "Phase 3 (Databricks Integration)",
        "capabilities": [
            "multi-agent orchestration",
            "human-in-the-loop approval",
            "interview-based requirement gathering",
            "Databricks workspace integration",
            "MLflow tracing",
            "Job creation and deployment",
            "Serving endpoint management"
        ],
        "active_workflows": len(workflows_store),
        "active_interviews": len(interviews_store),
        "databricks": databricks_info
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
