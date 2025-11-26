"""
Tool: Risk Logger

Logs high-risk events (layoffs, breaches, regulatory issues, etc.) for human review.
Creates an audit trail that triggers HITL (Human-in-the-Loop) workflow.
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, HttpUrl

# Define high-risk event types (aligned with Event model where applicable)
RiskType = Literal[
    "layoff",                    # Workforce reduction
    "security_incident",         # Data breach, security breach
    "regulatory",                # Regulatory violations, investigations
    "financial_distress",        # Cash flow issues, funding problems
    "leadership_crisis",         # Key executive departure, scandal
    "legal_action",              # Lawsuits, legal disputes
    "product_recall",            # Product safety issues
    "market_disruption",         # Major market changes affecting business
    "other"                      # Catch-all for other high-risk events
]


class RiskSignal(BaseModel):
    """Structured description of a high-risk event signal."""
    company_id: str
    occurred_on: date
    description: str
    source_url: HttpUrl
    risk_type: RiskType
    severity: Literal["low", "medium", "high", "critical"] = "medium"


async def report_risk_signal(signal_data: RiskSignal) -> bool:
    """
    Tool: report_risk_signal

    Record a high-risk event for the given company.
    This creates a persistent audit trail that can trigger HITL (Human-in-the-Loop) review.

    Args:
        signal_data: RiskSignal with company_id, occurred_on, description, 
                    source_url, risk_type, and optional severity.

    Returns:
        True if logging succeeded, False otherwise.
        Never raises exceptions - graceful degradation on errors.
    """
    try:
        # Create risk signals directory if it doesn't exist
        # From: src/tools/risk_logger.py -> go up 2 levels to project root
        project_root = Path(__file__).parent.parent.parent
        risk_log_dir = project_root / "data" / "risk_signals"
        risk_log_dir.mkdir(parents=True, exist_ok=True)
        
        # Append to JSONL file (one JSON object per line)
        risk_log_file = risk_log_dir / "risk_signals.jsonl"
        
        # Create log entry with timestamp
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "company_id": signal_data.company_id,
            "occurred_on": signal_data.occurred_on.isoformat(),
            "description": signal_data.description,
            "source_url": str(signal_data.source_url),
            "risk_type": signal_data.risk_type,
            "severity": signal_data.severity,
        }
        
        # Append to file (append mode ensures we never overwrite)
        with open(risk_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        return True
        
    except Exception:
        # Graceful degradation: return False on any error
        # Don't expose internal errors to the client
        return False


# Convenience wrapper for backward compatibility
async def report_layoff_signal(signal_data: "LayoffSignal") -> bool:
    """
    Tool: report_layoff_signal (convenience wrapper)

    Backward-compatible wrapper for layoff-specific signals.
    Converts LayoffSignal to RiskSignal and calls report_risk_signal.

    Args:
        signal_data: LayoffSignal with company_id, occurred_on, description, and source_url.

    Returns:
        True if logging succeeded, False otherwise.
    """
    risk_signal = RiskSignal(
        company_id=signal_data.company_id,
        occurred_on=signal_data.occurred_on,
        description=signal_data.description,
        source_url=signal_data.source_url,
        risk_type="layoff",
        severity="medium"
    )
    return await report_risk_signal(risk_signal)


# Keep old class for backward compatibility
class LayoffSignal(BaseModel):
    """Backward-compatible class for layoff signals. Use RiskSignal for new code."""
    company_id: str
    occurred_on: date
    description: str
    source_url: HttpUrl


# ========== OLD CODE (COMMENTED FOR REFERENCE) ==========
# 
# class LayoffSignal(BaseModel):
#     """Structured description of a potential layoff / risk signal."""
#     company_id: str
#     occurred_on: date
#     description: str
#     source_url: HttpUrl
#
#
# async def report_layoff_signal(signal_data: LayoffSignal) -> bool:
#     """
#     Tool: report_layoff_signal
#
#     Record a high-risk layoff / workforce reduction / negative event for the given company.
#     This creates a persistent audit trail that can trigger HITL (Human-in-the-Loop) review.
#
#     Args:
#         signal_data: LayoffSignal with company_id, occurred_on, description, and source_url.
#
#     Returns:
#         True if logging succeeded, False otherwise.
#         Never raises exceptions - graceful degradation on errors.
#     """
#     try:
#         # Create risk signals directory if it doesn't exist
#         # From: src/tools/risk_logger.py -> go up 2 levels to project root
#         project_root = Path(__file__).parent.parent.parent
#         risk_log_dir = project_root / "data" / "risk_signals"
#         risk_log_dir.mkdir(parents=True, exist_ok=True)
#         
#         # Append to JSONL file (one JSON object per line)
#         risk_log_file = risk_log_dir / "risk_signals.jsonl"
#         
#         # Create log entry with timestamp
#         log_entry = {
#             "timestamp": datetime.now(timezone.utc).isoformat(),
#             "company_id": signal_data.company_id,
#             "occurred_on": signal_data.occurred_on.isoformat(),
#             "description": signal_data.description,
#             "source_url": str(signal_data.source_url),
#         }
#         
#         # Append to file (append mode ensures we never overwrite)
#         with open(risk_log_file, 'a', encoding='utf-8') as f:
#             f.write(json.dumps(log_entry) + '\n')
#         
#         return True
#         
#     except Exception:
#         # Graceful degradation: return False on any error
#         # Don't expose internal errors to the client
#         return False