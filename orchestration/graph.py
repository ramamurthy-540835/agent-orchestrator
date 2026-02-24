"""
Complete LangGraph orchestrator for multi-agent data pipeline.
Implements conditional routing, human checkpoints, and execution logging.
"""

import asyncio
import httpx
import json
import uuid
import time
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver

# ============================================================================
# CONFIGURATION
# ============================================================================

DATABRICKS_HOST = "https://adb-1377606806062971.11.azuredatabricks.net"
DATABRICKS_TOKEN = "dapia0b0cc277253ec27b9dc25426478699d-3"
RATE_LIMIT_DELAY = 30  # seconds between agent calls

# ============================================================================
# STATE DEFINITION
# ============================================================================

class ExecutionLogEntry(TypedDict):
    """Single entry in the execution log"""
    id: str
    timestamp: str
    workflow_id: str
    event_type: str  # AGENT_CALL, AGENT_RESULT, HUMAN_CHECKPOINT, HUMAN_DECISION, ROUTING_DECISION, ERROR, WORKFLOW_COMPLETE
    agent: str
    step: int
    details: Dict[str, Any]

class AgentResult(TypedDict):
    """Result from a single agent"""
    output: str
    raw: Dict[str, Any]
    duration_ms: int
    timestamp: str
    status: str  # SUCCESS, FAILED, RATE_LIMITED

class HumanDecision(TypedDict):
    """Record of human approval/rejection"""
    checkpoint: str  # quality_gate, pii_gate, pipeline_review
    decision: str  # approve, fix, abort, confirm_encryption
    timestamp: str
    approver: Optional[str]
    details: Dict[str, Any]

class OrchestratorState(TypedDict):
    """Complete state for the orchestration workflow"""
    workflow_id: str
    user_id: str
    input_data: str
    agent_order: List[str]  # User-defined order: [profiler, quality, classifier, autoloader]
    current_step: int
    current_agent: str
    results: Dict[str, AgentResult]  # {agent_name: result}
    quality_score: float
    pii_detected: List[str]
    human_decisions: List[HumanDecision]
    execution_log: List[ExecutionLogEntry]
    status: Literal["RUNNING", "PAUSED", "COMPLETED", "FAILED", "HALTED"]
    error: Optional[str]
    human_checkpoint_pending: bool
    checkpoint_type: Optional[str]
    checkpoint_details: Optional[Dict[str, Any]]

# ============================================================================
# HELPERS
# ============================================================================

def log_event(state: OrchestratorState, event_type: str, agent: str, details: Dict[str, Any]) -> ExecutionLogEntry:
    """Create an execution log entry"""
    return {
        "id": str(uuid.uuid4())[:8],
        "timestamp": datetime.utcnow().isoformat(),
        "workflow_id": state["workflow_id"],
        "event_type": event_type,
        "agent": agent,
        "step": state["current_step"],
        "details": details
    }

async def call_databricks_agent(endpoint_name: str, user_content: str) -> AgentResult:
    """Call a Databricks agent endpoint with Responses API format"""
    url = f"{DATABRICKS_HOST}/serving-endpoints/{endpoint_name}/invocations"
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "input": [{"role": "user", "content": user_content}]
    }

    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(url, json=payload, headers=headers)

        duration_ms = int((time.time() - start_time) * 1000)

        if response.status_code == 429:
            # Rate limited - return rate limit status
            return {
                "output": "Rate limited",
                "raw": {"error": "rate_limited"},
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "RATE_LIMITED"
            }

        if response.status_code != 200:
            return {
                "output": response.text,
                "raw": {"error": f"HTTP {response.status_code}"},
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "FAILED"
            }

        result = response.json()

        # Extract text from Databricks Responses API format
        text = extract_text_from_response(result)

        return {
            "output": text,
            "raw": result,
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "SUCCESS"
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "output": str(e),
            "raw": {"error": str(e)},
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "FAILED"
        }

def extract_text_from_response(result: Dict[str, Any]) -> str:
    """Extract text from Databricks Responses API response format"""
    try:
        outputs = result.get("output", [])
        if isinstance(outputs, list):
            texts = []
            for item in outputs:
                if isinstance(item, dict) and item.get("type") == "message":
                    content = item.get("content", [])
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "output_text":
                            text = c.get("text", "")
                            if text:
                                texts.append(text)
            if texts:
                return "\n\n".join(texts)
    except:
        pass

    # Fallback
    return json.dumps(result)

# ============================================================================
# NODES
# ============================================================================

