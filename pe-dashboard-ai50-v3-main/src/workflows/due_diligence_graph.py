"""
Lab 17 - Supervisory Workflow Pattern (Graph-based)
Due Diligence Workflow using LangGraph with conditional branching
Integrates with Assignment 4 real company data
"""

from typing import TypedDict, Annotated, Literal, Optional, Dict, List
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import json
import logging
from datetime import datetime, timezone
import sys
import os
from pathlib import Path

# Fix import paths - add project root to Python path
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import actual tools from previous labs
try:
    from src.tools.payload_tool import get_latest_structured_payload
    from src.tools.rag_tool import rag_search_company
    from src.tools.risk_logger import report_risk_signal
except ImportError as e:
    logger.warning(f"Could not import tools: {e}. Some functionality may be limited.")
    get_latest_structured_payload = None
    rag_search_company = None
    report_risk_signal = None

# Import dashboard generators
try:
    from src.dashboard_generator import generate_dashboard, generate_dashboard_from_rag
    from src.structured_pipeline import load_payload
except ImportError as e:
    logger.warning(f"Could not import dashboard generators: {e}")
    generate_dashboard = None
    generate_dashboard_from_rag = None
    load_payload = None

# Import GCS storage client (optional)
try:
    from src.storage.gcs_client import DashboardStorage
    GCS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import GCS client: {e}. Dashboards will be saved locally only.")
    DashboardStorage = None
    GCS_AVAILABLE = False


# ============================================================
# MCP HTTP CLIENT INTEGRATION (Lab 17 / 18)
# ============================================================

# We use a lightweight HTTP client to talk to the MCP server defined in
# src/server/mcp_server.py using the configuration in mcp_server.config.json.

try:
    import httpx  # type: ignore
except ImportError:  # pragma: no cover - httpx is in requirements.txt
    httpx = None
    logger.warning("[MCP] httpx is not installed; MCP tools will be disabled.")


class MCPHttpClient:
    """Simple HTTP client for calling MCP tool endpoints."""

    def __init__(self, config_path: Path):
        self.enabled = False
        self.base_url: Optional[str] = None
        self.timeout: float = 60.0

        if httpx is None:
            logger.warning("[MCP] Cannot initialize MCP client without httpx.")
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            server_cfg = cfg.get("mcp_server", {})
            # Check environment variable first (set by Docker Compose), then config file
            self.base_url = os.getenv('MCP_SERVER_URL') or server_cfg.get("base_url", "http://mcp-server:8100")
            self.timeout = float(server_cfg.get("timeout", 60))

            self.enabled = True
            logger.info(f"[MCP] MCP client configured for base_url={self.base_url}")
        except FileNotFoundError:
            logger.warning(f"[MCP] MCP config file not found at {config_path}; MCP tools disabled.")
        except Exception as e:
            logger.warning(f"[MCP] Failed to initialize MCP client: {e}")

    async def call_tool(self, tool_name: str, payload: Dict) -> Dict:
        """Call an MCP tool endpoint and return JSON response."""
        if not self.enabled or httpx is None or self.base_url is None:
            raise RuntimeError("MCP client is not enabled or httpx is missing.")

        url = f"{self.base_url}/tool/{tool_name}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()


# Create a global MCP client instance if possible
_mcp_config_path = _project_root / "src" / "server" / "mcp_server.config.json"
try:
    mcp_client: Optional[MCPHttpClient] = MCPHttpClient(_mcp_config_path)
    MCP_AVAILABLE: bool = bool(mcp_client and mcp_client.enabled)
except Exception as e:  # pragma: no cover - very defensive
    logger.warning(f"[MCP] MCP client initialization failed: {e}")
    mcp_client = None
    MCP_AVAILABLE = False

# Import agents - REQUIRED (no fallbacks)
try:
    from src.agents.planner_agent import plan_due_diligence
    from src.agents.evaluation_agent import evaluate_dashboards
except ImportError:
    # Try relative imports if src. doesn't work
    try:
        from agents.planner_agent import plan_due_diligence
        from agents.evaluation_agent import evaluate_dashboards
    except ImportError as e:
        logger.error(f"Could not import agents: {e}")
        raise


