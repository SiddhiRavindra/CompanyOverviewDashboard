"""
Supervisor Agent with MCP Integration (Lab 15)

Uses MCP client to call tools via HTTP instead of direct Python imports
"""
import os
import sys
import asyncio
from datetime import date, datetime
from typing import Dict, Any
from pathlib import Path
import time
import json

# Add project root to path FIRST
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# ✅ Load .env from src/.env
env_path = project_root / '.env'
print(f"📂 Loading .env from: {env_path}")
load_dotenv(dotenv_path=env_path, override=True)

# ✅ Set credentials environment variable
credentials_relative = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if credentials_relative:
    credentials_path = project_root / credentials_relative
    if credentials_path.exists():
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_path)
        print(f"🔑 Using credentials: {credentials_path}")
    else:
        print(f"⚠️ Credentials file not found: {credentials_path}")

# Set project ID
project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
if project_id:
    os.environ['GOOGLE_CLOUD_PROJECT'] = project_id

from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langchain.agents import create_agent

# Import MCP client
from mcp_client import MCPClient

# ✅ Import GCS client
try:
    from src.storage.gcs_client import DashboardStorage
    GCS_AVAILABLE = True
    print("✅ GCS module loaded")
except ImportError as e:
    print(f"⚠️ Google Cloud Storage not available: {e}")
    GCS_AVAILABLE = False


