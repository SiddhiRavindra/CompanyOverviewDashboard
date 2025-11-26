"""
Lab 13 - Supervisor Agent Bootstrap & Lab 16 - ReAct Pattern Implementation
LLM-based Planner Agent for Due Diligence Workflow

This planner agent uses an LLM to construct a dynamic plan for due diligence analysis.
It implements the ReAct pattern (Thought → Action → Observation) with structured logging.
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

# Load environment variables
load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"


class PlanStep(BaseModel):
    """Represents a single step in the due diligence plan"""
    step_id: str
    action: str
    description: str
    priority: str = "normal"  # low, normal, high
    dependencies: List[str] = []  # step_ids that must complete first


class DueDiligencePlan(BaseModel):
    """Structured plan for due diligence workflow"""
    company_id: str
    plan_id: str
    timestamp: str
    reasoning: str  # LLM's explanation of the plan
    steps: List[PlanStep]
    estimated_duration: Optional[str] = None
    risk_factors: List[str] = []  # Potential risk areas to investigate


class ReActLog(BaseModel):
    """Structured log entry for ReAct pattern"""
    timestamp: str
    run_id: str
    company_id: str
    phase: str  # "thought", "action", "observation"
    content: str
    metadata: Dict[str, Any] = {}


class PlannerAgent:
    """
    LLM-based Planner Agent that constructs due diligence plans using ReAct reasoning.
    
    Implements:
    - Lab 13: Supervisor Agent Bootstrap with LLM
    - Lab 16: ReAct Pattern (Thought → Action → Observation) with structured logging
    """
    
    def __init__(self, model: str = DEFAULT_MODEL, run_id: Optional[str] = None):
        """
        Initialize the planner agent.
        
        Args:
            model: OpenAI model to use (default: gpt-4o-mini)
            run_id: Optional run ID for correlation in logs
        """
        api_key = os.getenv('OPENAI_KEY') or os.getenv('OPENAI_KEY')
        if not api_key:
            raise RuntimeError(
                "OPENAI_KEY or OPENAI_KEY not set. "
                "Cannot initialize planner agent."
            )
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.run_id = run_id or f"plan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.react_logs: List[ReActLog] = []
        
        # System prompt for the planner
        self.system_prompt = """You are a PE Due Diligence Supervisor Agent specializing in creating execution plans for company analysis.

Your role is to construct a comprehensive, step-by-step plan for conducting due diligence on a company. The plan should cover:
1. Data retrieval and assembly
2. Dashboard generation (structured and RAG-based)
3. Quality evaluation
4. Risk assessment

You should reason through the planning process using the ReAct pattern:
- Thought: Analyze what information is needed and what steps are required
- Action: Retrieve company information if needed, or construct the plan
- Observation: Review the information and refine the plan

Always consider:
- The company's industry and business model
- Potential risk factors (layoffs, security incidents, regulatory issues)
- Data availability and completeness
- The need for both structured and RAG-based analysis

