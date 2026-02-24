"""
Agent node definitions for LangGraph orchestration.
Each node represents a specialized agent in the system.
Uses Google Gemini API for intelligent responses.
"""

import json
import asyncio
from graph import OrchestrationState
from llm import (
    supervisor_analyze,
    router_breakdown,
    rag_search,
    build_solution,
    synthesize_results,
)
from typing import Any


async def supervisor_node(state: OrchestrationState) -> OrchestrationState:
    """
    Supervisor Agent: Analyzes incoming request and decides next steps.
    Uses Gemini to intelligently route to appropriate agents.
    """
    workflow_id = state.get("workflow_id")
    user_input = state["messages"][-1].get("content", "") if state.get("messages") else ""

    try:
        # Use Gemini to analyze the query
        analysis = await supervisor_analyze(user_input)
        state["messages"].append({
            "role": "assistant",
            "content": f"Analyzing your request: {analysis.get('analysis', '')}",
            "source": "supervisor"
        })

        # Route based on analysis - for now, always go to router
        state["current_agent"] = "router"
        state["workflow_status"] = "executing"
    except Exception as e:
        state["messages"].append({
            "role": "assistant",
            "content": f"Error in supervisor: {str(e)}",
            "source": "supervisor",
            "error": True
        })
        state["current_agent"] = "router"

    return state


async def router_node(state: OrchestrationState) -> OrchestrationState:
    """
    Router Agent: Breaks down complex queries into sub-tasks.
    Uses Gemini to intelligently determine which agents to call.
    """
    user_input = state["messages"][-1].get("content", "") if state.get("messages") else ""
    context = json.dumps(state.get("results", {}))

    try:
        # Use Gemini to route the query
        routing_decision = await router_breakdown(user_input, context)

        state["routing_decision"] = routing_decision
        state["messages"].append({
            "role": "assistant",
            "content": f"Routing decision: {routing_decision.get('reasoning', 'Analyzing your query')}",
            "source": "router"
        })

        # Route to first agent in the decision
        route_to = routing_decision.get("route_to", [])
        if isinstance(route_to, list) and route_to:
            state["current_agent"] = route_to[0]
        else:
            state["current_agent"] = "synthesizer"
    except Exception as e:
        state["messages"].append({
            "role": "assistant",
            "content": f"Error in router: {str(e)}",
            "source": "router",
            "error": True
        })
        state["current_agent"] = "synthesizer"

    return state


async def rag_agent_node(state: OrchestrationState) -> OrchestrationState:
    """
    RAG Agent: Retrieval-Augmented Generation.
    Uses Gemini to search for and synthesize relevant documentation.
    """
    user_input = state["messages"][-1].get("content", "") if state.get("messages") else ""

    try:
        # Use Gemini to search and synthesize
        rag_result = await rag_search(user_input)

        if "results" not in state:
            state["results"] = {}
        state["results"]["rag"] = rag_result

        state["messages"].append({
            "role": "assistant",
            "content": f"Found relevant patterns:\n{rag_result.get('findings', '')}",
            "source": "rag_agent"
        })
    except Exception as e:
        state["messages"].append({
            "role": "assistant",
            "content": f"Error in RAG search: {str(e)}",
            "source": "rag_agent",
            "error": True
        })

    state["current_agent"] = "synthesizer"
    return state