class SupervisorAgentMCP:
    """Supervisor Agent that calls tools via MCP server"""
    
    def __init__(self, mcp_config_path: str = None):
        """Initialize with MCP client"""
        
        # Calculate path relative to project root
        if mcp_config_path is None:
            project_root = Path(__file__).parent.parent.parent
            mcp_config_path = project_root / "src" / "server" / "mcp_server.config.json"
        
        mcp_config_path = str(mcp_config_path)
        
        self.mcp_client = MCPClient(mcp_config_path)
        
        # Initialize LLM
        api_key = os.getenv('OPENAI_KEY')
        if not api_key:
            raise ValueError("OPENAI_KEY not found in environment variables")
        
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, openai_api_key=api_key)
        
        # Create tools
        self.tools = self._create_mcp_tools()
        
        # System prompt
        system_prompt = """You are a PE Due Diligence Supervisor Agent.

Your job:
1. Get structured payload for the company
2. Search for risks using RAG
3. If you find risks (layoffs, security incidents, lawsuits), log them
4. Generate a comprehensive dashboard

Use the tools available to you. Think step by step."""
        
        # Create agent
        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=system_prompt,
            debug=False  # ← Disable debug for batch processing
        )
        
        # Initialize GCS client
        if GCS_AVAILABLE:
            try:
                bucket_name = os.getenv('GCS_BUCKET_NAME', 'pe-dashboard-storage')
                self.storage = DashboardStorage(bucket_name)
            except Exception as e:
                print(f"⚠️ GCS client failed: {e}")
                self.storage = None
        else:
            self.storage = None

    def _create_mcp_tools(self):
        """Create LangChain tools that call MCP server"""
        
        def get_structured_dashboard_wrapper(company_id: str) -> str:
            """Get structured dashboard via MCP"""
            result = self.mcp_client.call_tool(
                "generate_structured_dashboard",
                {"company_id": company_id}
            )
            
            if result.get("success"):
                return result.get("result", "Dashboard generated but empty")
            else:
                return f"Error: {result.get('error')}"
        
        def get_rag_dashboard_wrapper(company_id: str, top_k: int = 5) -> str:
            """Get RAG dashboard via MCP"""
            result = self.mcp_client.call_tool(
                "generate_rag_dashboard",
                {"company_id": company_id, "top_k": top_k}
            )
            
            if result.get("success"):
                return result.get("result", "Dashboard generated but empty")
            else:
                return f"Error: {result.get('error')}"
        
        def report_risk_wrapper(
            company_id: str,
            occurred_on: str,
            description: str,
            source_url: str,
            risk_type: str,
            severity: str = "medium"
        ) -> str:
            """Report risk via MCP"""
            result = self.mcp_client.call_tool(
                "report_risk",
                {
                    "company_id": company_id,
                    "occurred_on": occurred_on,
                    "description": description,
                    "source_url": source_url,
                    "risk_type": risk_type,
                    "severity": severity
                }
            )
            
            if result.get("success"):
                hitl = result.get("metadata", {}).get("hitl_required", False)
                return f"Risk logged. HITL required: {hitl}"
            else:
                return f"Error: {result.get('error')}"
        
        return [
            StructuredTool.from_function(
                func=get_structured_dashboard_wrapper,
                name="generate_structured_dashboard",
                description="Generate dashboard using structured data from payloads"
            ),
            StructuredTool.from_function(
                func=get_rag_dashboard_wrapper,
                name="generate_rag_dashboard",
                description="Generate dashboard using RAG search. Specify top_k for number of results."
            ),
            StructuredTool.from_function(
                func=report_risk_wrapper,
                name="report_risk",
                description="""Log a risk signal. Required params:
                - company_id: str
                - occurred_on: str (YYYY-MM-DD)
                - description: str
                - source_url: str (valid URL)
                - risk_type: str (layoff, security_incident, regulatory, etc.)
                - severity: str (low, medium, high, critical)"""
            )
        ]
    
    async def generate_unified_dashboard(self, company_id: str) -> Dict[str, Any]:
        """Generate unified dashboard by merging structured + RAG data"""
        
        print(f"  🔄 Generating UNIFIED dashboard for: {company_id}")
        
        # Get structured dashboard
        structured_result = self.mcp_client.call_tool(
            "generate_structured_dashboard",
            {"company_id": company_id}
        )
        
        # Get RAG dashboard
        rag_result = self.mcp_client.call_tool(
            "generate_rag_dashboard",
            {"company_id": company_id, "top_k": 10}
        )
        
        if not structured_result.get("success"):
            return {"success": False, "error": "Structured pipeline failed"}
        
        structured_text = structured_result.get("result", "")
        rag_text = rag_result.get("result", "") if rag_result.get("success") else ""
        
        # Parse sections from both
        structured_sections = self._parse_sections(structured_text)
        rag_sections = self._parse_sections(rag_text)
        
        # Extract company name
        company_name = company_id.title()
        if "# PE Dashboard for" in structured_text:
            company_name = structured_text.split("# PE Dashboard for")[1].split("\n")[0].strip()
        
        # Build unified dashboard
        unified = f"""# PE Dashboard for {company_name}
*Combined from Structured Pipeline (validated data) + RAG Pipeline (recent context)*
*Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*

"""
        
        # Merge each of the 8 required sections
        section_mapping = [
            ("1. Company Overview", "1. Company Overview"),
            ("2. Business Model and GTM", "2. Business Model and GTM"),
            ("3. Funding & Investor Profile", "2. Funding History"),
            ("4. Growth Momentum", "7. Key Metrics"),
            ("5. Visibility & Market Sentiment", "5. Market Position"),
            ("6. Risks and Challenges", "8. Risk Factors"),
            ("7. Outlook", "6. Recent Developments"),
            ("8. Disclosure Gaps", "8. Disclosure Gaps")
        ]
        
        for structured_key, rag_key in section_mapping:
            structured_content = structured_sections.get(structured_key, "").strip()
            rag_content = rag_sections.get(rag_key, "").strip()
            
            # Merge the content
            merged_content = self._merge_content(structured_content, rag_content)
            
            unified += f"\n## {structured_key}\n{merged_content}\n"
        
        # Prepare metadata
        metadata = {
            "company_id": company_id,
            "generated_at": datetime.now().isoformat(),
            "sources": ["structured", "rag"],
            "sections": 8,
            "generator": "supervisor_agent_mcp"
        }
        
        # Try to save to GCS first
        if self.storage:
            try:
                gcs_uri = self.storage.save_dashboard(
                    company_id=company_id,
                    content=unified,
                    dashboard_type="unified",
                    metadata=metadata
                )
                
                return {
                    "success": True,
                    "company_id": company_id,
                    "dashboard": unified,
                    "saved_to": gcs_uri,
                    "storage_type": "gcs"
                }
            
            except Exception as e:
                print(f"  ⚠️ GCS save failed: {e}, falling back to local...")
        
        # Fallback: Save locally
        output_dir = Path("data/dashboards")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dashboard_file = output_dir / f"{company_id}_unified_{timestamp}.md"
        
        with open(dashboard_file, 'w', encoding='utf-8') as f:
            f.write(unified)
        
        return {
            "success": True,
            "company_id": company_id,
            "dashboard": unified,
            "saved_to": str(dashboard_file),
            "storage_type": "local"
        }

    def _parse_sections(self, dashboard: str) -> Dict[str, str]:
        """Parse dashboard markdown into sections"""
        sections = {}
        if not dashboard:
            return sections
        
        import re
        parts = re.split(r'\n##\s+', dashboard)
        
        for part in parts[1:]:  # Skip title
            lines = part.split('\n', 1)
            if len(lines) >= 1:
                header = lines[0].strip()
                content = lines[1].strip() if len(lines) > 1 else ""
                sections[header] = content
        
        return sections

    def _merge_content(self, structured: str, rag: str) -> str:
        """Merge content from structured and RAG"""
        
        structured_clean = structured.strip()
        rag_clean = rag.strip()
        
        is_structured_empty = not structured_clean or structured_clean in ["Not disclosed", "Not disclosed\n"]
        is_rag_empty = not rag_clean or rag_clean in ["Not disclosed", "Not disclosed\n"]
        
        if is_structured_empty and is_rag_empty:
            return "Not disclosed"
        
        if not is_structured_empty and is_rag_empty:
            return structured_clean
        
        if is_structured_empty and not is_rag_empty:
            return rag_clean
        
        # Both have data - combine
        return f"""{structured_clean}

**Additional Insights:**
{rag_clean}"""