async def profile_node(state: OrchestratorState) -> Dict[str, Any]:
    """Profile data using DataScout agent"""
    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    log.append(log_event(state, "AGENT_CALL", "profiler", {
        "endpoint": "mit_structured_data_profiler_endpoint",
        "input_length": len(state["input_data"])
    }))

    result = await call_databricks_agent("mit_structured_data_profiler_endpoint", state["input_data"])

    results["profiler"] = result

    log.append(log_event(state, "AGENT_RESULT", "profiler", {
        "status": result["status"],
        "duration_ms": result["duration_ms"],
        "output_preview": result["output"][:200] if result["output"] else ""
    }))

    return {
        "results": results,
        "execution_log": log,
        "current_step": state["current_step"] + 1,
        "current_agent": "quality" if "quality" in state["agent_order"] else "classifier"
    }

async def quality_node(state: OrchestratorState) -> Dict[str, Any]:
    """Validate data quality using DataGuard agent"""
    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    # Build context with profiler output
    context = state["input_data"]
    if "profiler" in results:
        context += f"\n\n--- PROFILER RESULTS ---\n{results['profiler']['output']}"

    log.append(log_event(state, "AGENT_CALL", "quality", {
        "endpoint": "mit_data_quality_agent_endpoint"
    }))

    result = await call_databricks_agent("mit_data_quality_agent_endpoint", context)

    results["quality"] = result

    # Extract quality score
    quality_score = extract_quality_score(result["output"])

    log.append(log_event(state, "AGENT_RESULT", "quality", {
        "status": result["status"],
        "duration_ms": result["duration_ms"],
        "quality_score": quality_score,
        "output_preview": result["output"][:200] if result["output"] else ""
    }))

    return {
        "results": results,
        "execution_log": log,
        "quality_score": quality_score,
        "current_step": state["current_step"] + 1
    }

def extract_quality_score(output: str) -> float:
    """Extract quality score from agent output"""
    try:
        import re
        scores = re.findall(r'(?:overall|quality|score)[^\d]*(\d+(?:\.\d+)?)\s*%', output.lower())
        if scores:
            return float(scores[0])
    except:
        pass
    return 50.0

async def quality_gate_node(state: OrchestratorState) -> Dict[str, Any]:
    """Human checkpoint for quality validation"""
    log = list(state.get("execution_log", []))
    score = state.get("quality_score", 0)

    log.append(log_event(state, "ROUTING_DECISION", "quality_gate", {
        "quality_score": score,
        "threshold": 80,
        "decision": "auto_pass" if score >= 80 else "human_review" if score >= 60 else "auto_halt"
    }))

    if score >= 80:
        log.append(log_event(state, "ROUTING_DECISION", "quality_gate", {
            "action": "AUTO_APPROVED",
            "reason": f"Quality score {score}% >= 80% threshold"
        }))
        return {
            "execution_log": log,
            "status": "RUNNING",
            "human_checkpoint_pending": False,
            "current_agent": "classifier" if "classifier" in state["agent_order"] else "autoloader"
        }

    elif score >= 60:
        # Human checkpoint
        log.append(log_event(state, "HUMAN_CHECKPOINT", "quality_gate", {
            "reason": f"Quality score {score}% is between 60-80%. Human approval required.",
            "options": ["approve", "fix", "abort"]
        }))

        # Pause for human decision
        human_response = interrupt({
            "checkpoint_type": "QUALITY_GATE",
            "quality_score": score,
            "quality_output": state["results"].get("quality", {}).get("output", "")[:500],
            "question": f"Data quality score is {score}% (minimum: 60%, target: 80%). Approve to continue?",
            "options": ["approve", "fix", "abort"]
        })

        decision = human_response.get("decision", "abort")
        decisions = list(state.get("human_decisions", []))
        decisions.append({
            "checkpoint": "quality_gate",
            "decision": decision,
            "timestamp": datetime.utcnow().isoformat(),
            "approver": human_response.get("approver"),
            "details": {"quality_score": score}
        })

        log.append(log_event(state, "HUMAN_DECISION", "quality_gate", {"decision": decision}))

        if decision == "abort":
            return {
                "execution_log": log,
                "human_decisions": decisions,
                "status": "HALTED",
                "human_checkpoint_pending": False
            }

        return {
            "execution_log": log,
            "human_decisions": decisions,
            "status": "RUNNING",
            "human_checkpoint_pending": False,
            "current_agent": "classifier" if "classifier" in state["agent_order"] else "autoloader"
        }

    else:
        # Auto-halt
        log.append(log_event(state, "ROUTING_DECISION", "quality_gate", {
            "action": "AUTO_HALTED",
            "reason": f"Quality score {score}% < 60% minimum threshold"
        }))
        return {
            "execution_log": log,
            "status": "HALTED",
            "human_checkpoint_pending": False
        }

