"""
Human Interview Flow for gathering requirements.
Uses Google Gemini API to generate intelligent follow-up questions.
Conducts structured interviews using LangGraph interrupts.
"""

from langgraph.types import interrupt
from graph import InterviewState
from llm import (
    generate_interview_question,
    should_continue_interview,
    generate_recommendation,
)
import json


# Default fallback questions by phase
DEFAULT_QUESTIONS = {
    "problem": [
        "What business problem are you trying to solve with agent orchestration?",
        "Who are your end users? (data engineers, analysts, business users, customers)",
        "What data sources are involved? (Delta tables, APIs, documents, real-time streams)"
    ],
    "technical": [
        "What Databricks workspaces and serving endpoints do you currently have?",
        "Do agents need to make autonomous decisions, or should workflows be predetermined?",
        "What's the expected scale? (concurrent users, data volume, response time requirements)"
    ],
    "design": [
        "Do you need human-in-the-loop approval at any step?",
        "Should agents share context/memory across conversations?"
    ]
}


async def ask_problem_question(state: InterviewState) -> InterviewState:
    """Ask Phase 1 questions about the business problem using Gemini"""
    responses = state.get("interview_responses", [])
    problem_responses = [r for r in responses if r.get("phase") == "problem"]

    try:
        # Use Gemini to generate next question
        if not problem_responses:
            # First question - use default
            question = DEFAULT_QUESTIONS["problem"][0]
        else:
            # Generate adaptive follow-up using Gemini
            question = await generate_interview_question(
                "problem",
                len(problem_responses),
                [r.get("answer", "") for r in problem_responses]
            )
    except Exception:
        # Fallback to default questions
        question_index = len(problem_responses)
        if question_index < len(DEFAULT_QUESTIONS["problem"]):
            question = DEFAULT_QUESTIONS["problem"][question_index]
        else:
            state["current_phase"] = "technical"
            return state

    # Interrupt to get user response
    user_response = interrupt(
        {
            "type": "question",
            "phase": "problem",
            "question_number": len(problem_responses) + 1,
            "question": question
        }
    )

    # Record response
    responses.append({
        "phase": "problem",
        "question": question,
        "answer": user_response.get("answer", ""),
        "timestamp": user_response.get("timestamp")
    })

    state["interview_responses"] = responses
    state["problem_description"] = user_response.get("answer", "")

    # Check if should move to next phase
    if len(problem_responses) >= 3:
        state["current_phase"] = "technical"

    return state


async def ask_technical_question(state: InterviewState) -> InterviewState:
    """Ask Phase 2 questions about technical requirements using Gemini"""
    responses = state.get("interview_responses", [])
    technical_responses = [r for r in responses if r.get("phase") == "technical"]

    try:
        # Use Gemini to generate next question
        if not technical_responses:
            # First question - use default
            question = DEFAULT_QUESTIONS["technical"][0]
        else:
            # Generate adaptive follow-up
            question = await generate_interview_question(
                "technical",
                len(technical_responses),
                [r.get("answer", "") for r in technical_responses]
            )
    except Exception:
        # Fallback
        question_index = len(technical_responses)
        if question_index < len(DEFAULT_QUESTIONS["technical"]):
            question = DEFAULT_QUESTIONS["technical"][question_index]
        else:
            state["current_phase"] = "design"
            return state

    # Interrupt to get user response
    user_response = interrupt(
        {
            "type": "question",
            "phase": "technical",
            "question_number": len(technical_responses) + 1,
            "question": question
        }
    )

    # Record response
    responses.append({
        "phase": "technical",
        "question": question,
        "answer": user_response.get("answer", ""),
        "timestamp": user_response.get("timestamp")
    })

    state["interview_responses"] = responses

    # Parse technical responses
    if len(technical_responses) == 0:
        # Workspaces question
        state["workspaces"] = user_response.get("workspaces", [])
    elif len(technical_responses) == 2:
        # Scale question
        state["scale_requirements"] = user_response.get("scale", {})

    # Check if should move to next phase
    if len(technical_responses) >= 3:
        state["current_phase"] = "design"

    return state


async def ask_design_question(state: InterviewState) -> InterviewState:
    """Ask Phase 3 questions about orchestration design using Gemini"""
    responses = state.get("interview_responses", [])
    design_responses = [r for r in responses if r.get("phase") == "design"]

    try:
        # Use Gemini to generate next question
        if not design_responses:
            # First question - use default
            question = DEFAULT_QUESTIONS["design"][0]
        else:
            # Generate adaptive follow-up
            question = await generate_interview_question(
                "design",
                len(design_responses),
                [r.get("answer", "") for r in design_responses]
            )
    except Exception:
        # Fallback
        question_index = len(design_responses)
        if question_index < len(DEFAULT_QUESTIONS["design"]):
            question = DEFAULT_QUESTIONS["design"][question_index]
        else:
            state["interview_complete"] = True
            state["current_phase"] = "complete"
            return state

    # Interrupt to get user response
    user_response = interrupt(
        {
            "type": "question",
            "phase": "design",
            "question_number": len(design_responses) + 1,
            "question": question
        }
    )

    # Record response
    responses.append({
        "phase": "design",
        "question": question,
        "answer": user_response.get("answer", ""),
        "timestamp": user_response.get("timestamp")
    })

    state["interview_responses"] = responses

    # Parse design responses
    if len(design_responses) == 0:
        # Human-in-the-loop
        state["human_approval"] = "yes" in user_response.get("answer", "").lower()

    # Check if should end interview
    if len(design_responses) >= 2:
        state["interview_complete"] = True
        state["current_phase"] = "complete"

    return state


async def summarize_responses(state: InterviewState) -> InterviewState:
    """Summarize interview responses and generate Gemini-powered recommendation"""
    responses = state.get("interview_responses", [])

    try:
        # Use Gemini to generate comprehensive recommendation
        recommendation = await generate_recommendation(
            problem=state.get("problem_description", ""),
            user_role=state.get("user_role", "Data Engineer"),
            data_sources=state.get("data_sources", []),
            workspaces=state.get("workspaces", []),
            scale=state.get("scale_requirements", {}),
            human_approval_needed=state.get("human_approval", False),
            all_responses=[r.get("answer", "") for r in responses]
        )
    except Exception as e:
        # Fallback to simple recommendation
        recommendation = generate_fallback_recommendation(state)

    state["interview_complete"] = True
    state["messages"].append({
        "role": "assistant",
        "content": f"Interview complete! Here's your recommended architecture:\n\n{recommendation}"
    })

    return state


def generate_fallback_recommendation(state: InterviewState) -> str:
    """Generate fallback recommendation if Gemini call fails"""
    problem = state.get("problem_description", "Unknown problem")
    workspaces = state.get("workspaces", [])
    requires_approval = state.get("human_approval", False)

    recommendation = f"""
## Recommended Solution Architecture

**Business Problem:** {problem}

**Workspaces Configured:** {len(workspaces) if workspaces else "Not specified"}

**Recommended Pattern:** Supervisor + Hierarchical Agents

**Key Features:**
- Multi-agent orchestration with LangGraph
- Intelligent routing using Gemini API
- Human-in-the-loop approval checkpoints
- Real-time workflow execution tracking

**Implementation Steps:**
1. Set up Python FastAPI orchestration service
2. Configure Databricks workspace connections
3. Deploy agent nodes with Gemini integration
4. Set up monitoring and logging

**Next Steps:**
Your solution design is ready. Contact the team to proceed with deployment.
"""

    return recommendation
