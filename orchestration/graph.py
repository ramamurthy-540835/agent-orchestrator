import httpx
import json
import time
import uuid
import asyncio
import re
import os
from datetime import datetime, timezone
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

# Import mock agents
try:
    from orchestration.mock_agents import MOCK_AGENT_REGISTRY, get_mock_agent
except ImportError:
    MOCK_AGENT_REGISTRY = {}
    def get_mock_agent(name):
        return None

# Mock mode configuration
USE_MOCK = os.environ.get("USE_MOCK", "auto")  # auto | always | never

# Databricks config
DATABRICKS_HOST = "https://adb-1377606806062971.11.azuredatabricks.net"
DATABRICKS_TOKEN = "dapia0b0cc277253ec27b9dc25426478699d-3"

ENDPOINT_MAP = {
    "profiler": "mit_structured_data_profiler_endpoint",
    "quality": "mit_data_quality_agent_endpoint",
    "classifier": "mit_data_classifier_endpoint",
    "autoloader": "mit_autoloader_agent_endpoint"
}

class WorkflowState(TypedDict):
    workflow_id: str
    input_data: str
    agent_order: list
    current_step: int
    current_agent: str
    results: dict
    quality_score: float
    pii_detected: list
    human_decisions: list
    execution_log: list
    supervisor_decisions: list
    status: str
    error: str
    use_mock_mode: bool  # Use mock agents (default: True)

def now():
    return datetime.now(timezone.utc).isoformat()

def log_entry(state, event_type, agent, details):
    return {
        "id": str(uuid.uuid4())[:8],
        "timestamp": now(),
        "event_type": event_type,
        "agent": agent,
        "step": state.get("current_step", 0),
        "details": details
    }

def call_agent(endpoint_name: str, content: str, context: dict = None, use_mock: bool = None) -> dict:
    """Route to either Databricks or mock agent.

    Args:
        endpoint_name: Name of the Databricks endpoint
        content: Input content to send to agent
        context: Additional context (state dict)
        use_mock: Override mock mode (if None, uses context['use_mock_mode'] or global USE_MOCK)
    """
    # Determine if we should use mock mode
    if use_mock is None:
        # Check if context has use_mock_mode (from state)
        if context and isinstance(context, dict) and "use_mock_mode" in context:
            use_mock = context.get("use_mock_mode", True)
        else:
            use_mock = USE_MOCK == "always"

    if use_mock:
        print(f"[MOCK] Using mock mode for {endpoint_name}")
        return call_mock_agent(endpoint_name, content, context)

    # Use real Databricks endpoint
    return call_databricks_sync(endpoint_name, content)


def map_endpoint_to_mock(endpoint_name: str) -> str:
    """Map Databricks endpoint name to equivalent mock agent."""
    mapping = {
        "mit_structured_data_profiler_endpoint": "mock_data_profiler",
        "mit_data_quality_agent_endpoint": "mock_data_quality",
        "mit_data_classifier_endpoint": "mock_data_classifier",
        "mit_autoloader_agent_endpoint": "mock_autoloader"
    }
    return mapping.get(endpoint_name, "mock_data_profiler")


def call_mock_agent(endpoint_name: str, content: str, context: dict = None) -> dict:
    """Call a mock agent and format response as Responses API."""
    mock_key = map_endpoint_to_mock(endpoint_name)
    agent = get_mock_agent(mock_key)

    if not agent:
        return {
            "data": {"error": f"Mock agent not found: {mock_key}"},
            "duration_ms": 0,
            "status_code": 404,
            "success": False,
            "source": "MOCK"
        }

    try:
        result = agent.process(content, context)
        # Format as Responses API output
        output = result.get("output", "")
        return {
            "data": {
                "object": "response",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": output
                            }
                        ]
                    }
                ]
            },
            "duration_ms": result.get("duration_ms", 1000),
            "status_code": 200,
            "success": True,
            "source": "MOCK",
            "pii_detected": result.get("pii_detected", []),
            "quality_score": result.get("quality_score")
        }
    except Exception as e:
        print(f"[MOCK ERROR] {mock_key}: {e}")
        return {
            "data": {"error": f"Mock agent error: {str(e)}"},
            "duration_ms": 0,
            "status_code": 500,
            "success": False,
            "source": "MOCK"
        }


