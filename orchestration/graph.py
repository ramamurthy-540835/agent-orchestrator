import httpx
import json
import time
import uuid
import asyncio
import re
from datetime import datetime, timezone
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

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

def call_databricks_sync(endpoint_name: str, content: str) -> dict:
    """Synchronous HTTP call to Databricks endpoint."""
    url = f"{DATABRICKS_HOST}/serving-endpoints/{endpoint_name}/invocations"
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }
    # Truncate content to 50KB to avoid payload limits
    if len(content) > 50000:
        content = content[:50000] + "\n\n[TRUNCATED - original was " + str(len(content)) + " chars]"

    payload = {"input": [{"role": "user", "content": content}]}

    start = time.time()
    try:
        with httpx.Client(timeout=300) as client:
            resp = client.post(url, json=payload, headers=headers)
        duration = int((time.time() - start) * 1000)

        if resp.status_code == 429:
            print(f"[RATE LIMITED] {endpoint_name} - waiting 60s")
            time.sleep(60)
            with httpx.Client(timeout=300) as client:
                resp = client.post(url, json=payload, headers=headers)
            duration = int((time.time() - start) * 1000)

        return {
            "data": resp.json(),
            "duration_ms": duration,
            "status_code": resp.status_code,
            "success": resp.status_code == 200
        }
    except Exception as e:
        duration = int((time.time() - start) * 1000)
        print(f"[ERROR] {endpoint_name}: {str(e)}")
        return {
            "data": {"error": str(e)},
            "duration_ms": duration,
            "status_code": 500,
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
    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    endpoint = ENDPOINT_MAP["profiler"]
    log.append(log_entry(state, "AGENT_CALL", "profiler", {"endpoint": endpoint, "message": f"Calling {endpoint}..."}))

    # Truncate CSV to first 50 rows to avoid payload limits
    input_data = truncate_csv(state["input_data"], 50)
    result = call_databricks_sync(endpoint, input_data)
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
    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    endpoint = ENDPOINT_MAP["quality"]
    # Truncate CSV to first 50 rows
    context = truncate_csv(state["input_data"], 50)
    if "profiler" in results:
        context += "\n\n--- PROFILER RESULTS ---\n" + results["profiler"].get("output", "")[:2000]

    log.append(log_entry(state, "AGENT_CALL", "quality", {"endpoint": endpoint, "message": f"Calling {endpoint}..."}))

    result = call_databricks_sync(endpoint, context)
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
        analysis = f"Quality score {score}% exceeds threshold. Auto-approving."
        decision = "AUTO_APPROVE"
        confidence = 95
    elif score >= 60:
        analysis = f"Quality score {score}% is moderate. Proceeding with classification."
        decision = "PROCEED"
        confidence = 75
    else:
        analysis = f"Quality score {score}% is low but proceeding to get full picture."
        decision = "PROCEED_WITH_CAUTION"
        confidence = 55

    entry = {"step": "after_quality", "analysis": analysis, "confidence": confidence, "decision": decision, "quality_score": score}
    decisions.append(entry)

    log.append(log_entry(state, "SUPERVISOR_ANALYSIS", "supervisor", {
        "message": f"🧠 {analysis} [Confidence: {confidence}%]",
        "confidence": confidence,
        "decision": decision
    }))

    log.append(log_entry(state, "ROUTING_DECISION", "quality_gate", {
        "message": f"🔀 Quality gate: score={score}%, decision={decision}",
        "quality_score": score
    }))

    return {"execution_log": log, "supervisor_decisions": decisions, "current_agent": "classifier"}

def classify_node(state: WorkflowState) -> dict:
    print(f"[NODE] classify_node starting")
    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    endpoint = ENDPOINT_MAP["classifier"]
    # Only send column names and 10 sample rows
    context = truncate_csv(state["input_data"], 10)
    for key in ["profiler", "quality"]:
        if key in results:
            context += f"\n\n--- {key.upper()} RESULTS ---\n" + results[key].get("output", "")[:1000]

    log.append(log_entry(state, "AGENT_CALL", "classifier", {"endpoint": endpoint, "message": f"Calling {endpoint}..."}))

    result = call_databricks_sync(endpoint, context)
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

    if pii:
        analysis = f"PII detected: {', '.join(pii)}. Encryption recommended. Proceeding to autoloader."
        confidence = 80
    else:
        analysis = "No restricted PII detected. Safe to proceed to autoloader."
        confidence = 95

    entry = {"step": "after_classify", "analysis": analysis, "confidence": confidence, "pii": pii}
    decisions.append(entry)

    log.append(log_entry(state, "SUPERVISOR_ANALYSIS", "supervisor", {
        "message": f"🧠 {analysis} [Confidence: {confidence}%]",
        "pii_detected": pii
    }))

    return {"execution_log": log, "supervisor_decisions": decisions, "current_agent": "autoloader"}

def autoloader_node(state: WorkflowState) -> dict:
    print(f"[NODE] autoloader_node starting")
    log = list(state.get("execution_log", []))
    results = dict(state.get("results", {}))

    endpoint = ENDPOINT_MAP["autoloader"]
    # Send only metadata (column names, row count, summaries)
    lines = state["input_data"].strip().split('\n')
    row_count = len(lines) - 1
    column_names = lines[0] if lines else "unknown"
    context = f"Load CSV data with {row_count} rows and columns: {column_names}. Source: claims.csv\n\n"

    for key in ["profiler", "quality", "classifier"]:
        if key in results:
            context += f"--- {key.upper()} RESULTS ---\n" + results[key].get("output", "")[:1000] + "\n\n"

    log.append(log_entry(state, "AGENT_CALL", "autoloader", {"endpoint": endpoint, "message": f"Calling {endpoint}..."}))

    result = call_databricks_sync(endpoint, context)
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

orchestrator = build_orchestrator_graph()