async def classify_node(state: OrchestratorState) -> Dict[str, Any]:
    """Classify data sensitivity using ClassifyGuard agent"""
    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    # Build context with previous results
    context = state["input_data"]
    for agent_name in ["profiler", "quality"]:
        if agent_name in results:
            context += f"\n\n--- {agent_name.upper()} RESULTS ---\n{results[agent_name]['output'][:1000]}"

    log.append(log_event(state, "AGENT_CALL", "classifier", {
        "endpoint": "mit_data_classifier_endpoint"
    }))

    result = await call_databricks_agent("mit_data_classifier_endpoint", context)

    results["classifier"] = result

    # Detect PII columns
    pii_detected = extract_pii_columns(result["output"])

    log.append(log_event(state, "AGENT_RESULT", "classifier", {
        "status": result["status"],
        "duration_ms": result["duration_ms"],
        "pii_detected": pii_detected,
        "output_preview": result["output"][:200] if result["output"] else ""
    }))

    return {
        "results": results,
        "execution_log": log,
        "pii_detected": pii_detected,
        "current_step": state["current_step"] + 1,
        "current_agent": "pii_gate"
    }

def extract_pii_columns(output: str) -> List[str]:
    """Extract detected PII columns from classifier output"""
    pii_keywords = [
        "ssn", "social security", "credit card", "credit_card",
        "passport", "driver license", "bank account", "email",
        "phone", "telephone", "dob", "date of birth"
    ]
    detected = []
    output_lower = output.lower()
    for keyword in pii_keywords:
        if keyword in output_lower and keyword not in detected:
            detected.append(keyword)
    return detected

async def pii_gate_node(state: OrchestratorState) -> Dict[str, Any]:
    """Human checkpoint for PII verification"""
    log = list(state.get("execution_log", []))
    pii = state.get("pii_detected", [])

    if not pii:
        log.append(log_event(state, "ROUTING_DECISION", "pii_gate", {
            "action": "AUTO_PASS",
            "reason": "No restricted PII detected"
        }))
        return {
            "execution_log": log,
            "status": "RUNNING",
            "human_checkpoint_pending": False,
            "current_agent": "autoloader"
        }

    # PII found - human must confirm
    log.append(log_event(state, "HUMAN_CHECKPOINT", "pii_gate", {
        "reason": f"Restricted PII detected: {', '.join(pii)}",
        "pii_columns": pii,
        "options": ["confirm_encryption", "abort"]
    }))

    human_response = interrupt({
        "checkpoint_type": "PII_GATE",
        "pii_detected": pii,
        "question": f"Restricted PII detected: {', '.join(pii)}. Confirm encryption and masking will be applied?",
        "options": ["confirm_encryption", "abort"]
    })

    decision = human_response.get("decision", "abort")
    decisions = list(state.get("human_decisions", []))
    decisions.append({
        "checkpoint": "pii_gate",
        "decision": decision,
        "timestamp": datetime.utcnow().isoformat(),
        "approver": human_response.get("approver"),
        "details": {"pii_detected": pii}
    })

    log.append(log_event(state, "HUMAN_DECISION", "pii_gate", {"decision": decision, "pii": pii}))

    if decision == "abort":
        return {
            "execution_log": log,
            "human_decisions": decisions,
            "status": "HALTED",
            "human_checkpoint_pending": False
        }

    return {
        "execution_log": log,
        "human_decisions": decisions,
        "status": "RUNNING",
        "human_checkpoint_pending": False,
        "current_agent": "autoloader"
    }

async def autoloader_node(state: OrchestratorState) -> Dict[str, Any]:
    """Generate Auto Loader pipeline using AutoLoad agent"""
    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    # Build context with all previous results
    context = state["input_data"]
    for agent_name in ["profiler", "quality", "classifier"]:
        if agent_name in results:
            context += f"\n\n--- {agent_name.upper()} RESULTS ---\n{results[agent_name]['output'][:1000]}"

    log.append(log_event(state, "AGENT_CALL", "autoloader", {
        "endpoint": "mit_autoloader_agent_endpoint"
    }))

    result = await call_databricks_agent("mit_autoloader_agent_endpoint", context)

    results["autoloader"] = result

    log.append(log_event(state, "AGENT_RESULT", "autoloader", {
        "status": result["status"],
        "duration_ms": result["duration_ms"],
        "output_preview": result["output"][:200] if result["output"] else ""
    }))

    return {
        "results": results,
        "execution_log": log,
        "current_step": state["current_step"] + 1,
        "current_agent": "pipeline_review"
    }