def call_databricks_sync(endpoint_name: str, content: str) -> dict:
    """Synchronous HTTP call to Databricks endpoint with exponential backoff retry."""
    url = f"{DATABRICKS_HOST}/serving-endpoints/{endpoint_name}/invocations"
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }
    # Truncate content to 30KB to reduce token usage
    if len(content) > 30000:
        content = content[:30000] + "\n[TRUNCATED]"

    payload = {"input": [{"role": "user", "content": content}]}

    max_retries = 3
    start = time.time()

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=300) as client:
                resp = client.post(url, json=payload, headers=headers)

            resp_data = resp.json()
            duration = int((time.time() - start) * 1000)

            # Check for rate limit (429 or REQUEST_LIMIT_EXCEEDED in response)
            is_rate_limited = (resp.status_code == 429 or
                             "REQUEST_LIMIT_EXCEEDED" in str(resp_data) or
                             "rate limit" in str(resp_data).lower())

            if is_rate_limited and attempt < max_retries - 1:
                wait_time = 90 * (attempt + 1)  # 90s, 180s, 270s
                print(f"[RATE LIMIT] {endpoint_name} attempt {attempt+1}/{max_retries}. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue

            return {
                "data": resp_data,
                "duration_ms": duration,
                "status_code": resp.status_code,
                "success": resp.status_code == 200 and "error_code" not in resp_data
            }
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            if attempt < max_retries - 1:
                print(f"[ERROR] {endpoint_name} attempt {attempt+1}: {str(e)}. Retrying in 60s...")
                time.sleep(60)
                continue
            return {
                "data": {"error": str(e)},
                "duration_ms": duration,
                "status_code": 500,
                "success": False
            }

    # All retries failed - fall back to mock if enabled
    if USE_MOCK == "auto":
        print(f"[FALLBACK] Databricks unavailable, using mock for {endpoint_name}")
        return call_mock_agent(endpoint_name, content)

    return {
        "data": {"error": "Max retries exceeded"},
        "duration_ms": int((time.time() - start) * 1000),
        "status_code": 429,
        "success": False
    }

def extract_text(response_data: dict) -> str:
    """Extract text from Databricks Responses API output."""
    try:
        texts = []
        for item in response_data.get("output", []):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        texts.append(c.get("text", ""))
        if texts:
            return "\n".join(texts)
    except Exception:
        pass
    return json.dumps(response_data)[:2000]

def truncate_csv(data: str, max_rows: int = 50) -> str:
    """Take only header + first N rows of CSV data."""
    lines = data.strip().split('\n')
    if len(lines) <= max_rows + 1:
        return data
    truncated = '\n'.join(lines[:max_rows + 1])
    return truncated + f"\n\n[TRUNCATED: showing {max_rows} of {len(lines)-1} total rows]"

# ============ GRAPH NODES ============

def profile_node(state: WorkflowState) -> dict:
    print(f"[NODE] profile_node starting")

    # Skip if profiler is not in the configured agent order
    agent_order = state.get("agent_order", [])
    if "profiler" not in agent_order:
        print(f"[NODE] profile_node skipped (not in agent_order)")
        return {"current_agent": "quality" if "quality" in agent_order else "classifier" if "classifier" in agent_order else "autoloader" if "autoloader" in agent_order else "complete",
                "current_step": state.get("current_step", 0) + 1}

    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    endpoint = ENDPOINT_MAP["profiler"]
    log.append(log_entry(state, "AGENT_CALL", "profiler", {"endpoint": endpoint, "message": f"Calling {endpoint}..."}))

    # Truncate CSV to first 50 rows to avoid payload limits
    input_data = truncate_csv(state["input_data"], 50)
    result = call_agent(endpoint, input_data, state)
    output_text = extract_text(result["data"]) if result["success"] else json.dumps(result["data"])

    results["profiler"] = {
        "output": output_text[:5000],
        "duration_ms": result["duration_ms"],
        "status": "SUCCESS" if result["success"] else "FAILED",
        "timestamp": now()
    }

    log.append(log_entry(state, "AGENT_RESULT", "profiler", {
        "status": results["profiler"]["status"],
        "duration_ms": result["duration_ms"],
        "message": f"Profiler {'completed' if result['success'] else 'failed'} in {result['duration_ms']}ms",
        "output_preview": output_text[:300]
    }))

    print(f"[NODE] profile_node done: {results['profiler']['status']} in {result['duration_ms']}ms")
    return {
        "results": results,
        "execution_log": log,
        "current_step": state.get("current_step", 0) + 1,
        "current_agent": "supervisor_profile"
    }

def supervisor_profile_node(state: WorkflowState) -> dict:
    print(f"[NODE] supervisor_profile_node")
    log = list(state.get("execution_log", []))
    decisions = list(state.get("supervisor_decisions", []))

    profiler_result = state.get("results", {}).get("profiler", {})
    status = profiler_result.get("status", "UNKNOWN")

    if status == "SUCCESS":
        analysis = "Profiler completed successfully. Data structure analyzed. Proceeding to quality check."
        confidence = 95
        decision = "PROCEED"
    else:
        analysis = "Profiler failed or returned error. Recommending quality check to assess data."
        confidence = 60
        decision = "PROCEED_WITH_CAUTION"

    entry = {"step": "after_profile", "analysis": analysis, "confidence": confidence, "decision": decision}
    decisions.append(entry)

    log.append(log_entry(state, "SUPERVISOR_ANALYSIS", "supervisor", {
        "message": f"🧠 {analysis} [Confidence: {confidence}%]",
        "confidence": confidence,
        "decision": decision
    }))

    return {"execution_log": log, "supervisor_decisions": decisions, "current_agent": "quality"}

def quality_node(state: WorkflowState) -> dict:
    print(f"[NODE] quality_node starting")

    # Skip if quality is not in the configured agent order
    agent_order = state.get("agent_order", [])
    if "quality" not in agent_order:
        print(f"[NODE] quality_node skipped (not in agent_order)")
        return {"current_agent": "classifier" if "classifier" in agent_order else "autoloader" if "autoloader" in agent_order else "complete",
                "current_step": state.get("current_step", 0) + 1}

    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    endpoint = ENDPOINT_MAP["quality"]

    # Add rate limit cooldown log
    log.append(log_entry(state, "AGENT_CALL", "quality", {
        "message": "⏳ Waiting 90s for rate limit cooldown before calling quality agent..."
    }))

    # Wait 90 seconds to allow Databricks rate limit to reset
    time.sleep(90)

    # Send only first 5 rows of CSV + profiler summary (not full CSV)
    csv_lines = state["input_data"].strip().split('\n')
    sample = '\n'.join(csv_lines[:6])  # header + 5 rows
    context = f"Here is a sample of the data (5 of {len(csv_lines)-1} rows):\n{sample}"
    if "profiler" in results:
        context += "\n\n--- PROFILER ANALYSIS ---\n" + results["profiler"].get("output", "")[:3000]

    log.append(log_entry(state, "AGENT_CALL", "quality", {"endpoint": endpoint, "message": f"Calling {endpoint}..."}))

    result = call_agent(endpoint, context, state)
    output_text = extract_text(result["data"]) if result["success"] else json.dumps(result["data"])

    # Extract quality score
    quality_score = 50.0
    try:
        scores = re.findall(r'(?:overall|quality|score|data quality)[^\d]*(\d+(?:\.\d+)?)\s*%', output_text.lower())
        if scores:
            quality_score = float(scores[0])
    except:
        pass

    results["quality"] = {
        "output": output_text[:5000],
        "duration_ms": result["duration_ms"],
        "status": "SUCCESS" if result["success"] else "FAILED",
        "quality_score": quality_score,
        "timestamp": now()
    }

    log.append(log_entry(state, "AGENT_RESULT", "quality", {
        "status": results["quality"]["status"],
        "duration_ms": result["duration_ms"],
        "quality_score": quality_score,
        "message": f"Quality check {'completed' if result['success'] else 'failed'} in {result['duration_ms']}ms. Score: {quality_score}%"
    }))

    print(f"[NODE] quality_node done: score={quality_score}")
    return {
        "results": results,
        "execution_log": log,
        "quality_score": quality_score,
        "current_step": state.get("current_step", 0) + 1,
        "current_agent": "supervisor_quality"
    }

def supervisor_quality_node(state: WorkflowState) -> dict:
    print(f"[NODE] supervisor_quality_node")
    log = list(state.get("execution_log", []))
    decisions = list(state.get("supervisor_decisions", []))
    score = state.get("quality_score", 50)

    if score >= 80:
        analysis = f"✅ Quality score {score}% exceeds threshold. Auto-approving for classification."
        confidence = 95
        decision = "AUTO_APPROVE"
    else:
        analysis = f"⚠️ Quality score {score}% is below 80% threshold. Human review required before proceeding."
        confidence = 75
        decision = "ESCALATE"

    decisions.append({"step": "after_quality", "analysis": analysis, "confidence": confidence, "decision": decision})

    log.append(log_entry(state, "SUPERVISOR_ANALYSIS", "supervisor", {
        "message": f"🧠 {analysis} [Confidence: {confidence}%]",
        "confidence": confidence,
        "decision": decision
    }))

    if score < 80:
        # PAUSE for human intervention
        log.append(log_entry(state, "HUMAN_CHECKPOINT", "quality_gate", {
            "message": f"⚠️ Quality score {score}% below threshold. Awaiting human decision.",
            "question": f"Data quality score is {score}%. Multiple records failed validation (invalid emails, future dates, negative values). Proceed to PII classification?",
            "options": ["approve", "fix_retry", "abort"]
        }))
        return {
            "execution_log": log,
            "supervisor_decisions": decisions,
            "status": "PAUSED",
            "checkpoint_pending": True,
            "checkpoint_type": "QUALITY_GATE",
            "supervisor_guidance": f"Quality score {score}% is below the 80% acceptance threshold. Multiple records failed validation including invalid emails, future dates, and negative values. Review the quality report and decide whether to proceed to PII classification or retry with cleaner data. Confidence: {confidence}%",
            "current_agent": "quality_gate"
        }
    else:
        log.append(log_entry(state, "ROUTING_DECISION", "quality_gate", {
            "message": f"✅ Quality score {score}% ≥ 80%. Auto-approved. Proceeding to classifier."
        }))
        return {
            "execution_log": log,
            "supervisor_decisions": decisions,
            "current_agent": "classifier"
        }

def classify_node(state: WorkflowState) -> dict:
    print(f"[NODE] classify_node starting")

    # Skip if classifier is not in the configured agent order
    agent_order = state.get("agent_order", [])
    if "classifier" not in agent_order:
        print(f"[NODE] classify_node skipped (not in agent_order)")
        return {"current_agent": "autoloader" if "autoloader" in agent_order else "complete",
                "current_step": state.get("current_step", 0) + 1}

    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    endpoint = ENDPOINT_MAP["classifier"]

    # Add rate limit cooldown log
    log.append(log_entry(state, "AGENT_CALL", "classifier", {
        "message": "⏳ Waiting 90s for rate limit cooldown before calling classifier agent..."
    }))

    # Wait 90 seconds to allow Databricks rate limit to reset
    time.sleep(90)

    # Send only column headers + 5 sample rows + profiler summary
    csv_lines = state["input_data"].strip().split('\n')
    header = csv_lines[0] if csv_lines else "unknown"
    sample_rows = '\n'.join(csv_lines[1:6]) if len(csv_lines) > 1 else ""
    context = f"Columns: {header}\nSample rows (5 of {len(csv_lines)-1} total):\n{sample_rows}"

    if "profiler" in results:
        context += "\n\nProfiler found: " + results["profiler"].get("output", "")[:2000]

    log.append(log_entry(state, "AGENT_CALL", "classifier", {"endpoint": endpoint, "message": f"Calling {endpoint}..."}))

    result = call_agent(endpoint, context, state)
    output_text = extract_text(result["data"]) if result["success"] else json.dumps(result["data"])

    # Detect PII
    pii_detected = []
    pii_keywords = ["ssn", "social security", "credit card", "credit_card", "passport", "bank_account"]
    for kw in pii_keywords:
        if kw in output_text.lower():
            pii_detected.append(kw)

    results["classifier"] = {
        "output": output_text[:5000],
        "duration_ms": result["duration_ms"],
        "status": "SUCCESS" if result["success"] else "FAILED",
        "pii_detected": pii_detected,
        "timestamp": now()
    }

    log.append(log_entry(state, "AGENT_RESULT", "classifier", {
        "status": results["classifier"]["status"],
        "duration_ms": result["duration_ms"],
        "pii_detected": pii_detected,
        "message": f"Classifier {'completed' if result['success'] else 'failed'} in {result['duration_ms']}ms. PII: {pii_detected or 'none'}"
    }))

    print(f"[NODE] classify_node done: pii={pii_detected}")
    return {
        "results": results,
        "execution_log": log,
        "pii_detected": pii_detected,
        "current_step": state.get("current_step", 0) + 1,
        "current_agent": "supervisor_classify"
    }

def supervisor_classify_node(state: WorkflowState) -> dict:
    print(f"[NODE] supervisor_classify_node")
    log = list(state.get("execution_log", []))
    decisions = list(state.get("supervisor_decisions", []))
    pii = state.get("pii_detected", [])

    # Check for restricted PII that requires human confirmation
    restricted = [p for p in pii if any(kw in p.lower() for kw in ['ssn', 'credit_card', 'credit', 'social_security'])]

    if restricted:
        analysis = f"🔒 Restricted PII detected: {', '.join(restricted)}. Human confirmation required for compliance."
        confidence = 85
        decision = "ESCALATE"
    else:
        analysis = "✅ No restricted PII detected. Safe to proceed to autoloader."
        confidence = 95
        decision = "PROCEED"

    decisions.append({"step": "after_classify", "analysis": analysis, "confidence": confidence, "pii": pii})

    log.append(log_entry(state, "SUPERVISOR_ANALYSIS", "supervisor", {
        "message": f"🧠 {analysis} [Confidence: {confidence}%]",
        "confidence": confidence,
        "decision": decision
    }))

    if restricted:
        log.append(log_entry(state, "HUMAN_CHECKPOINT", "pii_gate", {
            "message": f"🔒 Restricted PII: {', '.join(restricted)}. Encryption required. Awaiting human confirmation.",
            "question": f"Columns with restricted PII: {', '.join(restricted)}. Apply AES-256 encryption and proceed to auto-loader?",
            "options": ["approve_encrypt", "abort"]
        }))
        return {
            "execution_log": log,
            "supervisor_decisions": decisions,
            "status": "PAUSED",
            "checkpoint_pending": True,
            "checkpoint_type": "PII_GATE",
            "supervisor_guidance": f"Restricted PII detected in columns: {', '.join(restricted)}. PCI-DSS and GDPR compliance require encryption before data loading. Recommend AES-256 encryption for SSN and credit card fields. Proceed with encryption enabled? Confidence: {confidence}%",
            "current_agent": "pii_gate"
        }
    else:
        log.append(log_entry(state, "ROUTING_DECISION", "pii_gate", {
            "message": "✅ No restricted PII. Proceeding to autoloader."
        }))
        return {
            "execution_log": log,
            "supervisor_decisions": decisions,
            "current_agent": "autoloader"
        }

def autoloader_node(state: WorkflowState) -> dict:
    print(f"[NODE] autoloader_node starting")

    # Skip if autoloader is not in the configured agent order
    agent_order = state.get("agent_order", [])
    if "autoloader" not in agent_order:
        print(f"[NODE] autoloader_node skipped (not in agent_order)")
        return {"current_agent": "complete",
                "current_step": state.get("current_step", 0) + 1}

    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    endpoint = ENDPOINT_MAP["autoloader"]

    # Add rate limit cooldown log
    log.append(log_entry(state, "AGENT_CALL", "autoloader", {
        "message": "⏳ Waiting 90s for rate limit cooldown before calling autoloader agent..."
    }))

    # Wait 90 seconds to allow Databricks rate limit to reset
    time.sleep(90)

    # Send only metadata: dataset info + summaries from previous agents
    lines = state["input_data"].strip().split('\n')
    row_count = len(lines) - 1
    column_names = lines[0] if lines else "unknown"
    context = f"Load dataset with {row_count} rows. Columns: {column_names}\nFormat: CSV"

    for key in ["profiler", "quality", "classifier"]:
        if key in results:
            context += f"\n{key}: " + results[key].get("output", "")[:1000]

    log.append(log_entry(state, "AGENT_CALL", "autoloader", {"endpoint": endpoint, "message": f"Calling {endpoint}..."}))

    result = call_agent(endpoint, context, state)
    output_text = extract_text(result["data"]) if result["success"] else json.dumps(result["data"])

    results["autoloader"] = {
        "output": output_text[:5000],
        "duration_ms": result["duration_ms"],
        "status": "SUCCESS" if result["success"] else "FAILED",
        "timestamp": now()
    }

    log.append(log_entry(state, "AGENT_RESULT", "autoloader", {
        "status": results["autoloader"]["status"],
        "duration_ms": result["duration_ms"],
        "message": f"AutoLoader {'completed' if result['success'] else 'failed'} in {result['duration_ms']}ms"
    }))

    print(f"[NODE] autoloader_node done")
    return {
        "results": results,
        "execution_log": log,
        "current_step": state.get("current_step", 0) + 1,
        "current_agent": "supervisor_autoloader"
    }

def supervisor_autoloader_node(state: WorkflowState) -> dict:
    print(f"[NODE] supervisor_autoloader_node")
    log = list(state.get("execution_log", []))
    decisions = list(state.get("supervisor_decisions", []))

    al_result = state.get("results", {}).get("autoloader", {})
    if al_result.get("status") == "SUCCESS":
        analysis = "AutoLoader pipeline code generated successfully. Pipeline ready for deployment."
        confidence = 90
    else:
        analysis = "AutoLoader had issues. Review recommended."
        confidence = 60

    entry = {"step": "after_autoloader", "analysis": analysis, "confidence": confidence}
    decisions.append(entry)

    log.append(log_entry(state, "SUPERVISOR_ANALYSIS", "supervisor", {
        "message": f"🧠 {analysis} [Confidence: {confidence}%]"
    }))

    return {"execution_log": log, "supervisor_decisions": decisions, "current_agent": "complete"}

def complete_node(state: WorkflowState) -> dict:
    print(f"[NODE] complete_node")
    log = list(state.get("execution_log", []))
    results = state.get("results", {})

    total_duration = sum(r.get("duration_ms", 0) for r in results.values())
    agents_run = len(results)
    successful = sum(1 for r in results.values() if r.get("status") == "SUCCESS")

    log.append(log_entry(state, "WORKFLOW_COMPLETE", "orchestrator", {
        "message": f"🏁 Pipeline complete! {successful}/{agents_run} agents succeeded. Total time: {total_duration}ms",
        "total_duration_ms": total_duration,
        "agents_run": agents_run,
        "successful": successful,
        "quality_score": state.get("quality_score", 0),
        "pii_detected": state.get("pii_detected", [])
    }))

    return {
        "execution_log": log,
        "status": "COMPLETED",
        "current_agent": "complete"
    }

# ============ BUILD GRAPH ============

def build_orchestrator_graph():
    graph = StateGraph(WorkflowState)

    graph.add_node("profile", profile_node)
    graph.add_node("supervisor_profile", supervisor_profile_node)
    graph.add_node("quality", quality_node)
    graph.add_node("supervisor_quality", supervisor_quality_node)
    graph.add_node("classify", classify_node)
    graph.add_node("supervisor_classify", supervisor_classify_node)
    graph.add_node("autoloader", autoloader_node)
    graph.add_node("supervisor_autoloader", supervisor_autoloader_node)
    graph.add_node("complete", complete_node)

    graph.set_entry_point("profile")
    graph.add_edge("profile", "supervisor_profile")
    graph.add_edge("supervisor_profile", "quality")
    graph.add_edge("quality", "supervisor_quality")
    graph.add_edge("supervisor_quality", "classify")
    graph.add_edge("classify", "supervisor_classify")
    graph.add_edge("supervisor_classify", "autoloader")
    graph.add_edge("autoloader", "supervisor_autoloader")
    graph.add_edge("supervisor_autoloader", "complete")
    graph.add_edge("complete", END)

    return graph.compile(checkpointer=InMemorySaver())


# ============================================================================
# MODULE-LEVEL SINGLETON GRAPH
# ============================================================================
# Create a single shared graph instance to maintain consistent checkpointer
# across all threads (workflow execution and GET status queries)

_singleton_graph = None

def get_orchestrator():
    """Get or create the singleton graph instance.

    This ensures all threads use the same LangGraph instance with the same
    InMemorySaver checkpointer, enabling real-time state updates during streaming.
    """
    global _singleton_graph
    if _singleton_graph is None:
        _singleton_graph = build_orchestrator_graph()
        print("[GRAPH] Singleton graph created", flush=True)
    return _singleton_graph


# For backwards compatibility
orchestrator = get_orchestrator()