async def sql_agent_node(state: OrchestrationState) -> OrchestrationState:
    """
    SQL Agent: Database and metadata queries.
    Queries Databricks workspace info, tables, and endpoints.
    """
    from databricks_client import databricks_client

    try:
        if not databricks_client or not databricks_client.config.is_configured():
            sql_result = {
                "source": "sql_agent",
                "status": "not_configured",
                "message": "Databricks not configured - Phase 3 feature",
                "tables": [],
                "endpoints": [],
            }
        else:
            # Query Databricks workspace metadata
            tables = await databricks_client.list_tables(catalog="main")
            endpoints = await databricks_client.list_endpoints()

            sql_result = {
                "source": "sql_agent",
                "status": "success",
                "tables_found": len(tables),
                "endpoints_found": len(endpoints),
                "tables": [t.get("name", "unknown") for t in tables[:5]],  # First 5
                "endpoints": [e.get("name", "unknown") for e in endpoints[:5]],
            }

        if "results" not in state:
            state["results"] = {}
        state["results"]["sql"] = sql_result

        message = (
            f"Found {sql_result.get('tables_found', 0)} tables and "
            f"{sql_result.get('endpoints_found', 0)} endpoints"
            if sql_result.get("status") == "success"
            else "Databricks workspace metadata query ready"
        )

        state["messages"].append({
            "role": "assistant",
            "content": message,
            "source": "sql_agent"
        })
    except Exception as e:
        state["messages"].append({
            "role": "assistant",
            "content": f"Error in SQL agent: {str(e)}",
            "source": "sql_agent",
            "error": True
        })

    state["current_agent"] = "synthesizer"
    return state


async def solution_builder_node(state: OrchestrationState) -> OrchestrationState:
    """
    Solution Builder Agent: Designs solution architecture using Gemini.
    Creates recommended architecture and implementation plan.
    """
    problem = state.get("messages", [{}])[-1].get("content", "")
    user_role = state.get("interview_results", {}).get("user_role", "Data Engineer") if state.get("interview_results") else "Data Engineer"
    workspaces = state.get("interview_results", {}).get("workspaces", []) if state.get("interview_results") else []
    scale = state.get("interview_results", {}).get("scale_requirements", {}) if state.get("interview_results") else {}

    try:
        # Use Gemini to build the solution
        solution = await build_solution(problem, user_role, workspaces, scale)

        if "results" not in state:
            state["results"] = {}
        state["results"]["solution"] = solution

        state["messages"].append({
            "role": "assistant",
            "content": f"Recommended Architecture: {solution.get('architecture', 'Multi-Agent System')}\n"
                      f"Implementation Steps: {json.dumps(solution.get('implementation_steps', []), indent=2)}",
            "source": "solution_builder"
        })
    except Exception as e:
        state["messages"].append({
            "role": "assistant",
            "content": f"Error building solution: {str(e)}",
            "source": "solution_builder",
            "error": True
        })

    state["current_agent"] = "synthesizer"
    return state


async def synthesizer_node(state: OrchestrationState) -> OrchestrationState:
    """
    Synthesizer Agent: Combines results from multiple agents using Gemini.
    Provides final recommendation and prepares for human review.
    """
    try:
        rag_findings = state.get("results", {}).get("rag", {}).get("findings", "")
        initial_design = state.get("results", {}).get("solution", {})

        if rag_findings and initial_design:
            # Use Gemini to synthesize
            synthesis_text = await synthesize_results(rag_findings, initial_design)
        else:
            synthesis_text = "Solution design ready for review"

        synthesis = {
            "source": "synthesizer",
            "summary": synthesis_text,
            "confidence_score": 0.85,
            "ready_for_approval": True,
            "agent_contributions": list(state.get("results", {}).keys())
        }

        if "results" not in state:
            state["results"] = {}
        state["results"]["synthesis"] = synthesis

        state["messages"].append({
            "role": "assistant",
            "content": synthesis_text,
            "source": "synthesizer"
        })
    except Exception as e:
        state["messages"].append({
            "role": "assistant",
            "content": f"Error synthesizing results: {str(e)}",
            "source": "synthesizer",
            "error": True
        })

    # Move to human approval
    state["current_agent"] = "human_approval"
    state["human_checkpoint_pending"] = True

    return state