async def pipeline_review_node(state: OrchestratorState) -> Dict[str, Any]:
    """Human checkpoint for pipeline review - always triggers"""
    log = list(state.get("execution_log", []))

    pipeline_code = state.get("results", {}).get("autoloader", {}).get("output", "No pipeline generated")

    log.append(log_event(state, "HUMAN_CHECKPOINT", "pipeline_review", {
        "reason": "Auto Loader pipeline generated. Human must review before execution.",
        "pipeline_preview": pipeline_code[:500]
    }))

    human_response = interrupt({
        "checkpoint_type": "PIPELINE_REVIEW",
        "pipeline_code": pipeline_code[:2000],
        "question": "Review the generated Auto Loader pipeline. Approve to deploy?",
        "options": ["approve_deploy", "modify", "abort"]
    })

    decision = human_response.get("decision", "abort")
    decisions = list(state.get("human_decisions", []))
    decisions.append({
        "checkpoint": "pipeline_review",
        "decision": decision,
        "timestamp": datetime.utcnow().isoformat(),
        "approver": human_response.get("approver"),
        "details": {}
    })

    log.append(log_event(state, "HUMAN_DECISION", "pipeline_review", {"decision": decision}))

    if decision == "abort":
        return {
            "execution_log": log,
            "human_decisions": decisions,
            "status": "HALTED",
            "human_checkpoint_pending": False,
            "current_agent": "complete"
        }

    return {
        "execution_log": log,
        "human_decisions": decisions,
        "status": "COMPLETED",
        "human_checkpoint_pending": False,
        "current_agent": "complete"
    }

async def complete_node(state: OrchestratorState) -> Dict[str, Any]:
    """Workflow completion"""
    log = list(state.get("execution_log", []))

    total_duration = sum(r.get("duration_ms", 0) for r in state.get("results", {}).values())

    log.append(log_event(state, "WORKFLOW_COMPLETE", "orchestrator", {
        "total_agents_run": len(state.get("results", {})),
        "total_duration_ms": total_duration,
        "quality_score": state.get("quality_score", 0),
        "pii_detected": state.get("pii_detected", []),
        "human_decisions": len(state.get("human_decisions", []))
    }))

    return {
        "execution_log": log,
        "status": state.get("status", "COMPLETED") if state.get("status") != "PAUSED" else "COMPLETED"
    }

# ============================================================================
# CONDITIONAL ROUTING
# ============================================================================

def route_after_quality_gate(state: OrchestratorState) -> str:
    """Route after quality gate checkpoint"""
    if state.get("status") == "HALTED":
        return "complete"
    return "classifier" if "classifier" in state.get("agent_order", []) else "autoloader"

def route_after_pii_gate(state: OrchestratorState) -> str:
    """Route after PII gate checkpoint"""
    if state.get("status") == "HALTED":
        return "complete"
    return "autoloader"

# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def build_orchestrator_graph() -> Any:
    """Build the LangGraph orchestration workflow"""
    graph = StateGraph(OrchestratorState)

    # Add nodes
    graph.add_node("profile", profile_node)
    graph.add_node("quality", quality_node)
    graph.add_node("quality_gate", quality_gate_node)
    graph.add_node("classify", classify_node)
    graph.add_node("pii_gate", pii_gate_node)
    graph.add_node("autoloader", autoloader_node)
    graph.add_node("pipeline_review", pipeline_review_node)
    graph.add_node("complete", complete_node)

    # Set entry point
    graph.set_entry_point("profile")

    # Define edges
    graph.add_edge("profile", "quality")
    graph.add_edge("quality", "quality_gate")
    graph.add_conditional_edges(
        "quality_gate",
        route_after_quality_gate,
        {"classifier": "classify", "autoloader": "autoloader", "complete": "complete"}
    )
    graph.add_edge("classify", "pii_gate")
    graph.add_conditional_edges(
        "pii_gate",
        route_after_pii_gate,
        {"autoloader": "autoloader", "complete": "complete"}
    )
    graph.add_edge("autoloader", "pipeline_review")
    graph.add_edge("pipeline_review", "complete")
    graph.add_edge("complete", END)

    # Compile with memory checkpoint
    return graph.compile(checkpointer=InMemorySaver())

# Create the graph instance
orchestrator_graph = build_orchestrator_graph()


# ============================================================================
# INTERVIEW GRAPH (Stub for compatibility)
# ============================================================================

class InterviewState(TypedDict):
    """State for the interview phase (stub)"""
    messages: List[Dict[str, str]]
    interview_responses: List[Dict[str, Any]]
    problem_description: str
    user_role: str
    data_sources: List[str]
    workspaces: List[str]
    scale_requirements: Dict[str, Any]
    human_approval: bool
    current_phase: str
    interview_complete: bool


def build_interview_graph() -> Any:
    """Build interview graph (stub for now)"""
    graph = StateGraph(InterviewState)

    async def interview_node(state: InterviewState) -> Dict[str, Any]:
        return {
            "interview_complete": True,
            "human_approval": True
        }

    graph.add_node("interview", interview_node)
    graph.set_entry_point("interview")
    graph.add_edge("interview", END)

    return graph.compile()


interview_graph = build_interview_graph()
