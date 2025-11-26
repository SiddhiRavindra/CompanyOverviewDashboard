# from __future__ import annotations
# # airflow/dags/orbit_agentic_dashboard_dag.py
# """
# Airflow DAG: Agentic Dashboard Generation with Due Diligence Workflow
# Runs Supervisor Agent via Due Diligence Workflow Graph to generate unified dashboards for all companies.

# Airflow 3.x compatible - uses standard imports
# """

# import json
# import os
# import sys
# from datetime import datetime, timedelta
# from pathlib import Path
# from typing import Dict, Any, List

# import pendulum
# from airflow import DAG
# from airflow.decorators import task

# # Airflow mounts
# DATA_DIR = Path("/opt/airflow/data")
# SRC_DIR = Path("/opt/airflow/src")

# # Note: sys.path modification here may not persist in task execution
# # We'll set it again inside each task function to ensure it works


# @task
# def load_companies_with_payloads() -> List[str]:
#     """Get list of companies that have payload files"""
#     payloads_dir = DATA_DIR / "payloads"
    
#     if not payloads_dir.exists():
#         print(f"❌ Payloads directory not found: {payloads_dir}")
#         return []
    
#     companies = sorted([f.stem for f in payloads_dir.glob("abridge.json")])
#     print(f"✓ Found {len(companies)} companies with payloads")
#     return companies


# @task
# def run_complete_workflow(company_id: str) -> Dict[str, Any]:
#     """
#     Run complete Due Diligence Workflow Graph for a company.
    
#     This task:
#     1. Runs Planner node to create due diligence plan
#     2. Runs Data Generator node (via MCP) to generate structured + RAG dashboards
#     3. Runs Evaluator node to score dashboards
#     4. Runs Risk Detector node to check for risks
#     5. Runs Finalize node to create final dashboard
#     6. Saves execution trace and dashboard
#     """
#     import asyncio
#     from dotenv import load_dotenv
    
#     # CRITICAL: Add parent directory to Python path BEFORE any src imports
#     # The import "from src.workflows..." requires /opt/airflow to be in path, not /opt/airflow/src
#     # Airflow tasks run in isolated environments, so we must set path explicitly
#     src_parent = SRC_DIR.parent  # /opt/airflow
#     if str(src_parent) not in sys.path:
#         sys.path.insert(0, str(src_parent))
    
#     # Also ensure src directory itself is in path (for direct imports)
#     if str(SRC_DIR) not in sys.path:
#         sys.path.insert(0, str(SRC_DIR))
    
#     # Load environment
#     env_path = SRC_DIR / '.env'
#     if env_path.exists():
#         load_dotenv(dotenv_path=env_path, override=True)
    
#     # Set GCS credentials if available
#     credentials_relative = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
#     if credentials_relative:
#         credentials_path = Path("/opt/airflow") / credentials_relative
#         if credentials_path.exists():
#             os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_path)
    
#     os.environ['GOOGLE_CLOUD_PROJECT'] = os.getenv('GOOGLE_CLOUD_PROJECT', 'pedashboard')
    
#     # Import workflow components (after path is set)
#     from src.workflows.due_diligence_graph import (
#         planner_node,
#         data_generator_node,
#         evaluator_node,
#         risk_detector_node,
#         finalize_node,
#         save_execution_trace,
#         save_dashboard,
#         WorkflowState,
#     )
#     from datetime import timezone
    
#     async def run_complete_workflow_async():
#         run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
#         initial_state: WorkflowState = {
#             "company_id": company_id,
#             "run_id": run_id,
#             "plan": {},
#             "rag_dashboard": "",
#             "structured_dashboard": "",
#             "dashboard_data": {},
#             "evaluation_result": {},
#             "evaluation_score": 0.0,
#             "risk_detected": False,
#             "risk_details": [],
#             "human_approval": False,  # Auto-approve for now (HITL can be added later)
#             "final_dashboard": "",
#             "messages": []
#         }
        
#         # Run workflow nodes sequentially
#         state = initial_state
#         print(f"[{company_id}] Running Planner node...")
#         state = planner_node(state)
        
#         print(f"[{company_id}] Running Data Generator node...")
#         state = await data_generator_node(state)
        