async def human_approval_node(state: OrchestrationState) -> OrchestrationState:
    """
    Human Approval Checkpoint: Pauses workflow for human review and approval.
    Uses LangGraph's interrupt() to return control to user.
    """
    from langgraph.types import interrupt

    # Format the recommendation for user review
    recommendation = {
        "synthesis": state.get("results", {}).get("synthesis", {}),
        "solution": state.get("results", {}).get("solution", {}),
    }

    # Interrupt to get human feedback
    human_response = interrupt(
        {
            "type": "approval_required",
            "data": recommendation,
            "required_response": ["approve", "reject", "modify"]
        }
    )

    if human_response.get("status") == "approve":
        state["human_approval"] = True
        state["current_agent"] = "deployer"
        state["messages"].append({
            "role": "user",
            "content": "Approved - proceeding with deployment"
        })
    elif human_response.get("status") == "modify":
        # Re-route to solution builder for modifications
        state["human_approval"] = False
        state["current_agent"] = "solution_builder"
        state["messages"].append({
            "role": "user",
            "content": f"Requesting modifications: {human_response.get('feedback', '')}"
        })
    else:
        # Reject and end workflow
        state["workflow_status"] = "completed"
        state["current_agent"] = "completed"
        state["messages"].append({
            "role": "user",
            "content": "Workflow rejected"
        })

    state["human_checkpoint_pending"] = False

    return state


async def deployer_node(state: OrchestrationState) -> OrchestrationState:
    """
    Deployer Agent: Executes the approved solution.
    Creates resources, configures agents, and deploys to Databricks.
    """
    from databricks_client import deployment as db_deployment

    try:
        workflow_id = state.get("workflow_id")
        solution = state.get("results", {}).get("solution", {})

        deployment_actions = []
        deployment_status = "success"

        if not db_deployment or not db_deployment.client.config.is_configured():
            # Databricks not configured - simulate deployment
            deployment_actions = [
                {
                    "type": "create_job",
                    "name": f"orchestration-{workflow_id[:8]}",
                    "status": "simulated",
                    "message": "Databricks not configured - run in production with credentials"
                }
            ]
            deployment_status = "simulated"
        else:
            # Real deployment to Databricks
            job_name = f"orchestration-job-{workflow_id[:8]}"

            # Create Databricks job for the solution
            job_response = await db_deployment.create_or_update_job(
                job_name=job_name,
                notebook_path=f"/Users/orchestration/{job_name}",
                cluster_config={
                    "spark_version": "13.3.x-scala2.12",
                    "node_type_id": "i3.xlarge",
                    "num_workers": 2,
                },
            )

            deployment_actions.append({
                "type": "create_job",
                "name": job_name,
                "job_id": job_response.get("job_id"),
                "status": job_response.get("status"),
            })

            # Get deployment endpoints if model deployment is needed
            endpoints = await db_deployment.client.list_endpoints()
            if endpoints:
                deployment_actions.append({
                    "type": "list_endpoints",
                    "count": len(endpoints),
                    "endpoints": [e.get("name") for e in endpoints[:3]],
                })

        deployment_result = {
            "source": "deployer",
            "status": deployment_status,
            "deployment_id": workflow_id,
            "actions": deployment_actions,
            "solution": {
                "architecture": solution.get("architecture", "Multi-Agent"),
                "agents": solution.get("recommended_agents", []),
            }
        }

        if "results" not in state:
            state["results"] = {}
        state["results"]["deployment"] = deployment_result

        action_summary = "\n".join([
            f"- {a.get('type')}: {a.get('name', 'unnamed')} ({a.get('status', 'unknown')})"
            for a in deployment_actions
        ])

        state["messages"].append({
            "role": "assistant",
            "content": f"Deployment initiated! Actions:\n{action_summary}\n\nWorkflow ID: {workflow_id}",
            "source": "deployer"
        })
    except Exception as e:
        state["messages"].append({
            "role": "assistant",
            "content": f"Error in deployer: {str(e)}",
            "source": "deployer",
            "error": True
        })

    state["workflow_status"] = "completed"
    state["current_agent"] = "completed"

    return state
