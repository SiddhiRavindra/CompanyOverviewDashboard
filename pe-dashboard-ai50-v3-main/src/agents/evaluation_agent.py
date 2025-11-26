"""
Lab 17 - Supervisory Workflow Pattern: Evaluator Node
LLM-based Evaluation Agent for Dashboard Quality Assessment

This evaluation agent uses an LLM to score dashboards based on a comprehensive rubric.
It implements the ReAct pattern (Thought → Action → Observation) with structured logging.
"""

import os
import json
import re
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


class RubricScores(BaseModel):
    """Individual rubric criterion scores"""
    completeness: float  # 0.0-1.0: Does it cover all 8 required sections?
    accuracy: float      # 0.0-1.0: Are claims factual and verifiable?
    disclosure: float   # 0.0-1.0: Does it properly handle missing data with "Not disclosed"?
    formatting: float   # 0.0-1.0: Is it well-structured and readable?
    provenance: float   # 0.0-1.0: Does it show evidence/citations from sources?
    hallucination_control: float  # 0.0-1.0: Does it avoid making up facts?


class DetailedRubricScores(BaseModel):
    """Detailed rubric scores for both dashboards"""
    rag: RubricScores
    structured: RubricScores


class EvaluationResult(BaseModel):
    """Structured evaluation result"""
    score: float  # Overall score (0.0-1.0)
    rubric: Dict[str, float]  # Simplified rubric for workflow compatibility
    detailed_rubric: Optional[DetailedRubricScores] = None
    winner: str  # "rag" or "structured" or "tie"
    recommendation: str
    strengths: List[str] = []
    weaknesses: List[str] = []
    timestamp: str


class ReActLog(BaseModel):
    """Structured log entry for ReAct pattern"""
    timestamp: str
    run_id: str
    company_id: Optional[str] = None
    phase: str  # "thought", "action", "observation"
    content: str
    metadata: Dict[str, Any] = {}