#         print(f"[{company_id}] Running Evaluator node...")
#         state = evaluator_node(state)
        
#         print(f"[{company_id}] Running Risk Detector node...")
#         state = risk_detector_node(state)
        
#         # Auto-approve for now (HITL can be added later)
#         state["human_approval"] = True
        
#         print(f"[{company_id}] Running Finalize node...")
#         state = finalize_node(state)
        
#         # Save outputs
#         save_execution_trace(state)
#         save_dashboard(state)
        
#         print(f"[{company_id}] ✅ Dashboard finalized and saved")
        
#         return {
#             "success": True,
#             "company_id": company_id,
#             "run_id": state.get("run_id"),
#             "risk_detected": state.get("risk_detected", False),
#             "evaluation_score": state.get("evaluation_score", 0.0),
#             "final_dashboard": state.get("final_dashboard", ""),
#         }
    
#     return asyncio.run(run_complete_workflow_async())


# @task
# def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
#     """Aggregate results from all dashboard generations"""
    
#     results = list(results) if not isinstance(results, list) else results

#     summary = {
#         "total": len(results),
#         "success": len([r for r in results if r.get("success")]),
#         "failed": len([r for r in results if not r.get("success")]),
#         "risk_detected_count": len([r for r in results if r.get("risk_detected")]),
#         "timestamp": datetime.utcnow().isoformat(),
#         "results": results
#     }
    
#     # Save summary
#     summary_file = DATA_DIR / "dashboard_generation_summary.json"
#     summary_file.parent.mkdir(parents=True, exist_ok=True)
#     with open(summary_file, 'w') as f:
#         json.dump(summary, f, indent=2)
    
#     print(f"\n{'='*60}")
#     print(f"📊 Dashboard Generation Summary")
#     print(f"{'='*60}")
#     print(f"  Total: {summary['total']}")
#     print(f"  Success: {summary['success']}")
#     print(f"  Failed: {summary['failed']}")
#     print(f"  Risk Detected: {summary['risk_detected_count']}")
#     print(f"\n💾 Summary saved to: {summary_file}")
    
#     return summary


# # ============================================================================
# # DAG Definition
# # ============================================================================

# with DAG(
#     dag_id="orbit_agentic_dashboard_dag",
#     description="Generate unified dashboards using Due Diligence Workflow Graph",
#     start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
#     schedule="0 4 * * *",  # 4:00 AM daily (after daily_update_dag at 3am)
#     catchup=False,
#     tags=["orbit", "agentic", "dashboard", "mcp"],
#     default_args={
#         "owner": "orbit",
#         "retries": 1,
#         "retry_delay": timedelta(minutes=5)
#     },
# ) as dag_instance:
    
#     # Task 1: Get list of companies
#     companies = load_companies_with_payloads()
    
#     # Task 2: Run complete workflow for each company (dynamic task mapping)
#     workflow_results = run_complete_workflow.expand(company_id=companies)
    
#     # Task 3: Aggregate all results
#     summary = aggregate_results(workflow_results)
    
#     # Set task dependencies
#     companies >> workflow_results >> summary


