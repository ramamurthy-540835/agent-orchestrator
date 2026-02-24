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
from functools import partial
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver
from .llm import supervisor_analyze_logs, autonomous_supervisor_decide

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
    supervisor_guidance: Optional[str]  # AI-generated guidance for human reviewers

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
# GENERIC AGENT NODE (supports any Databricks endpoint)
# ============================================================================

async def generic_agent_node(
    state: OrchestratorState,
    endpoint_name: str,
    agent_name: str,
) -> Dict[str, Any]:
    """
    Generic node that can call any Databricks agent endpoint.
    Supports dynamic agents - any endpoint can be used.
    """
    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    # Build context with previous results
    context = state["input_data"]
    if state.get("results"):
        for prev_agent in results:
            if prev_agent != agent_name:
                prev_output = results[prev_agent].get("output", "")
                context += f"\n\n--- {prev_agent.upper()} RESULTS ---\n{prev_output[:1000]}"

    log.append(log_event(state, "AGENT_CALL", agent_name, {
        "endpoint": endpoint_name,
        "input_length": len(context)
    }))

    result = await call_databricks_agent(endpoint_name, context)
    results[agent_name] = result

    log.append(log_event(state, "AGENT_RESULT", agent_name, {
        "status": result["status"],
        "duration_ms": result["duration_ms"],
        "output_preview": result["output"][:200] if result["output"] else ""
    }))

    return {
        "results": results,
        "execution_log": log,
        "current_step": state["current_step"] + 1,
        "current_agent": agent_name
    }

# ============================================================================
# AUTONOMOUS SUPERVISOR NODE
# ============================================================================