# ============================================================
# WORKFLOW STATE
# ============================================================

class WorkflowState(TypedDict):
    """Shared workflow state for the due diligence process"""
    company_id: str
    run_id: str
    plan: Dict
    rag_dashboard: str
    structured_dashboard: str
    dashboard_data: Dict
    evaluation_result: Dict
    evaluation_score: float
    risk_detected: bool
    risk_details: List[Dict]
    human_approval: bool
    final_dashboard: str
    messages: List[Dict]


# ============================================================
# COMPANY DATA LOADER - Uses Real Assignment 4 Data Sources
# ============================================================

class CompanyDataLoader:
    """Loads company data from actual Assignment 4 payloads and structured data"""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize loader with project root path"""
        if project_root is None:
            # Assume we're in src/workflows/, go up 2 levels to project root
            self.project_root = Path(__file__).parent.parent.parent
        else:
            self.project_root = Path(project_root)

        # Data directories consistent with Assignment 4
        self.payloads_dir = self.project_root / "data" / "payloads"
        self.structured_dir = self.project_root / "data" / "structured"

    def get_available_company_ids(self) -> List[str]:
        """Return list of company_ids for which we have data"""
        ids = set()

        if self.payloads_dir.exists():
            for f in self.payloads_dir.glob("*.json"):
                ids.add(f.stem)

        if self.structured_dir.exists():
            for f in self.structured_dir.glob("*.json"):
                ids.add(f.stem)

        return sorted(ids)

    def load_company_payload(self, company_id: str) -> Optional[Dict]:
        """
        Load company payload from payloads and/or structured data.
        Returns a dictionary with normalized keys for downstream dashboards.
        """
        payload = None
        structured = None

        # Load payload file (Assignment 4 output format)
        payload_path = self.payloads_dir / f"{company_id}.json"
        if payload_path.exists():
            try:
                with open(payload_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception as e:
                logger.warning(f"Error loading payload for {company_id}: {e}")

        # Load structured data file if available
        structured_path = self.structured_dir / f"{company_id}.json"
        if structured_path.exists():
            try:
                with open(structured_path, "r", encoding="utf-8") as f:
                    structured = json.load(f)
            except Exception as e:
                logger.warning(f"Error loading structured data for {company_id}: {e}")

        if not payload and not structured:
            return None

        # Normalize into a single dict
        company_data: Dict = {
            "company_id": company_id,
            "name": None,
            "website": None,
            "industry": None,
            "hq_city": None,
            "hq_state": None,
            "hq_country": None,
            "founded": None,
            "funding": None,
            "valuation": None,
            "last_round": None,
            "revenue_model": None,
            "target_market": None,
            "revenue_growth": None,
            "employee_count": None,
            "has_risk": False,
            "events": [],
            "payload": None,  # raw payload (if available)
        }

        # Extract from structured if available
        if structured:
            company_data["name"] = structured.get("name") or structured.get("company_name")
            company_data["website"] = structured.get("website")
            company_data["industry"] = structured.get("industry")
            company_data["hq_city"] = structured.get("hq_city")
            company_data["hq_state"] = structured.get("hq_state")
            company_data["hq_country"] = structured.get("hq_country")
            company_data["founded"] = structured.get("founded")
            company_data["funding"] = structured.get("funding")
            company_data["valuation"] = structured.get("valuation")
            company_data["last_round"] = structured.get("last_round")
            company_data["revenue_model"] = structured.get("revenue_model")
            company_data["target_market"] = structured.get("target_market")
            company_data["revenue_growth"] = structured.get("revenue_growth")
            company_data["employee_count"] = structured.get("employee_count")
            company_data["events"] = structured.get("events", [])

        # Attach raw payload object for richer extraction
        if payload:
            company_data["payload"] = payload
            # Try to infer risk from payload events
            events = payload.get("events") or []
            if events:
                company_data["events"] = events
                company_data["has_risk"] = any(
                    e.get("event_type") in ["layoff", "security_incident", "regulatory", "legal_action"]
                    for e in events
                )

        return company_data


# ============================================================
# WORKFLOW NODES
# ============================================================

def planner_node(state: WorkflowState) -> WorkflowState:
    """
    Planner Node: Calls planner_agent.plan_due_diligence() to get a plan.
    """
    logger.info(f"[Planner] Planning due diligence for company_id={state['company_id']}")
    # We pass run_id for ReAct trace correlation
    plan = plan_due_diligence(state["company_id"], run_id=state.get("run_id"))
    print("PLAN:", plan)

    state["plan"] = plan
    state["messages"].append({
        "node": "planner",
        "action": "plan_created",
        "details": plan
    })

    logger.info(f"[Planner] Plan created with {len(plan.get('steps', []))} steps")
    return state


async def data_generator_node(state: WorkflowState) -> WorkflowState:
    """
    Data Generator Node (Lab 17):
    - Loads REAL company data from Assignment 4 outputs
    - Prefers MCP dashboard tools for generation
    - Falls back to local Python tools if MCP is unavailable
    """
    logger.info(f"[DataGenerator] Generating dashboards for: {state['company_id']}")

    loader = CompanyDataLoader()
    company_id = state["company_id"]

    # Load company metadata / payload from Assignment 4
    company_data = loader.load_company_payload(company_id)
    risks_found: List[Dict[str, str]] = []

    structured_from_mcp: Optional[str] = None
    rag_from_mcp: Optional[str] = None

    # ------------------------------------------------------------
    # 1) Call MCP tools (preferred path)
    # ------------------------------------------------------------
    if MCP_AVAILABLE and mcp_client is not None:
        logger.info("[DataGenerator] Using MCP tools for dashboard generation")

        # Structured dashboard via MCP
        try:
            struct_resp = await mcp_client.call_tool(
                "generate_structured_dashboard",
                {"company_id": company_id}
            )
            if struct_resp.get("success"):
                structured_from_mcp = struct_resp.get("result") or ""
                logger.info("[DataGenerator] Structured dashboard obtained via MCP")
            else:
                logger.warning(f"[DataGenerator] MCP structured_dashboard error: {struct_resp.get('error')}")
        except Exception as e:
            logger.warning(f"[DataGenerator] MCP structured_dashboard exception: {e}")

        # RAG dashboard via MCP
        try:
            rag_resp = await mcp_client.call_tool(
                "generate_rag_dashboard",
                {"company_id": company_id, "top_k": 10}
            )
            if rag_resp.get("success"):
                rag_from_mcp = rag_resp.get("result") or ""
                logger.info("[DataGenerator] RAG dashboard obtained via MCP")
            else:
                logger.warning(f"[DataGenerator] MCP rag_dashboard error: {rag_resp.get('error')}")
        except Exception as e:
            logger.warning(f"[DataGenerator] MCP rag_dashboard exception: {e}")
    else:
        logger.info("[DataGenerator] MCP client not available; falling back to local tools")

    # ------------------------------------------------------------
    # 2) Generate dashboards using payload-backed data + fallbacks
    # ------------------------------------------------------------
    if company_data:
        company_name = company_data.get("name", company_id)

        # -------- Structured dashboard --------
        if structured_from_mcp:
            state["structured_dashboard"] = structured_from_mcp
        elif load_payload is not None and generate_dashboard is not None:
            try:
                payload = load_payload(company_id)
                state["structured_dashboard"] = generate_dashboard(payload)
                logger.info("[DataGenerator] Structured dashboard generated from local payload pipeline")
            except Exception as e:
                logger.warning(f"[DataGenerator] Local structured dashboard error: {e}")
                state["structured_dashboard"] = (
                    f"# Structured Dashboard - {company_name}\n\n"
                    "*Error generating structured dashboard*"
                )
        else:
            state["structured_dashboard"] = (
                f"# Structured Dashboard - {company_name}\n\n"
                "*Dashboard generator not available*"
            )

        # -------- RAG dashboard --------
        if rag_from_mcp:
            state["rag_dashboard"] = rag_from_mcp
        elif generate_dashboard_from_rag is not None and rag_search_company is not None:
            try:
                rag_queries = [
                    f"{company_name} company overview mission",
                    f"{company_name} funding investors",
                    f"{company_name} business model revenue",
                    f"{company_name} risks challenges layoffs",
                ]
                all_context: List[Dict] = []
                for query in rag_queries:
                    try:
                        results = await rag_search_company(company_id, query, top_k=3)
                        all_context.extend(results)
                    except Exception as e:
                        logger.warning(f"[DataGenerator] RAG search error for query '{query}': {e}")

                if all_context:
                    state["rag_dashboard"] = generate_dashboard_from_rag(company_name, all_context)
                    logger.info(f"[DataGenerator] Generated RAG dashboard with {len(all_context)} context chunks")
                else:
                    state["rag_dashboard"] = (
                        f"# RAG Dashboard - {company_name}\n\n"
                        "*No RAG context available*"
                    )
            except Exception as e:
                logger.warning(f"[DataGenerator] Error generating RAG dashboard: {e}")
                state["rag_dashboard"] = (
                    f"# RAG Dashboard - {company_name}\n\n"
                    f"*Error: {str(e)}*"
                )
        else:
            state["rag_dashboard"] = (
                f"# RAG Dashboard - {company_name}\n\n"
                "*RAG dashboard generation not available (Lab 4/7 integration pending)*"
            )
            logger.warning("[DataGenerator] RAG dashboard generation skipped - tools not available")

        # -------- Dashboard metadata from company_data --------
        dashboard_data = {
            "company_overview": {
                "name": company_name,
                "industry": company_data.get("industry", "Not disclosed"),
                "founded": company_data.get("founded", "Not disclosed"),
                "website": company_data.get("website", "Not disclosed"),
                "hq_city": company_data.get("hq_city", "Not disclosed"),
                "hq_state": company_data.get("hq_state", "Not disclosed"),
                "hq_country": company_data.get("hq_country", "Not disclosed"),
            },
            "business_model": {
                "revenue_model": company_data.get("revenue_model", "Not disclosed"),
                "target_market": company_data.get("target_market", "Enterprise / B2B"),
            },
            "funding": {
                "total_raised": company_data.get("funding", "Not disclosed"),
                "last_round": company_data.get("last_round", "Not disclosed"),
                "valuation": company_data.get("valuation", "Not disclosed"),
            },
            "growth_metrics": {
                "revenue_growth": company_data.get("revenue_growth", "Not disclosed"),
                "employee_count": company_data.get("employee_count", "Not disclosed"),
            },
        }

        # Extract risk events if we have a payload events list
        payload_obj = company_data.get("payload")
        if payload_obj is not None and hasattr(payload_obj, "events"):
            for event in payload_obj.events:
                event_type = getattr(event, "event_type", None)
                if event_type in ["layoff", "security_incident", "regulatory", "legal_action"]:
                    risks_found.append(
                        {
                            "type": event_type,
                            "severity": "high" if event_type == "layoff" else "medium",
                            "description": getattr(event, "description", "") or getattr(event, "title", ""),
                            "occurred_on": str(getattr(event, "occurred_on", "Unknown")),
                        }
                    )

        logger.info(f"[DataGenerator] Using REAL data for {company_name}")

    else:
        # --------------------------------------------------------
        # No payload found: stub dashboards and basic metadata
        # --------------------------------------------------------
        logger.warning(f"[DataGenerator] No payload found for {company_id}, using minimal stub")

        dashboard_data = {
            "company_overview": {
                "name": company_id,
                "industry": "Not disclosed",
                "founded": "Not disclosed",
            },
            "business_model": {
                "revenue_model": "Not disclosed",
                "target_market": "Not disclosed",
            },
            "funding": {
                "total_raised": "Not disclosed",
                "last_round": "Not disclosed",
            },
            "growth_metrics": {
                "revenue_growth": "Not disclosed",
                "employee_count": "Not disclosed",
            },
        }

        state["structured_dashboard"] = (
            f"# Structured Dashboard - {company_id}\n\n"
            "*No payload data available*"
        )
        state["rag_dashboard"] = (
            f"# RAG Dashboard - {company_id}\n\n"
            "*No payload data available*"
        )

    # Persist back into workflow state
    state["dashboard_data"] = dashboard_data
    state["risk_details"] = risks_found
    state["messages"].append(
        {
            "node": "data_generator",
            "action": "dashboards_generated",
            "risk_count": len(risks_found),
            "data_source": "real" if company_data else "stub",
        }
    )

    logger.info(f"[DataGenerator] Dashboards generated, {len(risks_found)} risks found")
    return state


def evaluator_node(state: WorkflowState) -> WorkflowState:
    """
    Evaluator Node: Uses existing evaluation_agent to score dashboards
    """
    logger.info(f"[Evaluator] Evaluating dashboards for company_id={state['company_id']}")

    result = evaluate_dashboards(
        state["rag_dashboard"],
        state["structured_dashboard"],
        company_id=state["company_id"],
        run_id=state["run_id"]
    )

    state["evaluation_result"] = result
    state["evaluation_score"] = float(result.get("score", 0.0))
    state["messages"].append({
        "node": "evaluator",
        "action": "evaluation_completed",
        "result": result
    })

    print("EVAL RESULT:", result)
    return state


def risk_detector_node(state: WorkflowState) -> WorkflowState:
    """
    Risk Detector Node:
    - Simple keyword-based risk detection for Lab 17
    - Can be extended with LLM-based risk analysis
    """
    logger.info(f"[RiskDetector] Checking risks for company_id={state['company_id']}")

    structured_text = state["structured_dashboard"].lower()
    risk_keywords = ["layoff", "breach", "regulatory", "security incident"]

    risk_detected = any(k in structured_text for k in risk_keywords)
    state["risk_detected"] = risk_detected

    if risk_detected:
        logger.warning("[RiskDetector] Risk detected -> HITL branch!")
        state["risk_details"].append({
            "type": "keyword_match",
            "severity": "medium",
            "description": "Risk keywords found in structured dashboard",
            "keywords": risk_keywords
        })
    else:
        logger.info("[RiskDetector] No risk detected -> Auto-approve branch.")

    state["messages"].append({
        "node": "risk_detector",
        "action": "risk_evaluated",
        "risk_detected": risk_detected
    })

    return state


def human_approval_node(state: WorkflowState) -> WorkflowState:
    """
    Human-in-the-Loop Node (Lab 18):
    - Pauses for human approval via CLI
    """
    logger.info(f"[HITL] Human approval required for company_id={state['company_id']}")

    print("\n" + "=" * 80)
    print("🚨 HUMAN APPROVAL REQUIRED 🚨")
    print(f"Company: {state['company_id']}")
    print(f"Evaluation Score: {state['evaluation_score']}")
    print("Detected Risks:")
    for idx, r in enumerate(state.get("risk_details", []), start=1):
        print(f"  {idx}. {r.get('type', 'unknown')} - {r.get('description', '')}")
    print("=" * 80)

    approval_input = input("Approve this dashboard? (yes/no): ").strip().lower()
    approved = approval_input in ["yes", "y"]

    state["human_approval"] = approved
    state["messages"].append({
        "node": "hitl",
        "action": "human_approval",
        "approved": approved
    })

    logger.info(f"[HITL] Human approval: {approved}")
    return state


def finalize_node(state: WorkflowState) -> WorkflowState:
    """
    Finalize Node:
    - Assembles final dashboard markdown including evaluation & risk info.
    """
    logger.info(f"[Finalize] Finalizing dashboard for company_id={state['company_id']}")

    company_id = state["company_id"]
    eval_score = state.get("evaluation_score", 0.0)
    risk_detected = state.get("risk_detected", False)
    # Get human_approval from state
    # - If explicitly set to True/False (via CLI or API), use that value
    # - If None and no risk: default to True (auto-approve)
    # - If None and risk detected: keep as None (pending external approval)
    human_approval = state.get("human_approval")
    if human_approval is None and not risk_detected:
        human_approval = True  # Auto-approve if no risk

    overview = state.get("dashboard_data", {}).get("company_overview", {})
    name = overview.get("name", company_id)
    industry = overview.get("industry", "Not disclosed")
    website = overview.get("website", "Not disclosed")

    final_md = [
        f"# Due Diligence Dashboard — {name}",
        "",
        f"- **Company ID:** {company_id}",
        f"- **Industry:** {industry}",
        f"- **Website:** {website}",
        "",
        "## 1. Evaluation Summary",
        f"- **Evaluation Score:** {eval_score:.2f}",
        f"- **Risk Detected:** {'Yes' if risk_detected else 'No'}",
        f"- **Human Approval:** {'Approved' if human_approval is True else ('Rejected' if human_approval is False else 'Pending')}",
        "",
        "## 2. Structured Dashboard",
        state.get("structured_dashboard", "_No structured dashboard available_"),
        "",
        "## 3. RAG Dashboard",
        state.get("rag_dashboard", "_No RAG dashboard available_"),
        "",
        "## 4. Risk Details",
    ]

    if state.get("risk_details"):
        for idx, r in enumerate(state["risk_details"], start=1):
            final_md.append(
                f"- **{idx}. {r.get('type', 'unknown')}** — {r.get('description', '')}"
            )
    else:
        final_md.append("_No explicit risk signals detected._")

    state["final_dashboard"] = "\n".join(final_md)
    # CRITICAL: Preserve human_approval value (including None for pending)
    # Don't override it - it should remain None if pending, True if approved, False if rejected
    state["human_approval"] = human_approval
    state["messages"].append({
        "node": "finalize",
        "action": "dashboard_finalized"
    })

    logger.info("[Finalize] Dashboard finalized")
    return state


# ============================================================
# GRAPH DEFINITION
# ============================================================

def should_require_approval(state: WorkflowState) -> Literal["hitl", "finalize"]:
    """Conditional routing based on risk detection."""
    if state["risk_detected"]:
        return "hitl"
    else:
        return "finalize"


def build_workflow() -> StateGraph:
    """Build LangGraph workflow for Lab 17."""
    workflow = StateGraph(WorkflowState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("data_generator", data_generator_node)
    workflow.add_node("evaluator", evaluator_node)
    workflow.add_node("risk_detector", risk_detector_node)
    workflow.add_node("hitl", human_approval_node)
    workflow.add_node("finalize", finalize_node)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "data_generator")
    workflow.add_edge("data_generator", "evaluator")
    workflow.add_edge("evaluator", "risk_detector")

    workflow.add_conditional_edges(
        "risk_detector",
        should_require_approval,
        {
            "hitl": "hitl",
            "finalize": "finalize",
        },
    )

    workflow.add_edge("hitl", "finalize")
    workflow.add_edge("finalize", END)

    return workflow


# ============================================================
# EXECUTION HELPERS (TRACE SAVING)
# ============================================================

def save_execution_trace(state: WorkflowState):
    """Save execution trace as JSON for Lab 18."""
    try:
        dashboard_data = state.get("dashboard_data", {})
        company_overview = dashboard_data.get("company_overview", {})
        company_name = company_overview.get("name", state["company_id"])
    except Exception:
        company_name = state["company_id"]

    trace = {
        "company_id": state["company_id"],
        "company_name": company_name,
        "run_id": state.get("run_id"),
        "risk_detected": state.get("risk_detected"),
        "evaluation_score": state.get("evaluation_score"),
        "branch_taken": "hitl_then_finalize" if state.get("risk_detected") else "direct_to_finalize",
        "human_approval": state.get("human_approval"),
        "data_source": state.get("messages", [{}])[1].get("data_source", "unknown") if len(state.get("messages", [])) > 1 else "unknown",
        "messages": state.get("messages", []),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Try to save to GCS first
    if GCS_AVAILABLE and DashboardStorage is not None:
        try:
            bucket_name = os.getenv('GCS_BUCKET_NAME', 'ai-pe-dashboard')
            storage = DashboardStorage(bucket_name)
            
            # Save trace as JSON content
            trace_content = json.dumps(trace, indent=2, default=str)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            blob_name = f"data/workflow_traces/{state['company_id']}/trace_{timestamp}.json"
            
            blob = storage.bucket.blob(blob_name)
            blob.upload_from_string(trace_content, content_type='application/json')
            
            gcs_uri = f"gs://{bucket_name}/{blob_name}"
            logger.info(f"[Trace] Saved execution trace to GCS: {gcs_uri}")
            print(f"  ✅ Trace saved to GCS: {gcs_uri}")
            
            # Also save locally as backup
            filename = f"workflow_execution_trace_{state['company_id']}.json"
            output_path = _project_root / "workflow_execution_traces"
            output_path.mkdir(exist_ok=True)
            full_path = output_path / filename
            with open(full_path, "w", encoding="utf-8") as f:
                json.dump(trace, f, indent=2)
            logger.info(f"[Trace] Also saved locally: {full_path}")
            return
            
        except Exception as e:
            logger.warning(f"[Trace] GCS save failed: {e}, falling back to local...")
    
    # Fallback to local save
    filename = f"workflow_execution_trace_{state['company_id']}.json"
    output_path = _project_root / "workflow_execution_traces"
    output_path.mkdir(exist_ok=True)

    full_path = output_path / filename
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2)

    logger.info(f"[Trace] Saved execution trace to {full_path}")


def save_dashboard(state: WorkflowState):
    """Save final dashboard markdown. 
    - If risk detected and not yet approved: save to pending_approval/
    - If approved: save directly to company folder (no subfolder)
    - If rejected: save to rejected/
    - If no risk: save directly to company folder (no subfolder)
    """
    company_id = state["company_id"]
    dashboard_content = state.get("final_dashboard", "")
    risk_detected = state.get("risk_detected", False)
    # Don't use default=False here - we need to distinguish None (pending) from False (rejected)
    human_approval = state.get("human_approval")  # Can be True, False, or None
    run_id = state.get("run_id", "unknown")
    
    # Determine save location based on risk detection and approval status
    # human_approval can be: True (approved), False (rejected), or None/not set (pending)
    # Approved dashboards go directly in company folder (no subfolder)
    # Rejected dashboards go to rejected/ subfolder
    # Pending approvals go to pending_approval/ subfolder
    if risk_detected:
        # Check if human_approval was explicitly set (True or False)
        # If it's False, it was rejected; if True, approved; if None/not set, pending
        if human_approval is False:
            # Explicitly rejected (via CLI or API)
            subfolder = "rejected"
            logger.info(f"[Finalize] Dashboard rejected - saving to {subfolder}")
            print(f"  ❌ Dashboard rejected - saved to {subfolder}")
        elif human_approval is True:
            # Approved after risk detection (via CLI or API) - save directly in company folder
            subfolder = None  # No subfolder for approved
            logger.info(f"[Finalize] Dashboard approved after risk detection - saving to company folder")
            print(f"  ✅ Dashboard approved - saved to company folder")
        else:
            # Risk detected but human_approval not set yet (pending external approval)
            # This happens when running via Airflow with external HITL
            subfolder = "pending_approval"
            logger.info(f"[Finalize] Risk detected - saving to {subfolder} for approval")
            print(f"  ⚠️ Risk detected - dashboard saved to {subfolder} for approval")
    else:
        # No risk - auto-approved, save directly in company folder
        subfolder = None  # No subfolder for approved
        logger.info(f"[Finalize] No risk - saving to company folder")
        print(f"  ✅ No risk - dashboard saved to company folder")
    
    # Try to save to GCS first
    if GCS_AVAILABLE and DashboardStorage is not None:
        try:
            bucket_name = os.getenv('GCS_BUCKET_NAME', 'ai-pe-dashboard')
            storage = DashboardStorage(bucket_name)
            
            # Prepare metadata
            metadata = {
                "company_id": company_id,
                "run_id": run_id,
                "evaluation_score": state.get("evaluation_score", 0.0),
                "risk_detected": risk_detected,
                "human_approval": human_approval,
                "status": "pending" if (risk_detected and human_approval is None) else ("approved" if (human_approval is True or not risk_detected) else "rejected"),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "workflow": "due_diligence_graph"
            }
            
            # Save dashboard to GCS with subfolder (if any)
            if subfolder:
                blob_name = f"data/dashboards/{company_id}/{subfolder}/due_diligence_{run_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
            else:
                blob_name = f"data/dashboards/{company_id}/due_diligence_{run_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
            blob = storage.bucket.blob(blob_name)
            blob.upload_from_string(dashboard_content, content_type='text/markdown')
            blob.metadata = metadata
            blob.patch()
            
            gcs_uri = f"gs://{bucket_name}/{blob_name}"
            logger.info(f"[Finalize] Saved dashboard to GCS: {gcs_uri}")
            print(f"  ✅ Dashboard saved to GCS: {gcs_uri}")
            
            # Also save locally as backup
            if subfolder:
                local_output_path = _project_root / "data" / "dashboards" / company_id / subfolder
            else:
                local_output_path = _project_root / "data" / "dashboards" / company_id
            local_output_path.mkdir(parents=True, exist_ok=True)
            filename = f"due_diligence_{run_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
            full_path = local_output_path / filename
            
            # Save dashboard content
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(dashboard_content)
            
            # Save metadata JSON
            metadata_file = full_path.with_suffix('.json')
            with open(metadata_file, "w", encoding="utf-8") as f:
                import json
                json.dump(metadata, f, indent=2)
            
            logger.info(f"[Finalize] Also saved locally: {full_path}")
            return
            
        except Exception as e:
            logger.warning(f"[Finalize] GCS save failed: {e}, falling back to local...")
    
    # Fallback to local save
    if subfolder:
        local_output_path = _project_root / "data" / "dashboards" / company_id / subfolder
    else:
        local_output_path = _project_root / "data" / "dashboards" / company_id
    local_output_path.mkdir(parents=True, exist_ok=True)
    filename = f"due_diligence_{run_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    full_path = local_output_path / filename

    # Save dashboard content
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(dashboard_content)
    
    # Save metadata JSON
    metadata = {
        "company_id": company_id,
        "run_id": run_id,
        "evaluation_score": state.get("evaluation_score", 0.0),
        "risk_detected": risk_detected,
        "human_approval": human_approval,
        "status": "pending" if (risk_detected and human_approval is None) else ("approved" if (human_approval is True or not risk_detected) else "rejected"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workflow": "due_diligence_graph"
    }
    metadata_file = full_path.with_suffix('.json')
    with open(metadata_file, "w", encoding="utf-8") as f:
        import json
        json.dump(metadata, f, indent=2)

    logger.info(f"[Finalize] Saved dashboard markdown to {full_path}")


async def run_workflow(company_id: str) -> WorkflowState:
    """Run the workflow for a single company and return the final state."""
    workflow = build_workflow()
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

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

    config = {
        "configurable": {
            "thread_id": f"due_diligence_{company_id}_{run_id}"
        }
    }

    final_output = None
    node_name = None

    async for output in app.astream(initial_state, config):
        node_name = list(output.keys())[0]
        print(f"\n✓ Completed: {node_name}")
        final_output = output

    final_state = final_output[node_name] if final_output else initial_state

    print("\n📊 WORKFLOW RESULTS")
    print(f"Branch Taken: {'HITL → Finalize' if final_state['risk_detected'] else 'Auto-approve → Finalize'}")
    print(f"Evaluation Score: {final_state['evaluation_score']}")
    print(f"Human Approval: {final_state.get('human_approval', not final_state['risk_detected'])}")

    save_execution_trace(final_state)
    save_dashboard(final_state)
    return final_state


# ============================================================
# CLI ENTRYPOINT
# ============================================================

async def main():
    """
    CLI entrypoint:
    - List companies: python src/workflows/due_diligence_graph.py --list
    - Run workflow:   python src/workflows/due_diligence_graph.py <company_id>
    """
    loader = CompanyDataLoader()

    if len(sys.argv) > 1 and sys.argv[1] in ["--list", "-l"]:
        company_ids = loader.get_available_company_ids()
        print("Available companies:")
        for cid in company_ids:
            print(f"- {cid}")
        return

    if len(sys.argv) > 1:
        cid = sys.argv[1]
    else:
        # If no company_id is passed, pick the first available one
        company_ids = loader.get_available_company_ids()
        if not company_ids:
            print("No company data found in data/payloads or data/structured.")
            return
        cid = company_ids[0]
        print(f"Using first available company: {cid}")

    await run_workflow(cid)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