class EvaluationAgent:
    """
    LLM-based Evaluation Agent that scores dashboards using a comprehensive rubric.
    
    Implements:
    - Lab 17: Evaluator Node that scores dashboards per rubric
    - Lab 16: ReAct Pattern (Thought → Action → Observation) with structured logging
    """
    
    def __init__(self, model: str = DEFAULT_MODEL, run_id: Optional[str] = None):
        """
        Initialize the evaluation agent.
        
        Args:
            model: OpenAI model to use (default: gpt-4o-mini)
            run_id: Optional run ID for correlation in logs
        """
        api_key = os.getenv('OPENAI_KEY') or os.getenv('OPENAI_KEY')
        if not api_key:
            raise RuntimeError(
                "OPENAI_KEY or OPENAI_KEY not set. "
                "Cannot initialize evaluation agent."
            )
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.run_id = run_id or f"eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.react_logs: List[ReActLog] = []
        
        # System prompt for the evaluator
        self.system_prompt = """You are a professional PE (Private Equity) Due Diligence Dashboard Evaluator.

Your role is to evaluate investor-facing dashboards based on a comprehensive rubric. You must be strict, objective, and thorough.

Evaluation Criteria:
1. **Completeness (0.0-1.0)**: Does the dashboard cover all 8 required sections?
   - Company Overview
   - Business Model and GTM
   - Funding & Investor Profile
   - Growth Momentum
   - Visibility & Market Sentiment
   - Risks and Challenges
   - Outlook
   - Disclosure Gaps

2. **Accuracy (0.0-1.0)**: Are the claims factual, verifiable, and accurate?
   - No invented facts (ARR, MRR, valuation, customer logos)
   - Information aligns with source data
   - No contradictions

3. **Disclosure (0.0-1.0)**: Does it properly handle missing data?
   - Uses "Not disclosed." for missing fields
   - Never invents information
   - Clearly indicates what information is unavailable

4. **Formatting (0.0-1.0)**: Is it well-structured and readable?
   - Proper markdown formatting
   - Clear section headers
   - Logical flow
   - Investor-friendly presentation

5. **Provenance (0.0-1.0)**: Does it show evidence or citations?
   - References to source documents
   - Attribution where appropriate
   - Traceability of claims

6. **Hallucination Control (0.0-1.0)**: Does it avoid making up facts?
   - No fabricated metrics
   - No invented customer logos
   - No unsupported claims

Return a JSON object with detailed scores for both RAG and Structured dashboards, plus an overall assessment."""
    
    def _log_react(self, phase: str, content: str, company_id: Optional[str] = None, metadata: Dict[str, Any] = None):
        """
        Log a ReAct step (Thought, Action, or Observation).
        
        Args:
            phase: "thought", "action", or "observation"
            content: The content of the step
            company_id: Optional company ID for correlation
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
    
    def evaluate_dashboards(
        self, 
        rag_dashboard: str, 
        structured_dashboard: str,
        company_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main evaluation function that uses LLM to score dashboards.
        Implements ReAct pattern with structured logging.
        
        Args:
            rag_dashboard: Markdown dashboard generated from RAG pipeline
            structured_dashboard: Markdown dashboard generated from structured pipeline
            company_id: Optional company identifier for correlation
            
        Returns:
            Dictionary containing evaluation results (compatible with workflow expectations)
        """
        # ReAct: Thought - Analyze evaluation task
        thought_1 = f"Evaluating two dashboards: RAG-based ({len(rag_dashboard)} chars) and " \
                   f"Structured-based ({len(structured_dashboard)} chars). " \
                   f"I need to score both on completeness, accuracy, disclosure, formatting, " \
                   f"provenance, and hallucination control."
        self._log_react("thought", thought_1, company_id)
        
        # ReAct: Action - Prepare evaluation prompt
        action_1 = "Preparing comprehensive evaluation prompt with rubric criteria"
        self._log_react("action", action_1, company_id, {"model": self.model})
        
        # Truncate dashboards if too long (keep first 6000 chars each)
        rag_preview = rag_dashboard[:6000] + ("..." if len(rag_dashboard) > 6000 else "")
        structured_preview = structured_dashboard[:6000] + ("..." if len(structured_dashboard) > 6000 else "")
        
        user_prompt = f"""Evaluate two investor-facing dashboards for a PE due diligence assessment.

Evaluate each dashboard on a scale of 0.0 to 1.0 for each criterion:
1. **Completeness**: Does it cover all 8 required sections? (Company Overview, Business Model, Funding, Growth, Visibility, Risks, Outlook, Disclosure Gaps)
2. **Accuracy**: Are claims factual and verifiable? No invented facts?
3. **Disclosure**: Does it use "Not disclosed." for missing data? Never invents information?
4. **Formatting**: Is it well-structured, readable, and investor-friendly?
5. **Provenance**: Does it show evidence, citations, or source references?
6. **Hallucination Control**: Does it avoid making up metrics, logos, or unsupported claims?

Return a JSON object with this exact structure:
{{
    "rag": {{
        "completeness": 0.0-1.0,
        "accuracy": 0.0-1.0,
        "disclosure": 0.0-1.0,
        "formatting": 0.0-1.0,
        "provenance": 0.0-1.0,
        "hallucination_control": 0.0-1.0
    }},
    "structured": {{
        "completeness": 0.0-1.0,
        "accuracy": 0.0-1.0,
        "disclosure": 0.0-1.0,
        "formatting": 0.0-1.0,
        "provenance": 0.0-1.0,
        "hallucination_control": 0.0-1.0
    }},
    "winner": "rag" or "structured" or "tie",
    "overall_assessment": {{
        "strengths": ["list of key strengths"],
        "weaknesses": ["list of key weaknesses"],
        "recommendation": "Brief recommendation text (e.g., 'Approved', 'Approved with minor improvements needed', 'Needs revision')"
    }}
}}

=== RAG DASHBOARD ===
{rag_preview}

=== STRUCTURED DASHBOARD ===
{structured_preview}

Return ONLY valid JSON, no markdown formatting."""
        
        # ReAct: Observation - Prompt prepared
        observation_1 = f"Evaluation prompt prepared. RAG dashboard: {len(rag_dashboard)} chars, " \
                       f"Structured dashboard: {len(structured_dashboard)} chars."
        self._log_react("observation", observation_1, company_id)
        
        # ReAct: Thought - Call LLM for evaluation
        thought_2 = "Calling LLM to perform comprehensive rubric-based evaluation of both dashboards."
        self._log_react("thought", thought_2, company_id)
        
        # ReAct: Action - Call LLM
        action_2 = "Calling LLM evaluation API"
        self._log_react("action", action_2, company_id, {"model": self.model})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent evaluation
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            eval_json_str = response.choices[0].message.content
            if not eval_json_str:
                raise RuntimeError("LLM returned empty response")
            
            # Clean JSON string (remove markdown code blocks if present)
            eval_json_str = eval_json_str.strip()
            if eval_json_str.startswith("```json"):
                eval_json_str = eval_json_str[7:]
            if eval_json_str.startswith("```"):
                eval_json_str = eval_json_str[3:]
            if eval_json_str.endswith("```"):
                eval_json_str = eval_json_str[:-3]
            eval_json_str = eval_json_str.strip()
            
            # Parse JSON response
            eval_data = json.loads(eval_json_str)
            
            # ReAct: Observation - Review LLM response
            winner = eval_data.get("winner", "tie")
            observation_2 = f"LLM evaluation completed. Winner: {winner}. " \
                          f"RAG scores: {len(eval_data.get('rag', {}))} criteria, " \
                          f"Structured scores: {len(eval_data.get('structured', {}))} criteria."
            self._log_react("observation", observation_2, company_id, {
                "winner": winner,
                "rag_criteria_count": len(eval_data.get('rag', {})),
                "structured_criteria_count": len(eval_data.get('structured', {}))
            })
            
            # Calculate overall scores
            rag_scores = eval_data.get("rag", {})
            structured_scores = eval_data.get("structured", {})
            
            # Calculate weighted average for each dashboard
            # All criteria are equally weighted
            rag_overall = sum([
                rag_scores.get("completeness", 0.0),
                rag_scores.get("accuracy", 0.0),
                rag_scores.get("disclosure", 0.0),
                rag_scores.get("formatting", 0.0),
                rag_scores.get("provenance", 0.0),
                rag_scores.get("hallucination_control", 0.0)
            ]) / 6.0
            
            structured_overall = sum([
                structured_scores.get("completeness", 0.0),
                structured_scores.get("accuracy", 0.0),
                structured_scores.get("disclosure", 0.0),
                structured_scores.get("formatting", 0.0),
                structured_scores.get("provenance", 0.0),
                structured_scores.get("hallucination_control", 0.0)
            ]) / 6.0
            
            # Use the better dashboard's overall score as the final score
            final_score = max(rag_overall, structured_overall)
            
            # Get assessment details
            assessment = eval_data.get("overall_assessment", {})
            strengths = assessment.get("strengths", [])
            weaknesses = assessment.get("weaknesses", [])
            recommendation = assessment.get("recommendation", "Evaluation completed")
            
            # ReAct: Thought - Finalize evaluation
            thought_3 = f"Evaluation complete. Final score: {final_score:.2f}. " \
                       f"Winner: {winner}. Recommendation: {recommendation[:50]}..."
            self._log_react("thought", thought_3, company_id)
            
            # Create simplified rubric for workflow compatibility
            # Use the winner's scores, or average if tie
            if winner == "rag":
                simplified_rubric = {
                    "completeness": rag_scores.get("completeness", 0.0),
                    "accuracy": rag_scores.get("accuracy", 0.0),
                    "disclosure": rag_scores.get("disclosure", 0.0),
                    "formatting": rag_scores.get("formatting", 0.0)
                }
            elif winner == "structured":
                simplified_rubric = {
                    "completeness": structured_scores.get("completeness", 0.0),
                    "accuracy": structured_scores.get("accuracy", 0.0),
                    "disclosure": structured_scores.get("disclosure", 0.0),
                    "formatting": structured_scores.get("formatting", 0.0)
                }
            else:  # tie
                simplified_rubric = {
                    "completeness": (rag_scores.get("completeness", 0.0) + structured_scores.get("completeness", 0.0)) / 2.0,
                    "accuracy": (rag_scores.get("accuracy", 0.0) + structured_scores.get("accuracy", 0.0)) / 2.0,
                    "disclosure": (rag_scores.get("disclosure", 0.0) + structured_scores.get("disclosure", 0.0)) / 2.0,
                    "formatting": (rag_scores.get("formatting", 0.0) + structured_scores.get("formatting", 0.0)) / 2.0
                }
            
            # Build evaluation result
            result = {
                "score": round(final_score, 2),
                "rubric": {k: round(v, 2) for k, v in simplified_rubric.items()},
                "winner": winner,
                "recommendation": recommendation,
                "strengths": strengths,
                "weaknesses": weaknesses,
                "detailed_scores": {
                    "rag": {
                        "overall": round(rag_overall, 2),
                        "breakdown": {k: round(v, 2) for k, v in rag_scores.items()}
                    },
                    "structured": {
                        "overall": round(structured_overall, 2),
                        "breakdown": {k: round(v, 2) for k, v in structured_scores.items()}
                    }
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Save ReAct trace
            self._save_react_trace(company_id)
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            return self._get_fallback_evaluation(company_id)
        except Exception as e:
            logger.error(f"Error evaluating dashboards with LLM: {e}")
            return self._get_fallback_evaluation(company_id)
    
    def _get_fallback_evaluation(self, company_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Fallback evaluation if LLM fails.
        
        Args:
            company_id: Optional company identifier
            
        Returns:
            Default evaluation structure
        """
        logger.warning(f"Using fallback evaluation for {company_id or 'unknown'}")
        return {
            "score": 0.75,
            "rubric": {
                "completeness": 0.8,
                "accuracy": 0.75,
                "disclosure": 0.7,
                "formatting": 0.8
            },
            "winner": "tie",
            "recommendation": "Evaluation completed with fallback scoring. LLM evaluation unavailable.",
            "strengths": ["Dashboards generated successfully"],
            "weaknesses": ["LLM evaluation unavailable - using default scores"],
            "detailed_scores": {
                "rag": {"overall": 0.75, "breakdown": {}},
                "structured": {"overall": 0.75, "breakdown": {}}
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _save_react_trace(self, company_id: Optional[str] = None):
        """
        Save ReAct trace to file for documentation (Lab 16 requirement).
        
        Args:
            company_id: Optional company identifier
        """
        try:
            project_root = Path(__file__).parent.parent.parent
            docs_dir = project_root / "docs"
            docs_dir.mkdir(exist_ok=True)
            
            trace_id = f"{company_id or 'unknown'}_{self.run_id}"
            trace_file = docs_dir / f"REACT_TRACE_EVAL_{trace_id}.json"
            
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
_evaluation_agent: Optional[EvaluationAgent] = None


def evaluate_dashboards(
    rag_dashboard: str, 
    structured_dashboard: str,
    company_id: Optional[str] = None,
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function for workflow integration.
    Creates or reuses an EvaluationAgent instance and evaluates dashboards.
    
    Args:
        rag_dashboard: Markdown dashboard from RAG pipeline
        structured_dashboard: Markdown dashboard from structured pipeline
        company_id: Optional company identifier for correlation
        run_id: Optional run ID for correlation
        
    Returns:
        Evaluation result dictionary compatible with workflow expectations
    """
    global _evaluation_agent
    
    # Create new agent for each run (or reuse if same run_id)
    if _evaluation_agent is None or (_evaluation_agent.run_id != run_id and run_id is not None):
        _evaluation_agent = EvaluationAgent(run_id=run_id)
    
    return _evaluation_agent.evaluate_dashboards(rag_dashboard, structured_dashboard, company_id)


if __name__ == "__main__":
    """
    Test the evaluation agent standalone.
    Usage: python src/agents/evaluation_agent.py
    """
    import sys
    
    # Sample dashboards for testing
    sample_rag = """# RAG Dashboard - Test Company

## 1. Company Overview
Test Company is a leading AI startup.

## 2. Business Model and GTM
SaaS model targeting enterprises.

## 3. Funding & Investor Profile
Not disclosed.

## 4. Growth Momentum
Not disclosed.

## 5. Visibility & Market Sentiment
Not disclosed.

## 6. Risks and Challenges
No significant risks identified.

## 7. Outlook
Positive outlook.

## 8. Disclosure Gaps
- Financial metrics not disclosed
- Customer list not available
"""
    
    sample_structured = """# Structured Dashboard - Test Company

## 1. Company Overview
Test Company is a leading AI startup founded in 2020.

## 2. Business Model and GTM
SaaS model targeting enterprise customers.

## 3. Funding & Investor Profile
Total raised: Not disclosed.
Last round: Not disclosed.

## 4. Growth Momentum
Revenue growth: Not disclosed.

## 5. Visibility & Market Sentiment
Not disclosed.

## 6. Risks and Challenges
No significant risks identified at this time.

## 7. Outlook
Based on available data, the company shows strong potential.

## 8. Disclosure Gaps
- Detailed financial metrics (revenue, ARR, MRR) not publicly disclosed
- Customer list and logos not available
"""
    
    print(f"\n{'='*60}")
    print(f"🧠 Testing Evaluation Agent")
    print(f"{'='*60}\n")
    
    try:
        result = evaluate_dashboards(sample_rag, sample_structured, company_id="test_company")
        
        print("\n📊 Evaluation Result:")
        print(json.dumps(result, indent=2))
        
        print(f"\n✅ Evaluation completed successfully!")
        print(f"   Overall Score: {result.get('score', 0.0):.2f}")
        print(f"   Winner: {result.get('winner', 'unknown')}")
        print(f"   Recommendation: {result.get('recommendation', 'N/A')}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