async def supervisor_node(state: OrchestratorState, stage: str = "general") -> Dict[str, Any]:
    """
    Autonomous supervisor analyzes execution and makes decisions without human intervention.
    Only escalates to human if severity is CRITICAL (>90% confidence required).

    Args:
        state: Orchestrator state
        stage: Which stage (after_profile, after_quality, after_classify, etc) - for context

    Returns:
        Updated state with supervisor_guidance and potential human_checkpoint_pending
    """
    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    # Get quality score
    quality_score = state.get("quality_score", 75.0)
    pii_detected = state.get("pii_detected", [])

    # Analyze logs
    analysis = await supervisor_analyze_logs(
        log,
        results,
        quality_score,
        pii_detected
    )

    # Make autonomous decision
    decision = await autonomous_supervisor_decide(
        analysis,
        quality_score,
        pii_detected
    )

    log.append(log_event(state, "SUPERVISOR_ANALYSIS", "supervisor", {
        "stage": stage,
        "analysis": analysis,
        "decision": decision
    }))

    supervisor_guidance = f"{analysis['guidance']} [Confidence: {decision['confidence']}%]"

    # If decision is to escalate and confidence is high (>90%), escalate to human
    if decision["human_escalation"] and decision["confidence"] >= 90:
        log.append(log_event(state, "HUMAN_CHECKPOINT", "supervisor", {
            "reason": analysis["reason"],
            "severity": analysis["severity"],
            "suggested_action": analysis["suggested_action"]
        }))

        return {
            "execution_log": log,
            "supervisor_guidance": supervisor_guidance,
            "human_checkpoint_pending": True,
            "checkpoint_type": f"SUPERVISOR_{analysis['severity']}",
            "checkpoint_details": {
                "supervisor_guidance": supervisor_guidance,
                "analysis": analysis,
                "decision": decision,
                "quality_score": quality_score,
                "pii_detected": pii_detected
            },
            "status": "PAUSED"
        }

    # Otherwise, proceed autonomously based on decision
    return {
        "execution_log": log,
        "supervisor_guidance": supervisor_guidance,
        "human_checkpoint_pending": False,
        "status": "RUNNING"
    }

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
    """Quality gate with supervisor guidance - autonomous with human escalation fallback"""
    log = list(state.get("execution_log", []))
    score = state.get("quality_score", 0)
    supervisor_guidance = state.get("supervisor_guidance", "")

    log.append(log_event(state, "ROUTING_DECISION", "quality_gate", {
        "quality_score": score,
        "threshold": 80,
        "decision": "auto_pass" if score >= 80 else "human_review" if score >= 60 else "auto_halt"
    }))

    if score >= 80:
        # High confidence - auto-approve
        log.append(log_event(state, "ROUTING_DECISION", "quality_gate", {
            "action": "AUTO_APPROVED",
            "reason": f"Quality score {score}% >= 80% threshold. Supervisor guidance: {supervisor_guidance[:200]}"
        }))
        return {
            "execution_log": log,
            "status": "RUNNING",
            "human_checkpoint_pending": False,
            "current_agent": "classifier" if "classifier" in state["agent_order"] else "autoloader"
        }

    elif score >= 60:
        # Borderline - only escalate if supervisor marked as CRITICAL
        if state.get("checkpoint_type") and "CRITICAL" in state.get("checkpoint_type", ""):
            # Escalate to human with supervisor guidance
            log.append(log_event(state, "HUMAN_CHECKPOINT", "quality_gate", {
                "reason": f"Quality score {score}% is borderline AND supervisor flagged critical issues.",
                "supervisor_guidance": supervisor_guidance,
                "options": ["approve", "fix", "abort"]
            }))

            human_response = interrupt({
                "checkpoint_type": "QUALITY_GATE",
                "quality_score": score,
                "quality_output": state["results"].get("quality", {}).get("output", "")[:500],
                "supervisor_guidance": supervisor_guidance,
                "question": f"Data quality score is {score}% (borderline). Supervisor analysis: {supervisor_guidance[:300]}. Approve to continue?",
                "options": ["approve", "fix", "abort"]
            })

            decision = human_response.get("decision", "abort")
            decisions = list(state.get("human_decisions", []))
            decisions.append({
                "checkpoint": "quality_gate",
                "decision": decision,
                "timestamp": datetime.utcnow().isoformat(),
                "approver": human_response.get("approver"),
                "details": {"quality_score": score, "supervisor_guidance": supervisor_guidance}
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
            # Supervisor is confident - proceed autonomously
            log.append(log_event(state, "ROUTING_DECISION", "quality_gate", {
                "action": "AUTO_APPROVED_BY_SUPERVISOR",
                "reason": f"Quality score {score}% is acceptable and supervisor is confident. {supervisor_guidance[:200]}"
            }))
            return {
                "execution_log": log,
                "status": "RUNNING",
                "human_checkpoint_pending": False,
                "current_agent": "classifier" if "classifier" in state["agent_order"] else "autoloader"
            }

    else:
        # Low quality - auto-halt unless supervisor has high confidence
        log.append(log_event(state, "ROUTING_DECISION", "quality_gate", {
            "action": "AUTO_HALTED",
            "reason": f"Quality score {score}% < 60% minimum threshold. {supervisor_guidance[:200]}"
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
    """PII gate with supervisor guidance - autonomous with human escalation for CRITICAL"""
    log = list(state.get("execution_log", []))
    pii = state.get("pii_detected", [])
    supervisor_guidance = state.get("supervisor_guidance", "")

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

    # PII found - check if supervisor marked CRITICAL
    if state.get("checkpoint_type") and "CRITICAL" in state.get("checkpoint_type", ""):
        # Escalate to human
        log.append(log_event(state, "HUMAN_CHECKPOINT", "pii_gate", {
            "reason": f"Restricted PII detected ({', '.join(pii)}) AND supervisor flagged critical.",
            "pii_columns": pii,
            "supervisor_guidance": supervisor_guidance,
            "options": ["confirm_encryption", "abort"]
        }))

        human_response = interrupt({
            "checkpoint_type": "PII_GATE",
            "pii_detected": pii,
            "supervisor_guidance": supervisor_guidance,
            "question": f"Restricted PII detected: {', '.join(pii)}. Supervisor: {supervisor_guidance[:300]}. Confirm encryption?",
            "options": ["confirm_encryption", "abort"]
        })

        decision = human_response.get("decision", "abort")
        decisions = list(state.get("human_decisions", []))
        decisions.append({
            "checkpoint": "pii_gate",
            "decision": decision,
            "timestamp": datetime.utcnow().isoformat(),
            "approver": human_response.get("approver"),
            "details": {"pii_detected": pii, "supervisor_guidance": supervisor_guidance}
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
    else:
        # Supervisor is confident - auto-approve PII handling
        log.append(log_event(state, "ROUTING_DECISION", "pii_gate", {
            "action": "AUTO_APPROVED_BY_SUPERVISOR",
            "reason": f"PII detected ({', '.join(pii)}) but supervisor confident in safe handling. {supervisor_guidance[:200]}"
        }))
        return {
            "execution_log": log,
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
    """Pipeline review with supervisor guidance - escalate only if CRITICAL"""
    log = list(state.get("execution_log", []))
    supervisor_guidance = state.get("supervisor_guidance", "")

    pipeline_code = state.get("results", {}).get("autoloader", {}).get("output", "No pipeline generated")

    # If supervisor marked CRITICAL, escalate to human
    if state.get("checkpoint_type") and "CRITICAL" in state.get("checkpoint_type", ""):
        log.append(log_event(state, "HUMAN_CHECKPOINT", "pipeline_review", {
            "reason": "Supervisor flagged critical issue in pipeline. Manual review required.",
            "supervisor_guidance": supervisor_guidance,
            "pipeline_preview": pipeline_code[:500]
        }))

        human_response = interrupt({
            "checkpoint_type": "PIPELINE_REVIEW",
            "pipeline_code": pipeline_code[:2000],
            "supervisor_guidance": supervisor_guidance,
            "question": f"Supervisor found issues: {supervisor_guidance[:300]}. Review pipeline and decide?",
            "options": ["approve_deploy", "modify", "abort"]
        })

        decision = human_response.get("decision", "abort")
        decisions = list(state.get("human_decisions", []))
        decisions.append({
            "checkpoint": "pipeline_review",
            "decision": decision,
            "timestamp": datetime.utcnow().isoformat(),
            "approver": human_response.get("approver"),
            "details": {"supervisor_guidance": supervisor_guidance}
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
    else:
        # Supervisor is confident - auto-approve
        log.append(log_event(state, "ROUTING_DECISION", "pipeline_review", {
            "action": "AUTO_APPROVED",
            "reason": f"Supervisor approved pipeline generation. {supervisor_guidance[:200]}"
        }))
        return {
            "execution_log": log,
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
    """
    Build the LangGraph orchestration workflow with autonomous supervisor nodes.

    NOTE: Supports fixed agent order (profiler → quality → quality_gate → classifier → pii_gate → autoloader → pipeline_review).
    For true dynamic agents, rebuild the graph per workflow in server.py with custom agent_specs.
    """
    graph = StateGraph(OrchestratorState)

    # Add nodes - hardcoded flow with supervisors
    graph.add_node("profile", profile_node)
    graph.add_node("supervisor_after_profile", partial(supervisor_node, stage="after_profile"))
    graph.add_node("quality", quality_node)
    graph.add_node("supervisor_after_quality", partial(supervisor_node, stage="after_quality"))
    graph.add_node("quality_gate", quality_gate_node)
    graph.add_node("classify", classify_node)
    graph.add_node("supervisor_after_classify", partial(supervisor_node, stage="after_classify"))
    graph.add_node("pii_gate", pii_gate_node)
    graph.add_node("autoloader", autoloader_node)
    graph.add_node("supervisor_after_autoloader", partial(supervisor_node, stage="after_autoloader"))
    graph.add_node("pipeline_review", pipeline_review_node)
    graph.add_node("complete", complete_node)

    # Set entry point
    graph.set_entry_point("profile")

    # Define edges with supervisor nodes
    graph.add_edge("profile", "supervisor_after_profile")
    graph.add_edge("supervisor_after_profile", "quality")
    graph.add_edge("quality", "supervisor_after_quality")
    graph.add_edge("supervisor_after_quality", "quality_gate")
    graph.add_conditional_edges(
        "quality_gate",
        route_after_quality_gate,
        {"classifier": "classify", "autoloader": "autoloader", "complete": "complete"}
    )
    graph.add_edge("classify", "supervisor_after_classify")
    graph.add_edge("supervisor_after_classify", "pii_gate")
    graph.add_conditional_edges(
        "pii_gate",
        route_after_pii_gate,
        {"autoloader": "autoloader", "complete": "complete"}
    )
    graph.add_edge("autoloader", "supervisor_after_autoloader")
    graph.add_edge("supervisor_after_autoloader", "pipeline_review")
    graph.add_edge("pipeline_review", "complete")
    graph.add_edge("complete", END)

    # Compile with memory checkpoint
    return graph.compile(checkpointer=InMemorySaver())


def build_custom_orchestrator_graph(agent_specs: List[Dict[str, str]]) -> Any:
    """
    Build a custom orchestration graph for any agent order.

    Args:
        agent_specs: List of agent specifications
                    [{"name": "agent_name", "endpoint": "endpoint_name"}, ...]
                    Example: [{"name": "custom_agent", "endpoint": "my_endpoint"}]

    Returns:
        Compiled LangGraph StateGraph supporting any agent
    """
    graph = StateGraph(OrchestratorState)

    if not agent_specs or len(agent_specs) == 0:
        raise ValueError("agent_specs cannot be empty")

    agent_names = [spec["name"] for spec in agent_specs]

    # Add generic agent nodes for each spec
    for spec in agent_specs:
        agent_name = spec["name"]
        endpoint_name = spec.get("endpoint", agent_name)

        # Add agent node
        graph.add_node(
            agent_name,
            partial(generic_agent_node, endpoint_name=endpoint_name, agent_name=agent_name)
        )

        # Add supervisor node after each agent
        graph.add_node(
            f"supervisor_{agent_name}",
            partial(supervisor_node, stage=f"after_{agent_name}")
        )

    # Add completion node
    graph.add_node("complete", complete_node)

    # Set entry point to first agent
    graph.set_entry_point(agent_names[0])

    # Connect agents with supervisors in sequence
    for i, agent_name in enumerate(agent_names):
        # Agent → Supervisor
        graph.add_edge(agent_name, f"supervisor_{agent_name}")

        # Supervisor → Next Agent or Complete
        if i < len(agent_names) - 1:
            next_agent = agent_names[i + 1]
            graph.add_edge(f"supervisor_{agent_name}", next_agent)
        else:
            # Last agent supervisor → complete
            graph.add_edge(f"supervisor_{agent_name}", "complete")

    # End
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