# airflow/dags/orbit_agentic_dashboard_dag.py
"""
Airflow DAG: Agentic Dashboard Generation with Due Diligence Workflow + HITL
Uses Airflow 3.x native HITL operators for human approval.

Airflow 3.x compatible - uses native HITL operators
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

import pendulum
from airflow import DAG
from airflow.decorators import task
# HITL temporarily disabled - see HITL_ALTERNATIVES.md for options
# from airflow.providers.standard.operators.hitl import HITLOperator


# Airflow mounts
DATA_DIR = Path("/opt/airflow/data")
SRC_DIR = Path("/opt/airflow/src")


@task
def load_companies_with_payloads() -> List[str]:
    """Get list of companies that have payload files"""
    payloads_dir = DATA_DIR / "payloads"
    
    if not payloads_dir.exists():
        print(f"❌ Payloads directory not found: {payloads_dir}")
        return []
    
    companies = sorted([f.stem for f in payloads_dir.glob("b*.json")])
    print(f"✓ Found {len(companies)} companies with payloads")
    return companies


@task
def run_workflow_part1(company_id: str) -> Dict[str, Any]:
    """
    Run Due Diligence Workflow Part 1: Up to Risk Detection
    
    This task:
    1. Runs Planner node to create due diligence plan
    2. Runs Data Generator node (via MCP) to generate structured + RAG dashboards
    3. Runs Evaluator node to score dashboards
    4. Runs Risk Detector node to check for risks
    
    Returns workflow state and risk detection status for HITL decision.
    """
    import asyncio
    from dotenv import load_dotenv
    
    # CRITICAL: Add parent directory to Python path BEFORE any src imports
    src_parent = SRC_DIR.parent  # /opt/airflow
    if str(src_parent) not in sys.path:
        sys.path.insert(0, str(src_parent))
    
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    
    # Load environment
    env_path = SRC_DIR / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
    
    # Set GCS credentials if available
    credentials_relative = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if credentials_relative:
        credentials_path = Path("/opt/airflow") / credentials_relative
        if credentials_path.exists():
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_path)
    
    os.environ['GOOGLE_CLOUD_PROJECT'] = os.getenv('GOOGLE_CLOUD_PROJECT', 'pedashboard')
    
    # Import workflow components (after path is set)
    from src.workflows.due_diligence_graph import (
        planner_node,
        data_generator_node,
        evaluator_node,
        risk_detector_node,
        WorkflowState,
    )
    from datetime import timezone
    
    async def run_workflow_part1_async():
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        initial_state: WorkflowState = {
            "company_id": company_id,
            "run_id": run_id,
            "plan": {},
            "rag_dashboard": "",
            "structured_dashboard": "",
            "dashboard_data": {},
            "evaluation_result": {},
            "evaluation_score": 0.0,
            "risk_detected": False,
            "risk_details": [],
            "human_approval": False,
            "final_dashboard": "",
            "messages": []
        }
        
        # Run workflow nodes sequentially up to risk detection
        state = initial_state
        print(f"[{company_id}] Running Planner node...")
        state = planner_node(state)
        
        print(f"[{company_id}] Running Data Generator node...")
        state = await data_generator_node(state)
        
        print(f"[{company_id}] Running Evaluator node...")
        state = evaluator_node(state)
        
        print(f"[{company_id}] Running Risk Detector node...")
        state = risk_detector_node(state)
        
        # Save state to file for Part 2 to access
        state_file = DATA_DIR / "workflow_states" / f"{company_id}_{run_id}_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        
        #testing purposes
        # state["risk_detected"] = True
        # state["risk_details"] = [
        #     {
        #         "type": "keyword_match",
        #         "severity": "medium",
        #         "description": "Risk keywords found in structured dashboard",
        #         "keywords": ["layoff", "breach", "regulatory", "security incident"]
        #     }
        # ]

        # Convert state to JSON-serializable format
        # If risk detected, human_approval should be None (pending), not False (rejected)
        risk_detected = state.get("risk_detected", False)
        state_dict = {
            "company_id": state["company_id"],
            "run_id": state["run_id"],
            "plan": state["plan"],
            "rag_dashboard": state["rag_dashboard"],
            "structured_dashboard": state["structured_dashboard"],
            "dashboard_data": state["dashboard_data"],
            "evaluation_result": state["evaluation_result"],
            "evaluation_score": state["evaluation_score"],
            "risk_detected": risk_detected,
            "risk_details": state["risk_details"],
            "human_approval": None if risk_detected else True,  # None if risk (pending), True if no risk (auto-approved)
            "final_dashboard": "",
            "messages": state["messages"],
        }
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state_dict, f, indent=2, default=str)
        
        print(f"[{company_id}] ✅ Part 1 complete. State saved to {state_file}")
        print(f"[{company_id}] Risk detected: {state['risk_detected']}")
        
        return {
            "success": True,
            "company_id": company_id,
            "run_id": run_id,
            "risk_detected": state["risk_detected"],
            "risk_details": state["risk_details"],
            "evaluation_score": state["evaluation_score"],
            "state_file": str(state_file),
        }
    
    return asyncio.run(run_workflow_part1_async())


@task
def check_if_hitl_needed(workflow_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if HITL is needed based on risk detection.
    Returns decision for conditional branching.
    """
    # Safety check: workflow_result should be a single dict, not a list
    if isinstance(workflow_result, list):
        raise ValueError(
            f"workflow_result is a list instead of a dict. This indicates a mapping issue. "
            f"workflow_result type: {type(workflow_result)}, length: {len(workflow_result)}"
        )
    
    if not isinstance(workflow_result, dict):
        raise ValueError(f"workflow_result must be a dict, got {type(workflow_result)}: {workflow_result}")
    
    risk_detected = workflow_result.get("risk_detected", False)
    
    return {
        "needs_hitl": risk_detected,
        "workflow_result": workflow_result,
    }

