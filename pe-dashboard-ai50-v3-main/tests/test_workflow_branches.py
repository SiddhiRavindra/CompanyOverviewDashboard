"""
Unit tests for Lab 17: Workflow Branch Logic

Tests the conditional branching in the due diligence workflow graph:
- Risk detected → HITL branch
- No risk → Auto-approve branch
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.workflows.due_diligence_graph import (
    should_require_approval,
    risk_detector_node,
    WorkflowState,
    build_workflow
)


def test_should_require_approval_with_risk():
    """Test conditional routing returns 'hitl' when risk is detected."""
    state: WorkflowState = {
        "company_id": "test-company",
        "run_id": "test_run",
        "plan": {},
        "rag_dashboard": "",
        "structured_dashboard": "",
        "dashboard_data": {},
        "evaluation_result": {},
        "evaluation_score": 0.0,
        "risk_detected": True,  # Risk detected
        "risk_details": [],
        "human_approval": False,
        "final_dashboard": "",
        "messages": []
    }
    
    result = should_require_approval(state)
    assert result == "hitl"


def test_should_require_approval_no_risk():
    """Test conditional routing returns 'finalize' when no risk is detected."""
    state: WorkflowState = {
        "company_id": "test-company",
        "run_id": "test_run",
        "plan": {},
        "rag_dashboard": "",
        "structured_dashboard": "",
        "dashboard_data": {},
        "evaluation_result": {},
        "evaluation_score": 0.0,
        "risk_detected": False,  # No risk
        "risk_details": [],
        "human_approval": False,
        "final_dashboard": "",
        "messages": []
    }
    
    result = should_require_approval(state)
    assert result == "finalize"


def test_risk_detector_node_detects_risk():
    """Test risk detector node detects risk keywords and sets risk_detected=True."""
    state: WorkflowState = {
        "company_id": "test-company",
        "run_id": "test_run",
        "plan": {},
        "rag_dashboard": "",
        "structured_dashboard": "# Dashboard\n\nCompany had a major layoff in 2024.",  # Contains "layoff"
        "dashboard_data": {},
        "evaluation_result": {},
        "evaluation_score": 0.0,
        "risk_detected": False,
        "risk_details": [],
        "human_approval": False,
        "final_dashboard": "",
        "messages": []
    }
    
    result_state = risk_detector_node(state)
    
    assert result_state["risk_detected"] is True
    assert len(result_state["risk_details"]) > 0
    assert result_state["risk_details"][0]["type"] == "keyword_match"
    assert "risk_evaluated" in [msg["action"] for msg in result_state["messages"]]


def test_risk_detector_node_no_risk():
    """Test risk detector node does not detect risk when keywords are absent."""
    state: WorkflowState = {
        "company_id": "test-company",
        "run_id": "test_run",
        "plan": {},
        "rag_dashboard": "",
        "structured_dashboard": "# Dashboard\n\nCompany is growing rapidly with strong revenue.",  # No risk keywords
        "dashboard_data": {},
        "evaluation_result": {},
        "evaluation_score": 0.0,
        "risk_detected": False,
        "risk_details": [],
        "human_approval": False,
        "final_dashboard": "",
        "messages": []
    }
    
    result_state = risk_detector_node(state)
    
    assert result_state["risk_detected"] is False
    assert len(result_state["risk_details"]) == 0
    assert "risk_evaluated" in [msg["action"] for msg in result_state["messages"]]


def test_risk_detector_node_detects_multiple_keywords():
    """Test risk detector detects various risk keywords."""
    risk_keywords = ["layoff", "breach", "regulatory", "security incident"]
    
    for keyword in risk_keywords:
        state: WorkflowState = {
            "company_id": "test-company",
            "run_id": "test_run",
            "plan": {},
            "rag_dashboard": "",
            "structured_dashboard": f"# Dashboard\n\nCompany experienced a {keyword} recently.",
            "dashboard_data": {},
            "evaluation_result": {},
            "evaluation_score": 0.0,
            "risk_detected": False,
            "risk_details": [],
            "human_approval": False,
            "final_dashboard": "",
            "messages": []
        }
        
        result_state = risk_detector_node(state)
        assert result_state["risk_detected"] is True, f"Should detect risk for keyword: {keyword}"


def test_risk_detector_node_case_insensitive():
    """Test risk detector is case-insensitive."""
    state: WorkflowState = {
        "company_id": "test-company",
        "run_id": "test_run",
        "plan": {},
        "rag_dashboard": "",
        "structured_dashboard": "# Dashboard\n\nCompany had a LAYOFF in 2024.",  # Uppercase
        "dashboard_data": {},
        "evaluation_result": {},
        "evaluation_score": 0.0,
        "risk_detected": False,
        "risk_details": [],
        "human_approval": False,
        "final_dashboard": "",
        "messages": []
    }
    
    result_state = risk_detector_node(state)
    assert result_state["risk_detected"] is True


def test_workflow_graph_structure():
    """Test that workflow graph is built correctly with all nodes."""
    workflow = build_workflow()
    
    # Check that all required nodes exist
    nodes = workflow.nodes
    assert "planner" in nodes
    assert "data_generator" in nodes
    assert "evaluator" in nodes
    assert "risk_detector" in nodes
    assert "hitl" in nodes
    assert "finalize" in nodes


@patch('src.workflows.due_diligence_graph.planner_node')
@patch('src.workflows.due_diligence_graph.data_generator_node')
@patch('src.workflows.due_diligence_graph.evaluator_node')
@patch('src.workflows.due_diligence_graph.risk_detector_node')
@patch('src.workflows.due_diligence_graph.finalize_node')
def test_workflow_no_risk_branch(mock_finalize, mock_risk, mock_eval, mock_data, mock_planner):
    """Test workflow takes no-risk branch (skips HITL)."""
    # Mock nodes to return states
    initial_state: WorkflowState = {
        "company_id": "test-company",
        "run_id": "test_run",
        "plan": {},
        "rag_dashboard": "",
        "structured_dashboard": "Safe dashboard content",
        "dashboard_data": {},
        "evaluation_result": {},
        "evaluation_score": 0.8,
        "risk_detected": False,  # No risk
        "risk_details": [],
        "human_approval": False,
        "final_dashboard": "",
        "messages": []
    }
    
    mock_planner.return_value = initial_state
    mock_data.return_value = initial_state
    mock_eval.return_value = initial_state
    mock_risk.return_value = initial_state
    mock_finalize.return_value = initial_state
    
    workflow = build_workflow()
    
    # Test conditional routing
    routing_result = should_require_approval(initial_state)
    assert routing_result == "finalize"  # Should skip HITL


@patch('src.workflows.due_diligence_graph.planner_node')
@patch('src.workflows.due_diligence_graph.data_generator_node')
@patch('src.workflows.due_diligence_graph.evaluator_node')
@patch('src.workflows.due_diligence_graph.risk_detector_node')
@patch('src.workflows.due_diligence_graph.human_approval_node')
@patch('src.workflows.due_diligence_graph.finalize_node')
def test_workflow_risk_branch(mock_finalize, mock_hitl, mock_risk, mock_eval, mock_data, mock_planner):
    """Test workflow takes risk branch (goes through HITL)."""
    # Mock nodes to return states
    initial_state: WorkflowState = {
        "company_id": "test-company",
        "run_id": "test_run",
        "plan": {},
        "rag_dashboard": "",
        "structured_dashboard": "Dashboard mentions layoff",
        "dashboard_data": {},
        "evaluation_result": {},
        "evaluation_score": 0.8,
        "risk_detected": True,  # Risk detected
        "risk_details": [{"type": "layoff", "severity": "high"}],
        "human_approval": False,
        "final_dashboard": "",
        "messages": []
    }
    
    mock_planner.return_value = initial_state
    mock_data.return_value = initial_state
    mock_eval.return_value = initial_state
    mock_risk.return_value = initial_state
    mock_hitl.return_value = initial_state
    mock_finalize.return_value = initial_state
    
    workflow = build_workflow()
    
    # Test conditional routing
    routing_result = should_require_approval(initial_state)
    assert routing_result == "hitl"  # Should go through HITL


def test_risk_detector_preserves_existing_risk_details():
    """Test risk detector appends to existing risk details rather than replacing."""
    state: WorkflowState = {
        "company_id": "test-company",
        "run_id": "test_run",
        "plan": {},
        "rag_dashboard": "",
        "structured_dashboard": "# Dashboard\n\nCompany had a layoff and security breach.",
        "dashboard_data": {},
        "evaluation_result": {},
        "evaluation_score": 0.0,
        "risk_detected": False,
        "risk_details": [
            {"type": "existing_risk", "description": "Pre-existing risk"}
        ],
        "human_approval": False,
        "final_dashboard": "",
        "messages": []
    }
    
    result_state = risk_detector_node(state)
    
    # Should have both existing risk and new detected risk
    assert len(result_state["risk_details"]) >= 2
    assert any(r["type"] == "existing_risk" for r in result_state["risk_details"])
    assert any(r["type"] == "keyword_match" for r in result_state["risk_details"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])