Return your plan as a structured JSON object with:
- reasoning: Your explanation of why this plan is appropriate
- steps: List of steps with step_id, action, description, priority, and dependencies
- risk_factors: Areas that may require special attention"""
    
    def _log_react(self, phase: str, content: str, company_id: str, metadata: Dict[str, Any] = None):
        """
        Log a ReAct step (Thought, Action, or Observation).
        
        Args:
            phase: "thought", "action", or "observation"
            content: The content of the step
            company_id: Company ID for correlation
            metadata: Additional metadata
        """
        log_entry = ReActLog(
            timestamp=datetime.now(timezone.utc).isoformat(),
            run_id=self.run_id,
            company_id=company_id,
            phase=phase,
            content=content,
            metadata=metadata or {}
        )
        self.react_logs.append(log_entry)
        
        # Also log to standard logger
        logger.info(f"[ReAct {phase.upper()}] {content}")
    
    def _get_company_context(self, company_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve basic company context to inform planning.
        This is an optional step to make the plan more informed.
        
        Args:
            company_id: Company identifier
            
        Returns:
            Dictionary with company context or None if unavailable
        """
        try:
            from src.tools.payload_tool import get_latest_structured_payload
            import asyncio
            
            # Try to get payload (async function)
            try:
                payload = asyncio.run(get_latest_structured_payload(company_id))
                if payload and hasattr(payload, 'company_record'):
                    company = payload.company_record
                    return {
                        "company_id": company_id,
                        "name": company.legal_name or company.brand_name or company_id,
                        "industry": ", ".join(company.categories) if company.categories else "Unknown",
                        "founded": str(company.founded_year) if company.founded_year else "Unknown",
                        "has_events": len(payload.events) > 0 if hasattr(payload, 'events') else False,
                        "has_snapshots": len(payload.snapshots) > 0 if hasattr(payload, 'snapshots') else False,
                    }
            except Exception as e:
                logger.debug(f"Could not retrieve payload for context: {e}")
                return None
        except ImportError:
            logger.debug("Payload tool not available for context retrieval")
            return None
    
    def plan_due_diligence(self, company_id: str) -> Dict[str, Any]:
        """
        Main planning function that uses LLM to construct a due diligence plan.
        Implements ReAct pattern with structured logging.
        
        Args:
            company_id: Company identifier to plan for
            
        Returns:
            Dictionary containing the plan (compatible with workflow expectations)
        """
        # ReAct: Thought - Analyze what's needed
        thought_1 = f"I need to create a due diligence plan for company: {company_id}. " \
                   f"First, I should check if I have any context about this company to inform my planning."
        self._log_react("thought", thought_1, company_id)
        
        # ReAct: Action - Retrieve company context
        action_1 = f"Retrieving company context for {company_id}"
        self._log_react("action", action_1, company_id, {"tool": "get_company_context"})
        
        company_context = self._get_company_context(company_id)
        
        # ReAct: Observation - Review context
        if company_context:
            observation_1 = f"Retrieved context: {company_context.get('name', company_id)} " \
                          f"in {company_context.get('industry', 'Unknown')} industry. " \
                          f"Data available: events={company_context.get('has_events', False)}, " \
                          f"snapshots={company_context.get('has_snapshots', False)}"
        else:
            observation_1 = f"No company context available for {company_id}. " \
                          f"Will create a standard plan."
        self._log_react("observation", observation_1, company_id, company_context or {})
        
        # ReAct: Thought - Plan construction
        thought_2 = "Now I'll use the LLM to generate a comprehensive, tailored plan " \
                   "based on the available information and standard due diligence requirements."
        self._log_react("thought", thought_2, company_id)
        
        # ReAct: Action - Call LLM to generate plan
        action_2 = "Calling LLM to generate structured due diligence plan"
        self._log_react("action", action_2, company_id, {"model": self.model})
        
        # Build user prompt
        context_info = ""
        if company_context:
            context_info = f"""
Company Context:
- Name: {company_context.get('name', 'Unknown')}
- Industry: {company_context.get('industry', 'Unknown')}
- Founded: {company_context.get('founded', 'Unknown')}
- Data Availability: Events={company_context.get('has_events', False)}, Snapshots={company_context.get('has_snapshots', False)}
"""
        
        user_prompt = f"""Create a due diligence execution plan for company ID: {company_id}

{context_info}

The plan must include these core steps (you can customize based on context):
1. Retrieve structured company payload
2. Generate structured dashboard from payload
3. Perform RAG search for additional context
4. Generate RAG-based dashboard
5. Evaluate both dashboards for quality
6. Check for risk signals (layoffs, security incidents, regulatory issues)

Return a JSON object with this structure:
{{
    "reasoning": "Your explanation of the plan approach",
    "steps": [
        {{
            "step_id": "step_1",
            "action": "generate_structured_dashboard",
            "description": "Generate dashboard from structured payload",
            "priority": "high",
            "dependencies": []
        }},
        ...
    ],
    "risk_factors": ["List of potential risk areas to investigate"]
}}

Ensure step_ids match these expected actions:
- "generate_structured_dashboard"
- "generate_rag_dashboard"
- "evaluate_dashboards"
- "check_for_risks"

Return ONLY valid JSON, no markdown formatting."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            plan_json_str = response.choices[0].message.content
            if not plan_json_str:
                raise RuntimeError("LLM returned empty response")
            
            # Clean JSON string (remove markdown code blocks if present)
            plan_json_str = plan_json_str.strip()
            if plan_json_str.startswith("```json"):
                plan_json_str = plan_json_str[7:]  # Remove ```json
            if plan_json_str.startswith("```"):
                plan_json_str = plan_json_str[3:]   # Remove ```
            if plan_json_str.endswith("```"):
                plan_json_str = plan_json_str[:-3]  # Remove trailing ```
            plan_json_str = plan_json_str.strip()
            
            # Parse JSON response
            plan_data = json.loads(plan_json_str)
            
            # ReAct: Observation - Review LLM response
            observation_2 = f"LLM generated plan with {len(plan_data.get('steps', []))} steps. " \
                          f"Reasoning: {plan_data.get('reasoning', 'N/A')[:100]}..."
            self._log_react("observation", observation_2, company_id, {
                "step_count": len(plan_data.get('steps', [])),
                "risk_factors_count": len(plan_data.get('risk_factors', []))
            })
            
            # Convert to DueDiligencePlan model for validation
            plan_steps = [
                PlanStep(**step) for step in plan_data.get('steps', [])
            ]
            
            plan = DueDiligencePlan(
                company_id=company_id,
                plan_id=self.run_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                reasoning=plan_data.get('reasoning', 'Plan generated by LLM'),
                steps=plan_steps,
                estimated_duration=plan_data.get('estimated_duration'),
                risk_factors=plan_data.get('risk_factors', [])
            )
            
            # ReAct: Thought - Finalize plan
            thought_3 = f"Plan validated and ready. Contains {len(plan.steps)} steps " \
                       f"with {len(plan.risk_factors)} risk factors identified."
            self._log_react("thought", thought_3, company_id)
            
            # Save ReAct trace
            self._save_react_trace(company_id)
            
            # Convert to workflow-compatible format
            return {
                "company_id": company_id,
                "plan_id": plan.plan_id,
                "timestamp": plan.timestamp,
                "reasoning": plan.reasoning,
                "steps": [step.action for step in plan.steps],  # Workflow expects list of action strings
                "detailed_steps": [step.model_dump() for step in plan.steps],  # Full details
                "risk_factors": plan.risk_factors,
                "estimated_duration": plan.estimated_duration
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            # Fallback to default plan
            return self._get_fallback_plan(company_id)
        except Exception as e:
            logger.error(f"Error generating plan with LLM: {e}")
            # Fallback to default plan
            return self._get_fallback_plan(company_id)
    
    def _get_fallback_plan(self, company_id: str) -> Dict[str, Any]:
        """
        Fallback plan if LLM fails.
        
        Args:
            company_id: Company identifier
            
        Returns:
            Default plan structure
        """
        logger.warning(f"Using fallback plan for {company_id}")
        return {
            "company_id": company_id,
            "plan_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reasoning": "Fallback plan: LLM generation failed, using standard workflow",
            "steps": [
                "generate_structured_dashboard",
                "generate_rag_dashboard",
                "evaluate_dashboards",
                "check_for_risks",
            ],
            "detailed_steps": [
                {
                    "step_id": "step_1",
                    "action": "generate_structured_dashboard",
                    "description": "Generate dashboard from structured payload",
                    "priority": "high",
                    "dependencies": []
                },
                {
                    "step_id": "step_2",
                    "action": "generate_rag_dashboard",
                    "description": "Generate dashboard from RAG search results",
                    "priority": "high",
                    "dependencies": []
                },
                {
                    "step_id": "step_3",
                    "action": "evaluate_dashboards",
                    "description": "Evaluate dashboard quality",
                    "priority": "normal",
                    "dependencies": ["step_1", "step_2"]
                },
                {
                    "step_id": "step_4",
                    "action": "check_for_risks",
                    "description": "Check for risk signals",
                    "priority": "high",
                    "dependencies": ["step_1", "step_2"]
                }
            ],
            "risk_factors": [],
            "estimated_duration": None
        }
    
    def _save_react_trace(self, company_id: str):
        """
        Save ReAct trace to file for documentation (Lab 16 requirement).
        
        Args:
            company_id: Company identifier
        """
        try:
            project_root = Path(__file__).parent.parent.parent
            docs_dir = project_root / "docs"
            docs_dir.mkdir(exist_ok=True)
            
            trace_file = docs_dir / f"REACT_TRACE_{company_id}_{self.run_id}.json"
            
            trace_data = {
                "run_id": self.run_id,
                "company_id": company_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "react_steps": [log.model_dump() for log in self.react_logs]
            }
            
            with open(trace_file, 'w', encoding='utf-8') as f:
                json.dump(trace_data, f, indent=2)
            
            logger.info(f"ReAct trace saved to: {trace_file}")
        except Exception as e:
            logger.warning(f"Failed to save ReAct trace: {e}")


# Global instance for convenience
_planner_agent: Optional[PlannerAgent] = None


def plan_due_diligence(company_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function for workflow integration.
    Creates or reuses a PlannerAgent instance and generates a plan.
    
    Args:
        company_id: Company identifier
        run_id: Optional run ID for correlation
        
    Returns:
        Plan dictionary compatible with workflow expectations
    """
    global _planner_agent
    
    # Create new agent for each run (or reuse if same run_id)
    if _planner_agent is None or (_planner_agent.run_id != run_id and run_id is not None):
        _planner_agent = PlannerAgent(run_id=run_id)
    
    return _planner_agent.plan_due_diligence(company_id)


if __name__ == "__main__":
    """
    Test the planner agent standalone.
    Usage: python src/agents/planner_agent.py <company_id>
    """
    import sys
    
    if len(sys.argv) > 1:
        test_company_id = sys.argv[1]
    else:
        test_company_id = "databricks"  # Default test company
    
    print(f"\n{'='*60}")
    print(f"🧠 Testing Planner Agent - Company: {test_company_id}")
    print(f"{'='*60}\n")
    
    try:
        plan = plan_due_diligence(test_company_id)
        
        print("\n📋 Generated Plan:")
        print(json.dumps(plan, indent=2))
        
        print(f"\n✅ Plan generated successfully!")
        print(f"   Steps: {len(plan.get('steps', []))}")
        print(f"   Risk Factors: {len(plan.get('risk_factors', []))}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