def _execute_workflow_part2_logic(company_id: str, workflow_state: Dict[str, Any], approval_result: Optional[str] = "Approve") -> Dict[str, Any]:
    """
    Helper function to execute workflow part 2 logic.
    This can be called directly from within tasks (not as a task itself).
    """
    import asyncio
    import json
    from dotenv import load_dotenv
    
    # CRITICAL: Add parent directory to Python path BEFORE any src imports
    src_parent = SRC_DIR.parent  # /opt/airflow
    if str(src_parent) not in sys.path:
        sys.path.insert(0, str(src_parent))
    
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    
    # Load environment
    env_path = SRC_DIR / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
    
    # Set GCS credentials if available
    credentials_relative = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if credentials_relative:
        credentials_path = Path("/opt/airflow") / credentials_relative
        if credentials_path.exists():
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_path)
    
    os.environ['GOOGLE_CLOUD_PROJECT'] = os.getenv('GOOGLE_CLOUD_PROJECT', 'pedashboard')
    
    # Import workflow components (after path is set)
    from src.workflows.due_diligence_graph import (
        finalize_node,
        save_execution_trace,
        save_dashboard,
        WorkflowState,
    )
    
    # Load state from file
    state_file = workflow_state.get("state_file")
    if not state_file or not Path(state_file).exists():
        raise ValueError(f"State file not found: {state_file}")
    
    with open(state_file, 'r', encoding='utf-8') as f:
        state_dict = json.load(f)
    
    # Apply HITL approval result
    # approval_result can be: "Approve", "Reject", or None (pending)
    if approval_result is None:
        # Pending approval - don't set human_approval, let it stay as None/False
        approved = None
        print(f"[{company_id}] ⚠️ Risk detected - saving to pending_approval (not yet approved)")
    elif approval_result == "Approve":
        approved = True
    else:
        # Rejected
        approved = False
        print(f"[{company_id}] ❌ HITL rejected - dashboard will not be finalized")
        return {
            "success": False,
            "company_id": company_id,
            "run_id": state_dict.get("run_id"),
            "reason": "HITL rejected",
            "approval_result": approval_result,
        }
    
    # Only set human_approval if explicitly approved/rejected (not None/pending)
    if approved is not None:
        state_dict["human_approval"] = approved
    
    # Convert back to WorkflowState
    state: WorkflowState = {
        "company_id": state_dict["company_id"],
        "run_id": state_dict["run_id"],
        "plan": state_dict["plan"],
        "rag_dashboard": state_dict["rag_dashboard"],
        "structured_dashboard": state_dict["structured_dashboard"],
        "dashboard_data": state_dict["dashboard_data"],
        "evaluation_result": state_dict["evaluation_result"],
        "evaluation_score": state_dict["evaluation_score"],
        "risk_detected": state_dict["risk_detected"],
        "risk_details": state_dict["risk_details"],
        # Preserve human_approval: use approved if set, otherwise keep what's in state_dict (could be None, False, or True)
        "human_approval": approved if approved is not None else state_dict.get("human_approval"),
        "final_dashboard": "",
        "messages": state_dict["messages"],
    }
    
    if approved is True:
        print(f"[{company_id}] ✅ HITL approved - proceeding to finalize")
    elif approved is None:
        print(f"[{company_id}] ⚠️ Pending approval - proceeding to finalize (will save to pending_approval)")
    print(f"[{company_id}] Running Finalize node...")
    state = finalize_node(state)
    
    # Save outputs
    save_execution_trace(state)
    save_dashboard(state)
    
    print(f"[{company_id}] ✅ Dashboard finalized and saved")
    
    return {
        "success": True,
        "company_id": company_id,
        "run_id": state.get("run_id"),
        "risk_detected": state.get("risk_detected", False),
        "evaluation_score": state.get("evaluation_score", 0.0),
        "human_approval": approved,
        "final_dashboard": state.get("final_dashboard", ""),
    }


