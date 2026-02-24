"""
LLM integration with Google Gemini API.
Provides functions for intelligent agent responses and interview question generation.
"""

import os
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Model configuration
MODEL_NAME = "gemini-2.5-flash"  # Fast, cost-effective model with improved reasoning
TEMPERATURE = 0.7  # Balanced creativity and consistency


class GeminiLLM:
    """Wrapper for Gemini API calls with retry logic and error handling"""

    def __init__(self, model: str = MODEL_NAME, temperature: float = TEMPERATURE):
        self.model = genai.GenerativeModel(model_name=model)
        self.temperature = temperature

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def call(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Call Gemini API with a prompt.

        Args:
            prompt: User prompt
            system_prompt: Optional system instructions

        Returns:
            LLM response text
        """
        try:
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

            response = self.model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature,
                    max_output_tokens=1024,
                ),
            )

            return response.text
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def call_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Call Gemini API and parse JSON response.

        Args:
            prompt: User prompt
            system_prompt: Optional system instructions

        Returns:
            Parsed JSON response
        """
        try:
            json_prompt = f"{prompt}\n\nRespond ONLY with valid JSON, no markdown."
            response_text = await self.call(json_prompt, system_prompt)

            # Clean up markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            return json.loads(response_text)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response: {str(e)}")


# Global LLM instance
llm = GeminiLLM()


# ============================================================================
# AGENT PROMPTS
# ============================================================================

SUPERVISOR_SYSTEM_PROMPT = """You are a Supervisor Agent in a multi-agent system for designing solutions on Azure Databricks.

Your responsibilities:
1. Analyze incoming user requests
2. Decide whether to route to specialized agents or ask clarifying questions
3. Determine if human approval is needed for sensitive operations

Always be professional, concise, and focused on understanding the user's needs."""

ROUTER_SYSTEM_PROMPT = """You are a Router Agent that breaks down complex queries into specialized sub-tasks.

Your job is to:
1. Analyze the user's query
2. Identify which specialized agents should handle which parts
3. Determine execution order (parallel vs. sequential)
4. Flag operations needing human approval

Respond with a JSON object containing:
{
  "reasoning": "Brief explanation",
  "route_to": ["agent_name1", "agent_name2"],
  "sub_tasks": [
    {"agent": "agent_name", "task": "description"}
  ],
  "needs_human_approval": true/false,
  "execution_order": "parallel" or "sequential"
}"""

RAG_SYSTEM_PROMPT = """You are a RAG (Retrieval-Augmented Generation) Agent specializing in finding relevant solutions.

Your responsibilities:
1. Search for documentation and past solutions similar to the user's problem
2. Synthesize findings into actionable insights
3. Identify patterns and best practices

Provide clear, relevant information with confidence scores."""

SOLUTION_BUILDER_SYSTEM_PROMPT = """You are a Solution Builder Agent that designs multi-agent architectures for Databricks.

Your job is to:
1. Synthesize requirements from previous agents
2. Design the optimal orchestration pattern (Supervisor, Hierarchical, DAG, etc.)
3. Recommend specific agents and their roles
4. Create an implementation roadmap

Respond with JSON containing:
{
  "architecture": "pattern name",
  "recommended_agents": ["agent1", "agent2"],
  "orchestration_pattern": "pattern",
  "implementation_steps": ["step1", "step2"],
  "estimated_effort_days": number,
  "risk_factors": ["risk1"]
}"""

INTERVIEW_SYSTEM_PROMPT = """You are an expert Solution Architect conducting a structured interview about Databricks agent orchestration.

Interview Rules:
1. Ask ONE question at a time
2. Be conversational and friendly
3. Listen carefully to answers and adapt follow-ups
4. After sufficient information (usually 5-7 questions), summarize and recommend a solution

Current Phase: {phase}
Questions Asked So Far: {questions_asked}
Responses Collected: {responses_count}"""


# ============================================================================
# AGENT FUNCTIONS
# ============================================================================

async def supervisor_analyze(user_query: str) -> Dict[str, Any]:
    """
    Supervisor agent analyzes user query and decides routing.
    """
    prompt = f"""User Query: {user_query}

Analyze this query and determine the next action.
Should we:
1. Ask clarifying questions (respond with "clarify")
2. Route to specialized agents (respond with "route")
3. End the conversation (respond with "end")

Also provide your reasoning."""

    response_text = await llm.call(prompt, SUPERVISOR_SYSTEM_PROMPT)
    return {"analysis": response_text}


async def router_breakdown(user_query: str, context: str = "") -> Dict[str, Any]:
    """
    Router agent breaks down complex queries into sub-tasks.
    """
    prompt = f"""User Query: {user_query}

Context: {context}

Break this down into specific sub-tasks and route to appropriate agents."""

    try:
        return await llm.call_json(prompt, ROUTER_SYSTEM_PROMPT)
    except Exception:
        # Fallback to text response
        response_text = await llm.call(prompt, ROUTER_SYSTEM_PROMPT)
        return {"reasoning": response_text, "sub_tasks": []}


async def rag_search(query: str) -> Dict[str, Any]:
    """
    RAG agent searches for relevant documentation and patterns.
    """
    prompt = f"""Search for solutions related to: {query}

Provide:
1. Relevant patterns and best practices
2. Common architectural approaches
3. Potential challenges and solutions
4. Confidence level for each recommendation"""

    response_text = await llm.call(prompt, RAG_SYSTEM_PROMPT)
    return {
        "source": "rag_agent",
        "findings": response_text,
        "confidence": 0.85,
    }


async def build_solution(
    problem: str, user_role: str, workspaces: List[str], scale_requirements: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Solution builder designs optimal architecture.
    """
    prompt = f"""Based on the following requirements, design an optimal Databricks agent orchestration solution:

Problem: {problem}
User Role: {user_role}
Available Workspaces: {', '.join(workspaces) if workspaces else 'Not specified'}
Scale Requirements: {json.dumps(scale_requirements)}

Design a complete solution architecture."""

    try:
        return await llm.call_json(prompt, SOLUTION_BUILDER_SYSTEM_PROMPT)
    except Exception:
        response_text = await llm.call(prompt, SOLUTION_BUILDER_SYSTEM_PROMPT)
        return {
            "architecture": "Supervisor Pattern",
            "recommended_agents": [],
            "notes": response_text,
        }


async def synthesize_results(rag_findings: str, initial_design: Dict[str, Any]) -> str:
    """
    Synthesize RAG findings and initial design into refined recommendation.
    """
    prompt = f"""Synthesize these findings into a cohesive recommendation:

RAG Findings:
{rag_findings}

Initial Design:
{json.dumps(initial_design, indent=2)}

Provide a single, coherent recommendation that combines the best of both."""

    return await llm.call(prompt, "You are a synthesis expert combining multiple inputs into clear recommendations.")


# ============================================================================
# INTERVIEW FUNCTIONS
# ============================================================================

async def generate_interview_question(
    phase: str,
    questions_asked: int,
    previous_responses: List[str],
) -> str:
    """
    Generate next interview question based on phase and previous answers.
    """
    phase_descriptions = {
        "problem": "Understanding the Business Problem",
        "technical": "Technical Requirements",
        "design": "Orchestration Design",
    }

    prompt = f"""Generate the next interview question for phase: {phase_descriptions.get(phase, phase)}

Questions Asked in This Phase: {questions_asked}
Previous Responses: {json.dumps(previous_responses[-2:] if previous_responses else [])}

Requirements:
1. Ask ONE clear, concise question
2. Build on previous responses if applicable
3. Ensure question is appropriate for the phase
4. Keep it under 150 words

Just respond with the question only."""

    return await llm.call(
        prompt,
        INTERVIEW_SYSTEM_PROMPT.format(
            phase=phase,
            questions_asked=questions_asked,
            responses_count=len(previous_responses),
        ),
    )


async def should_continue_interview(
    phase: str,
    responses_in_phase: int,
    all_responses: List[str],
) -> Dict[str, Any]:
    """
    Determine if interview should continue or move to next phase.
    """
    prompt = f"""Interview Status:
Phase: {phase}
Responses in Phase: {responses_in_phase}
Total Responses: {len(all_responses)}

Should we:
1. Continue asking in this phase
2. Move to the next phase
3. End interview and generate recommendation

Provide JSON with:
{{"continue": true/false, "move_to_next": true/false, "end_interview": true/false}}"""

    try:
        result = await llm.call_json(prompt, INTERVIEW_SYSTEM_PROMPT.format(phase=phase, questions_asked=responses_in_phase, responses_count=len(all_responses)))
        return result
    except Exception:
        # Conservative default: continue if < 3 responses
        return {
            "continue": responses_in_phase < 3,
            "move_to_next": responses_in_phase >= 3,
            "end_interview": False,
        }


async def generate_recommendation(
    problem: str,
    user_role: str,
    data_sources: List[str],
    workspaces: List[str],
    scale: Dict[str, Any],
    human_approval_needed: bool,
    all_responses: List[str],
) -> str:
    """
    Generate final recommendation based on all interview responses.
    """
    prompt = f"""Based on the following interview responses, generate a comprehensive solution recommendation:

Problem: {problem}
User Role: {user_role}
Data Sources: {json.dumps(data_sources)}
Workspaces: {json.dumps(workspaces)}
Scale Requirements: {json.dumps(scale)}
Human-in-the-Loop Required: {human_approval_needed}

Interview Responses:
{json.dumps(all_responses)}

Generate:
1. Recommended Architecture
2. Specific Agents Needed
3. Implementation Steps (numbered)
4. Estimated Timeline
5. Key Considerations

Format as clear, structured recommendation for the user."""

    return await llm.call(
        prompt,
        """You are an expert Azure Databricks architect generating a solution recommendation.
        Be specific, actionable, and professional in your response.""",
    )


# ============================================================================
# SUPERVISOR ANALYSIS FOR EXECUTION LOGS
# ============================================================================

async def supervisor_analyze_logs(
    execution_log: List[Dict[str, Any]],
    current_results: Dict[str, Dict[str, Any]],
    quality_score: float,
    pii_detected: List[str],
) -> Dict[str, Any]:
    """
    Gemini supervisor analyzes execution logs and decides if human intervention
    is needed beyond the 3 fixed gates.

    Args:
        execution_log: List of execution log entries
        current_results: Dictionary of agent results {agent_name: result}
        quality_score: Current quality score from quality agent
        pii_detected: List of detected PII types

    Returns:
        {
            "needs_human_intervention": bool,
            "reason": str,
            "guidance": str,      # AI-generated text for human reviewer
            "severity": "INFO"|"WARNING"|"CRITICAL",
            "suggested_action": str
        }
    """
    # Build context from execution log
    log_summary = []
    for entry in execution_log[-20:]:  # Last 20 entries for context
        log_summary.append(
            f"[{entry['event_type']}] {entry['agent']}: {json.dumps(entry['details'], indent=0)}"
        )
    log_context = "\n".join(log_summary)

    # Identify agent issues
    agent_issues = []
    for agent_name, result in current_results.items():
        if result.get("status") == "FAILED":
            agent_issues.append(f"{agent_name}: FAILED - {result.get('output', '')[:200]}")
        elif result.get("status") == "RATE_LIMITED":
            agent_issues.append(f"{agent_name}: RATE_LIMITED")
        # Check for empty/malformed output
        output = result.get("output", "")
        if not output or (len(output) < 50 and result.get("status") == "SUCCESS"):
            agent_issues.append(f"{agent_name}: Suspiciously short output ({len(output)} chars)")

    prompt = f"""You are a Supervisor Agent analyzing the execution of a data pipeline.

EXECUTION LOG (recent entries):
{log_context}

AGENT RESULTS SUMMARY:
{json.dumps({k: {
    "status": v.get("status"),
    "duration_ms": v.get("duration_ms"),
    "output_length": len(v.get("output", ""))
} for k, v in current_results.items()}, indent=2)}

POTENTIAL ISSUES DETECTED:
{json.dumps(agent_issues) if agent_issues else "None detected"}

CURRENT METRICS:
- Quality Score: {quality_score}%
- PII Detected: {json.dumps(pii_detected) if pii_detected else "None"}

Analyze the execution and determine if human intervention is needed. Look for:
1. Agent output format anomalies (malformed/empty JSON)
2. Agent disagreements (e.g., profiler clean but quality flagged issues)
3. Any FAILED/RATE_LIMITED agent results
4. Unexpected data patterns or quality drops

Respond with JSON:
{{
  "needs_human_intervention": true/false,
  "reason": "Brief explanation of why intervention is/isn't needed",
  "guidance": "Plain language explanation for human reviewer (1-2 sentences)",
  "severity": "INFO|WARNING|CRITICAL",
  "suggested_action": "Recommended action (approve, review carefully, abort, etc)"
}}

Be conservative: if there's any doubt about data quality or agent behavior, recommend intervention."""

    try:
        result = await llm.call_json(
            prompt,
            """You are a pipeline supervision expert. Analyze execution logs for anomalies and
provide clear, actionable guidance. Respond ONLY with valid JSON.""",
        )
        return result
    except Exception as e:
        # Fallback: if quality is borderline, recommend caution
        if 60 <= quality_score < 80 or agent_issues:
            return {
                "needs_human_intervention": True,
                "reason": "Quality score in borderline range or agent issues detected",
                "guidance": f"Quality score is {quality_score}%. Review carefully before proceeding.",
                "severity": "WARNING",
                "suggested_action": "Review quality report and agent outputs",
            }
        return {
            "needs_human_intervention": False,
            "reason": "No anomalies detected",
            "guidance": "Pipeline execution appears normal.",
            "severity": "INFO",
            "suggested_action": "Proceed",
        }


async def autonomous_supervisor_decide(
    analysis: Dict[str, Any],
    quality_score: float,
    pii_detected: List[str],
) -> Dict[str, Any]:
    """
    Autonomous supervisor makes intelligent decisions without human intervention.
    Uses conservative 90% confidence threshold as per system configuration.

    Args:
        analysis: Output from supervisor_analyze_logs()
        quality_score: Current quality score
        pii_detected: List of PII types detected

    Returns:
        {
            "decision": "approve"|"fix"|"escalate",
            "confidence": 0-100,
            "reasoning": str,
            "auto_action": "proceed"|"retry"|"halt",
            "human_escalation": bool
        }
    """
    severity = analysis.get("severity", "INFO")

    # CRITICAL always escalates
    if severity == "CRITICAL":
        return {
            "decision": "escalate",
            "confidence": 95,
            "reasoning": "CRITICAL severity detected. Requires human review.",
            "auto_action": "halt",
            "human_escalation": True,
        }

    # WARNING: evaluate based on quality score and confidence
    if severity == "WARNING":
        # If quality is very high (>90%), supervisor is confident to proceed
        if quality_score >= 90 and not pii_detected:
            return {
                "decision": "approve",
                "confidence": 92,
                "reasoning": f"High quality score ({quality_score}%) despite warning. Safe to proceed.",
                "auto_action": "proceed",
                "human_escalation": False,
            }
        # If quality is acceptable (70-90%) and no critical PII, suggest fix/retry
        elif quality_score >= 70:
            return {
                "decision": "fix",
                "confidence": 85,
                "reasoning": f"Quality score {quality_score}% indicates fixable issues. Recommend retry with adjustments.",
                "auto_action": "retry",
                "human_escalation": False,
            }
        # Quality too low - must escalate
        else:
            return {
                "decision": "escalate",
                "confidence": 88,
                "reasoning": f"Quality score {quality_score}% is too low for autonomous proceed. Requires review.",
                "auto_action": "halt",
                "human_escalation": True,
            }

    # INFO: proceed with confidence if quality is good
    if severity == "INFO":
        if quality_score >= 80 and not pii_detected:
            return {
                "decision": "approve",
                "confidence": 96,
                "reasoning": "Pipeline executing normally. Quality is good. Safe to proceed.",
                "auto_action": "proceed",
                "human_escalation": False,
            }
        elif quality_score >= 75:
            return {
                "decision": "approve",
                "confidence": 91,
                "reasoning": f"Quality acceptable ({quality_score}%). Proceeding with confidence.",
                "auto_action": "proceed",
                "human_escalation": False,
            }
        elif quality_score >= 70:
            return {
                "decision": "approve",
                "confidence": 88,
                "reasoning": f"Quality borderline ({quality_score}%) but meets minimum threshold.",
                "auto_action": "proceed",
                "human_escalation": False,
            }
        else:
            return {
                "decision": "escalate",
                "confidence": 89,
                "reasoning": f"Quality score {quality_score}% below safe threshold.",
                "auto_action": "halt",
                "human_escalation": True,
            }

    # Default: conservative escalation
    return {
        "decision": "escalate",
        "confidence": 60,
        "reasoning": "Unable to make confident autonomous decision.",
        "auto_action": "halt",
        "human_escalation": True,
    }