# ============================================================================
# BATCH PROCESSING FUNCTION
# ============================================================================

async def process_all_companies():
    """Process all companies and generate unified dashboards"""
    
    print("\n" + "="*70)
    print("🚀 BATCH DASHBOARD GENERATION FOR ALL COMPANIES")
    print("="*70)
    
    # Get list of all companies from data/payloads directory
    payloads_dir = project_root / "data" / "payloads"
    
    if not payloads_dir.exists():
        print(f"❌ Payloads directory not found: {payloads_dir}")
        print("   Make sure you've run the structured pipeline first!")
        return
    
    # Get all company IDs from payload files
    companies = []
    for payload_file in payloads_dir.glob("*.json"):
        company_id = payload_file.stem  # filename without .json
        companies.append(company_id)
    
    companies = sorted(companies)
    
    print(f"\n✓ Found {len(companies)} companies with payloads")
    print(f"\nCompanies to process:")
    for i, company in enumerate(companies[:10], 1):
        print(f"  {i}. {company}")
    if len(companies) > 10:
        print(f"  ... and {len(companies) - 10} more")
    
    # Confirm
    print(f"\n⚠️  This will generate {len(companies)} unified dashboards")
    print(f"⚠️  Estimated time: ~{len(companies) * 15} seconds ({len(companies) * 15 / 60:.1f} minutes)")
    response = input("\nContinue? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("Cancelled.")
        return
    
    # Initialize agent once (reuse for all companies)
    print("\n🤖 Initializing Supervisor Agent...")
    try:
        agent = SupervisorAgentMCP()
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        return
    
    # Process each company
    print(f"\n{'='*70}")
    print("Starting batch processing...")
    print(f"{'='*70}\n")
    
    results = {
        "success": [],
        "failed": [],
        "gcs_saved": [],
        "local_saved": []
    }
    
    start_time = time.time()
    
    for idx, company_id in enumerate(companies, 1):
        print(f"\n[{idx}/{len(companies)}] {company_id}")
        print("-" * 60)
        
        try:
            result = await agent.generate_unified_dashboard(company_id)
            
            if result.get("success"):
                results["success"].append(company_id)
                
                if result.get("storage_type") == "gcs":
                    results["gcs_saved"].append({
                        "company_id": company_id,
                        "uri": result.get("saved_to")
                    })
                    print(f"  ✅ Saved to GCS")
                else:
                    results["local_saved"].append({
                        "company_id": company_id,
                        "path": result.get("saved_to")
                    })
                    print(f"  ✅ Saved locally")
            else:
                results["failed"].append({
                    "company_id": company_id,
                    "error": result.get("error")
                })
                print(f"  ❌ Failed: {result.get('error')}")
        
        except KeyboardInterrupt:
            print("\n\n⚠️ Interrupted by user")
            break
        except Exception as e:
            results["failed"].append({
                "company_id": company_id,
                "error": str(e)
            })
            print(f"  ❌ Error: {e}")
        
        # Rate limiting (avoid overwhelming MCP server)
        time.sleep(1)
    
    # Final summary
    elapsed = time.time() - start_time
    
    print(f"\n{'='*70}")
    print("✅ BATCH PROCESSING COMPLETE")
    print(f"{'='*70}")
    print(f"\n📊 Summary:")
    print(f"  Total companies: {len(companies)}")
    print(f"  Successful: {len(results['success'])}")
    print(f"  Failed: {len(results['failed'])}")
    print(f"  Saved to GCS: {len(results['gcs_saved'])}")
    print(f"  Saved locally: {len(results['local_saved'])}")
    print(f"  Time elapsed: {elapsed:.2f}s ({elapsed/60:.1f} minutes)")
    
    # Show failures if any
    if results['failed']:
        print(f"\n❌ Failed companies ({len(results['failed'])}):")
        for item in results['failed'][:10]:
            print(f"  - {item['company_id']}: {item['error'][:50]}")
        if len(results['failed']) > 10:
            print(f"  ... and {len(results['failed']) - 10} more")
    
    # Save results summary
    summary_file = project_root / "data" / "batch_results.json"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(summary_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": len(companies),
            "success_count": len(results['success']),
            "failed_count": len(results['failed']),
            "success": results['success'],
            "failed": results['failed'],
            "gcs_saved": results['gcs_saved'],
            "local_saved": results['local_saved'],
            "elapsed_seconds": elapsed
        }, f, indent=2)
    
    print(f"\n💾 Results summary saved to: {summary_file}")
    
    # Show GCS dashboard locations
    if results['gcs_saved']:
        print(f"\n📍 GCS Dashboards:")
        for item in results['gcs_saved'][:5]:
            print(f"  {item['uri']}")
        if len(results['gcs_saved']) > 5:
            print(f"  ... and {len(results['gcs_saved']) - 5} more")
    
    return results