@task
def run_workflow_part2(company_id: str, workflow_state: Dict[str, Any], approval_result: str = "Approve") -> Dict[str, Any]:
    """
    Run Due Diligence Workflow Part 2: Finalize after HITL approval
    
    This task:
    1. Loads workflow state from Part 1
    2. Applies HITL approval result
    3. Runs Finalize node to create final dashboard
    4. Saves execution trace and dashboard
    """
    return _execute_workflow_part2_logic(company_id, workflow_state, approval_result)


@task
def auto_approve_no_risk(workflow_state: Dict[str, Any]) -> Dict[str, Any]:
    """Auto-approve when no risk is detected"""
    return {
        "approved": True,
        "status": "auto_approved",
        "workflow_state": workflow_state,
    }


@task
def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate results from all dashboard generations"""
    
    results = list(results) if not isinstance(results, list) else results

    summary = {
        "total": len(results),
        "success": len([r for r in results if r.get("success")]),
        "failed": len([r for r in results if not r.get("success")]),
        "risk_detected_count": len([r for r in results if r.get("risk_detected")]),
        "timestamp": datetime.utcnow().isoformat(),
        "results": results
    }
    
    # Save summary
    summary_file = DATA_DIR / "dashboard_generation_summary.json"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"📊 Dashboard Generation Summary")
    print(f"{'='*60}")
    print(f"  Total: {summary['total']}")
    print(f"  Success: {summary['success']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Risk Detected: {summary['risk_detected_count']}")
    print(f"\n💾 Summary saved to: {summary_file}")
    
    return summary


# ============================================================================
# DAG Definition
# ============================================================================

with DAG(
    dag_id="orbit_agentic_dashboard_dag",
    description="Generate unified dashboards using Due Diligence Workflow Graph with native HITL",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    schedule="0 4 * * *",  # 4:00 AM daily (after daily_update_dag at 3am)
    catchup=False,
    tags=["orbit", "agentic", "dashboard", "mcp", "hitl"],
    default_args={
        "owner": "orbit",
        "retries": 1,
        "retry_delay": timedelta(minutes=1)
    },
) as dag_instance:
    
    # Task 1: Get list of companies
    companies = load_companies_with_payloads()
    
    # Task 2: Run workflow Part 1 (up to risk detection)
    workflow_part1_results = run_workflow_part1.expand(company_id=companies)
    
    # Task 3: Check if HITL is needed
    hitl_check_results = check_if_hitl_needed.expand(workflow_result=workflow_part1_results)
    
    # HITL TEMPORARILY DISABLED - Auto-approving all workflows
    # See HITL_ALTERNATIVES.md for alternative solutions
    # The native HITLOperator is not resuming after approval in Airflow 3.x
    @task
    def auto_approve_all(hitl_check_result: Dict[str, Any]) -> Dict[str, Any]:
        """Temporarily auto-approve all workflows (HITL disabled)
        
        Args:
            hitl_check_result: The result from check_if_hitl_needed task (mapped result)
                Format: {"needs_hitl": bool, "workflow_result": {...}}
        """
        # Safety check: if hitl_check_result is a list, something went wrong
        if isinstance(hitl_check_result, list):
            raise ValueError(
                f"hitl_check_result is a list instead of a dict. This indicates a mapping issue. "
                f"hitl_check_result type: {type(hitl_check_result)}, length: {len(hitl_check_result) if isinstance(hitl_check_result, list) else 'N/A'}"
            )
        
        # Extract workflow_result from hitl_check_result
        # hitl_check_result should be: {"needs_hitl": bool, "workflow_result": {...}}
        if not isinstance(hitl_check_result, dict):
            raise ValueError(f"hitl_check_result must be a dict, got {type(hitl_check_result)}: {hitl_check_result}")
        
        workflow_result = hitl_check_result.get('workflow_result')
        
        # If workflow_result is not in hitl_check_result, use hitl_check_result itself
        if workflow_result is None:
            workflow_result = hitl_check_result
        
        # Safety check: workflow_result should be a dict, not a list
        if isinstance(workflow_result, list):
            raise ValueError(
                f"workflow_result is a list instead of a dict. hitl_check_result keys: {hitl_check_result.keys()}, "
                f"workflow_result type: {type(workflow_result)}, length: {len(workflow_result)}"
            )
        
        if not isinstance(workflow_result, dict):
            raise ValueError(f"workflow_result must be a dict, got {type(workflow_result)}: {workflow_result}")
        
        company_id = workflow_result.get('company_id')
        risk_detected = workflow_result.get('risk_detected', False)
        
        if not company_id:
            raise ValueError(
                f"Could not get company_id from workflow_result. "
                f"workflow_result keys: {workflow_result.keys()}, "
                f"hitl_check_result: {hitl_check_result}"
            )
        
        if risk_detected:
            print(f"[{company_id}] ⚠️ Risk detected but auto-approving (HITL disabled)")
        else:
            print(f"[{company_id}] ✅ No risk detected - auto-approving")
        
        return {
            "approved": True,
            "status": "auto_approved",
            "workflow_result": workflow_result,
        }
    
    auto_approve_all_results = auto_approve_all.expand(hitl_check_result=hitl_check_results)
    
    # Task 4: Auto-approve for companies without risk (original logic)
    auto_approve_results = auto_approve_no_risk.expand(workflow_state=workflow_part1_results)
    
    # Task 5: Finalize workflow (for all companies - HITL disabled)
    @task
    def finalize_workflow(approval_data: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize workflow after auto-approval or pending approval
        
        Args:
            approval_data: The approval data from auto_approve_all task (mapped result)
        """
        # Extract workflow_result from approval_data
        # approval_data is the output from auto_approve_all: {"approved": True, "status": "auto_approved", "workflow_result": {...}}
        workflow_result = approval_data.get('workflow_result', {}) if isinstance(approval_data, dict) else approval_data
        
        # Handle case where approval_data might be the workflow_result directly
        if not isinstance(workflow_result, dict):
            workflow_result = approval_data if isinstance(approval_data, dict) else {}
        
        # Safety check: if workflow_result is a list, something went wrong upstream
        if isinstance(workflow_result, list):
            raise ValueError(
                f"workflow_result is a list instead of a dict. This indicates a mapping issue. "
                f"approval_data structure: {type(approval_data)}, keys: {approval_data.keys() if isinstance(approval_data, dict) else 'N/A'}"
            )
        
        company_id = workflow_result.get('company_id')
        
        if not company_id:
            raise ValueError(
                f"Could not get company_id from approval_data. "
                f"approval_data type: {type(approval_data)}, "
                f"workflow_result type: {type(workflow_result)}, "
                f"workflow_result keys: {workflow_result.keys() if isinstance(workflow_result, dict) else 'N/A'}, "
                f"approval_data: {approval_data}"
            )
        
        # Check if risk was detected
        risk_detected = workflow_result.get('risk_detected', False)
        
        # If risk detected, don't approve - let it go to pending_approval
        # If no risk, auto-approve
        if risk_detected:
            print(f"[{company_id}] ⚠️ Risk detected - NOT auto-approving, will save to pending_approval")
            # Pass None to indicate pending approval (not approved, not rejected)
            approval_result = None
        else:
            print(f"[{company_id}] ✅ No risk - auto-approving")
            approval_result = "Approve"
        
        # Call the helper function directly
        return _execute_workflow_part2_logic(company_id, workflow_result, approval_result)
    
    finalize_results = finalize_workflow.expand(approval_data=auto_approve_all_results)
    
    # Task 6: Aggregate all results
    summary = aggregate_results([])  # Placeholder - needs proper result collection
    
    # Set task dependencies
    # Simplified: workflow_part1 -> hitl_check -> auto_approve_all -> finalize -> summary
    # Also: workflow_part1 -> auto_approve_no_risk -> finalize_auto_approved -> summary
    
    companies >> workflow_part1_results >> [hitl_check_results, auto_approve_results]
    hitl_check_results >> auto_approve_all_results >> finalize_results >> summary
    # Note: auto_approve_results path is handled by the main flow above