async def demo_mcp_consumption(company_id: str):
    """Demo Lab 15: Generate unified dashboard for single company"""
    
    print(f"\n{'='*60}")
    print(f"🤖 Supervisor Agent: Processing {company_id}")
    print(f"{'='*60}\n")
    
    agent = SupervisorAgentMCP()
    result = await agent.generate_unified_dashboard(company_id)
    
    if result.get("success"):
        print(f"\n{'='*60}")
        print("✅ UNIFIED DASHBOARD SAVED")
        print(f"{'='*60}")
        print(f"Saved to: {result['saved_to']}")
        print(f"Storage: {result.get('storage_type', 'unknown')}")
    else:
        print(f"\n❌ Error: {result.get('error')}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            # Process all companies
            asyncio.run(process_all_companies())
        else:
            # Process single company
            company = sys.argv[1]
            asyncio.run(demo_mcp_consumption(company))
    else:
        # Default: show help
        print("\n" + "="*70)
        print("PE Dashboard Generator - Supervisor Agent with MCP")
        print("="*70)
        print("\nUsage:")
        print("  python src/agents/supervisor_mcp.py <company_id>   # Single company")
        print("  python src/agents/supervisor_mcp.py --all          # All companies")
        print("\nExamples:")
        print("  python src/agents/supervisor_mcp.py anthropic")
        print("  python src/agents/supervisor_mcp.py openai")
        print("  python src/agents/supervisor_mcp.py --all")
        print("\n" + "="*70)
        print("\nℹ️  Tip: Make sure MCP server is running first!")
        print("  Terminal 1: python src/server/mcp_server.py")
        print("  Terminal 2: python src/agents/supervisor_mcp.py --all")
        print("\n")