# """
# MCP Server - Model Context Protocol Implementation
# Exposes tools, resources, and prompts for AI agents
# """

# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel, Field, HttpUrl
# from typing import List, Dict, Optional, Literal
# from datetime import date
# import os
# import sys
# from pathlib import Path
# from dotenv import load_dotenv

# # Add src to path for imports
# sys.path.append(str(Path(__file__).parent.parent))

# # Import your 3 tools
# from tools.payload_tool import get_latest_structured_payload
# from tools.rag_tool import rag_search_company
# from tools.risk_logger import report_risk_signal, RiskSignal

# load_dotenv()

# app = FastAPI(
#     title="MCP Server - PE Due Diligence",
#     description="Model Context Protocol server for AI agent tool access",
#     version="1.0.0"
# )

# # ============================================================================
# # PYDANTIC MODELS
# # ============================================================================

# class ToolRequest(BaseModel):
#     """Base request model for tool invocations"""
#     company_id: str = Field(..., description="Company identifier (e.g., 'abridge')")

# class StructuredDashboardRequest(ToolRequest):
#     """Request for structured dashboard generation"""
#     pass

# class RAGDashboardRequest(ToolRequest):
#     """Request for RAG dashboard generation"""
#     top_k: int = Field(default=5, description="Number of chunks to retrieve per query")
#     query: Optional[str] = Field(default=None, description="Optional search query")

# class UnifiedDashboardRequest(ToolRequest):
#     """Request for unified dashboard generation (combines structured + RAG)"""
#     top_k: int = Field(default=5, description="Number of RAG chunks to retrieve per query")
#     prefer_structured: bool = Field(default=True, description="Prefer structured data when available")

# class RiskReportRequest(BaseModel):
#     """Request for risk reporting"""
#     company_id: str = Field(..., description="Company identifier")
#     occurred_on: date = Field(..., description="Date when risk event occurred")
#     description: str = Field(..., description="Description of the risk")
#     source_url: HttpUrl = Field(..., description="Source URL of the risk information")
#     risk_type: Literal[
#         "layoff", "security_incident", "regulatory", "financial_distress",
#         "leadership_crisis", "legal_action", "product_recall", 
#         "market_disruption", "other"
#     ] = Field(..., description="Type of risk")
#     severity: Literal["low", "medium", "high", "critical"] = Field(
#         default="medium", 
#         description="Severity level"
#     )

# class ToolResponse(BaseModel):
#     """Standard response for tool invocations"""
#     success: bool
#     company_id: str
#     result: Optional[str] = None
#     error: Optional[str] = None
#     metadata: Optional[Dict] = None

# class UnifiedDashboardResponse(BaseModel):
#     """Response for unified dashboard"""
#     success: bool
#     company_id: str
#     result: Optional[str] = None
#     error: Optional[str] = None
#     metadata: Optional[Dict] = None
#     data_sources: Dict[str, str] = Field(
#         default_factory=dict,
#         description="Which data source was used for each section"
#     )

# class CompanyListResponse(BaseModel):
#     """Response for company list resource"""
#     companies: List[str]
#     count: int

# class PromptResponse(BaseModel):
#     """Response for prompt templates"""
#     prompt_id: str
#     template: str
#     description: str

# # ============================================================================
# # HEALTH CHECK
# # ============================================================================

# @app.get("/")
# async def root():
#     """Health check endpoint"""
#     return {
#         "service": "MCP Server",
#         "status": "healthy",
#         "version": "1.0.0",
#         "endpoints": {
#             "tools": 4,
#             "resources": 1,
#             "prompts": 1
#         }
#     }

# @app.get("/health")
# async def health_check():
#     """Detailed health check"""
#     return {
#         "status": "healthy",
#         "mcp_version": "2024-11-05",
#         "tools_available": [
#             "generate_structured_dashboard",
#             "generate_rag_dashboard",
#             "generate_unified_dashboard",
#             "report_risk"
#         ],
#         "resources_available": ["ai50/companies"],
#         "prompts_available": ["pe-dashboard"]
#     }

# # ============================================================================
# # TOOL ENDPOINTS - Connected to your actual tools
# # ============================================================================

# @app.post("/tool/generate_structured_dashboard", response_model=ToolResponse)
# async def tool_generate_structured_dashboard(request: StructuredDashboardRequest):
#     """
#     Tool: Generate structured dashboard
#     Calls your payload_tool.py -> get_latest_structured_payload()
#     """
#     try:
#         company_id = request.company_id
        
#         # Call your actual tool from tools/payload_tool.py
#         payload = await get_latest_structured_payload(company_id)
        
#         # Generate markdown dashboard from payload
#         dashboard_markdown = generate_dashboard_from_payload(payload, company_id)
        
#         return ToolResponse(
#             success=True,
#             company_id=company_id,
#             result=dashboard_markdown,
#             metadata={
#                 "source": "structured_pipeline",
#                 "tool": "payload_tool",
#                 "sections": 8,
#                 "type": "markdown",
#                 "has_events": len(payload.events) > 0,
#                 "has_leadership": len(payload.leadership) > 0,
#                 "has_products": len(payload.products) > 0
#             }
#         )
    
#     except FileNotFoundError as e:
#         raise HTTPException(
#             status_code=404,
#             detail=f"Company '{request.company_id}' not found in structured data: {str(e)}"
#         )
#     except ValueError as e:
#         return ToolResponse(
#             success=False,
#             company_id=request.company_id,
#             error=f"Validation error: {str(e)}",
#             metadata={"error_type": "ValueError"}
#         )
#     except Exception as e:
#         return ToolResponse(
#             success=False,
#             company_id=request.company_id,
#             error=str(e),
#             metadata={"error_type": type(e).__name__}
#         )

# @app.post("/tool/generate_rag_dashboard", response_model=ToolResponse)
# async def tool_generate_rag_dashboard(request: RAGDashboardRequest):
#     """
#     Tool: Generate RAG dashboard using LLM to structure the content
#     Calls rag_tool.py -> rag_search_company() and uses GPT for generation
#     """
#     try:
#         from openai import OpenAI
        
#         company_id = request.company_id
#         top_k = request.top_k
        
#         # Define sections to search for
#         sections = [
#             ("Company Overview", "company overview business model mission"),
#             ("Funding History", "funding history investors series round valuation"),
#             ("Leadership", "leadership team executives CEO founder management"),
#             ("Product/Technology", "product technology platform features innovation"),
#             ("Market Position", "market position competitors industry landscape"),
#             ("Recent Developments", "recent news developments announcements updates"),
#             ("Key Metrics", "metrics revenue growth employees customers headcount"),
#             ("Risk Factors", "risks challenges problems issues concerns")
#         ]
        
#         # Collect RAG results for each section
#         rag_results = {}
#         all_chunks_count = 0
        
#         for section_name, query in sections:
#             chunks = await rag_search_company(
#                 company_id=company_id,
#                 query=request.query or query,
#                 top_k=top_k
#             )
#             rag_results[section_name] = chunks
#             all_chunks_count += len(chunks)
        
#         # Format context for LLM
#         context = f"# Company Data: {company_id}\n\n"
#         for section_name, chunks in rag_results.items():
#             if chunks:
#                 context += f"## {section_name}\n"
#                 for i, chunk in enumerate(chunks[:3], 1):  # Use top 3 chunks per section
#                     context += f"**Source {i}:** {chunk.get('text', '')[:500]}...\n\n"
        
#         # System prompt for structured dashboard generation
#         system_prompt = """You are a PE analyst generating investor dashboards. Create a professional, well-structured 8-section dashboard.

# Rules:
# - Use ONLY information from the provided context
# - If information is missing, write "Not disclosed"
# - Be concise and factual
# - Format numbers properly (e.g., $100M, 500 employees)
# - Use bullet points for lists
# - Keep each section focused and relevant

# Generate exactly these 8 sections:
# 1. Company Overview
# 2. Business Model and GTM
# 3. Funding & Investor Profile
# 4. Growth Momentum
# 5. Visibility & Market Sentiment
# 6. Risks and Challenges
# 7. Outlook
# 8. Disclosure Gaps"""

#         user_prompt = f"""Generate a PE dashboard for {company_id}.

# {context}

# Create a professional markdown dashboard with all 8 sections."""

#         # Call OpenAI
#         client = OpenAI(api_key=os.getenv('OPENAI_KEY'))
#         response = client.chat.completions.create(
#             model="gpt-4o",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_prompt}
#             ],
#             temperature=0.3,
#             max_tokens=4000
#         )
        
#         dashboard_markdown = response.choices[0].message.content
        
#         return ToolResponse(
#             success=True,
#             company_id=company_id,
#             result=dashboard_markdown,
#             metadata={
#                 "source": "rag_pipeline",
#                 "tool": "rag_tool",
#                 "top_k": top_k,
#                 "sections": 8,
#                 "type": "markdown",
#                 "total_chunks_retrieved": all_chunks_count,
#                 "queries_executed": len(sections),
#                 "model": "gpt-4o",
#                 "tokens_used": response.usage.total_tokens
#             }
#         )
    
#     except Exception as e:
#         return ToolResponse(
#             success=False,
#             company_id=request.company_id,
#             error=str(e),
#             metadata={"error_type": type(e).__name__}
#         )

# @app.post("/tool/generate_unified_dashboard", response_model=UnifiedDashboardResponse)
# async def tool_generate_unified_dashboard(request: UnifiedDashboardRequest):
#     """
#     Tool: Generate unified dashboard
#     Combines structured payload data with RAG fallback for missing sections
    
#     **Default Behavior (prefer_structured=true):**
#     - Uses structured data when available
#     - Falls back to RAG for missing sections
#     - Best for comprehensive analysis
    
#     **Alternative (prefer_structured=false):**
#     - Uses RAG data primarily
#     - Enhances with structured data
#     - Useful when you want more context from documents
    
#     **Most users should use the default** (omit prefer_structured or set to true)
    
#     Strategy:
#     1. Try to get structured payload first
#     2. For any missing sections, use RAG to fill gaps
#     3. Indicate which source was used for each section
#     """
#     try:
#         company_id = request.company_id
#         top_k = request.top_k
#         prefer_structured = request.prefer_structured
        
#         # Track which source was used for each section
#         data_sources = {}
        
#         # Try to get structured payload
#         structured_payload = None
#         structured_available = False
        
#         try:
#             structured_payload = await get_latest_structured_payload(company_id)
#             structured_available = True
#         except (FileNotFoundError, ValueError) as e:
#             print(f"Structured data not available for {company_id}: {e}")
#             structured_available = False
        
#         # Define sections and RAG queries
#         sections = {
#             "Company Overview": "company overview business model description",
#             "Business Model and GTM": "business model go to market strategy revenue model customers",
#             "Funding & Investor Profile": "funding history investors series round valuation",
#             "Growth Momentum": "growth metrics revenue employees customers expansion",
#             "Visibility & Market Sentiment": "media mentions press coverage sentiment ratings reviews",
#             "Risks and Challenges": "risks challenges problems issues concerns threats",
#             "Outlook": "future plans roadmap strategy opportunities growth",
#             "Disclosure Gaps": "missing information undisclosed data gaps"
#         }
        
#         # Collect RAG results as fallback
#         rag_results = {}
#         for section_name, query in sections.items():
#             try:
#                 chunks = await rag_search_company(
#                     company_id=company_id,
#                     query=query,
#                     top_k=top_k
#                 )
#                 rag_results[section_name] = chunks
#             except Exception as e:
#                 print(f"RAG search failed for {section_name}: {e}")
#                 rag_results[section_name] = []
        
#         # Generate unified dashboard
#         if prefer_structured and structured_available:
#             # Primary: Structured, Secondary: RAG
#             dashboard_markdown = generate_unified_dashboard_structured_first(
#                 structured_payload=structured_payload,
#                 rag_results=rag_results,
#                 company_id=company_id,
#                 data_sources=data_sources
#             )
#         else:
#             # Primary: RAG, Secondary: Structured
#             dashboard_markdown = generate_unified_dashboard_rag_first(
#                 rag_results=rag_results,
#                 structured_payload=structured_payload if structured_available else None,
#                 company_id=company_id,
#                 data_sources=data_sources
#             )
        
#         return UnifiedDashboardResponse(
#             success=True,
#             company_id=company_id,
#             result=dashboard_markdown,
#             data_sources=data_sources,
#             metadata={
#                 "source": "unified_pipeline",
#                 "tool": "unified_dashboard",
#                 "structured_available": structured_available,
#                 "prefer_structured": prefer_structured,
#                 "top_k": top_k,
#                 "sections": 8,
#                 "type": "markdown"
#             }
#         )
    
#     except Exception as e:
#         return UnifiedDashboardResponse(
#             success=False,
#             company_id=request.company_id,
#             error=str(e),
#             data_sources={},
#             metadata={"error_type": type(e).__name__}
#         )

# @app.post("/tool/report_risk", response_model=ToolResponse)
# async def tool_report_risk(request: RiskReportRequest):
#     """
#     Tool: Report risk signal
#     Calls your risk_logger.py -> report_risk_signal()
#     """
#     try:
#         company_id = request.company_id
        
#         # Create RiskSignal object
#         risk_signal = RiskSignal(
#             company_id=company_id,
#             occurred_on=request.occurred_on,
#             description=request.description,
#             source_url=request.source_url,
#             risk_type=request.risk_type,
#             severity=request.severity
#         )
        
#         # Call your actual tool from tools/risk_logger.py
#         success = await report_risk_signal(risk_signal)
        
#         if not success:
#             return ToolResponse(
#                 success=False,
#                 company_id=company_id,
#                 error="Failed to log risk signal",
#                 metadata={"error_type": "RiskLoggingError"}
#             )
        
#         # Determine if HITL (Human-in-the-Loop) is required
#         hitl_required = request.severity in ["high", "critical"]
        
#         return ToolResponse(
#             success=True,
#             company_id=company_id,
#             result=f"Risk logged: {request.risk_type} - {request.description}",
#             metadata={
#                 "tool": "risk_logger",
#                 "hitl_required": hitl_required,
#                 "severity": request.severity,
#                 "risk_type": request.risk_type,
#                 "occurred_on": request.occurred_on.isoformat(),
#                 "log_location": "data/risk_signals/risk_signals.jsonl"
#             }
#         )
    
#     except Exception as e:
#         return ToolResponse(
#             success=False,
#             company_id=request.company_id,
#             error=str(e),
#             metadata={"error_type": type(e).__name__}
#         )

# # ============================================================================
# # RESOURCE ENDPOINTS
# # ============================================================================

# @app.get("/resource/ai50/companies", response_model=CompanyListResponse)
# async def resource_list_companies():
#     """
#     Resource: List all AI50 companies from forbes_ai50_seed.json
#     """
#     import json
#     from pathlib import Path
    
#     companies = []
    
#     # Method 1: Read from forbes_ai50_seed.json
#     try:
#         seed_file = Path(__file__).resolve().parent.parent.parent / "data" / "forbes_ai50_seed.json"
        
#         if seed_file.exists():
#             with open(seed_file, 'r', encoding='utf-8') as f:
#                 data = json.load(f)
                
#             # Extract company names from the JSON
#             if isinstance(data, list):
#                 for item in data:
#                     if 'company_name' in item:
#                         # Normalize company name to lowercase and replace spaces with hyphens
#                         company_name = item['company_name'].lower().replace(' ', '-')
#                         companies.append(company_name)
            
#             print(f"✓ Loaded {len(companies)} companies from forbes_ai50_seed.json")
#         else:
#             print(f"❌ forbes_ai50_seed.json not found at: {seed_file}")
#     except Exception as e:
#         print(f"Error reading forbes_ai50_seed.json: {e}")
    
#     # Method 2: Fallback - try to get from structured payloads directory
#     if not companies:
#         try:
#             data_dir = Path(__file__).resolve().parents[1] / "data" / "payloads"
#             if data_dir.exists():
#                 payload_files = list(data_dir.glob("*.json"))
#                 companies = [f.stem for f in payload_files]
#                 print(f"✓ Found {len(companies)} companies from payloads directory")
#         except Exception as e:
#             print(f"Could not scan payload directory: {e}")
    
#     # Sort and remove duplicates
#     companies = sorted(list(set(companies)))
    
#     return CompanyListResponse(
#         companies=companies,
#         count=len(companies)
#     )

# # ============================================================================
# # PROMPT ENDPOINTS
# # ============================================================================

# @app.get("/prompt/pe-dashboard", response_model=PromptResponse)
# async def prompt_pe_dashboard():
#     """
#     Prompt: PE Dashboard Template
#     """
#     template = """Generate a Private Equity due diligence dashboard with exactly 8 sections:

# ## 1. Company Overview
# - Brief description of the company
# - Industry and sector
# - Founded date and headquarters location
# - Mission and vision

# ## 2. Business Model and GTM
# - Revenue model (SaaS, enterprise, API, etc.)
# - Go-to-market strategy
# - Customer segments and target market
# - Sales channels and distribution
# - Key partnerships

# ## 3. Funding & Investor Profile
# - Total funding raised
# - Series rounds with dates and amounts
# - Lead investors for each round
# - Notable investors and their backgrounds
# - Current valuation

# ## 4. Growth Momentum
# - Revenue growth (if disclosed)
# - Customer growth and metrics
# - Product adoption trends
# - Market expansion activities
# - Employee headcount growth

# ## 5. Visibility & Market Sentiment
# - Media mentions and press coverage
# - Social media presence
# - Industry recognition and awards
# - Glassdoor ratings
# - GitHub stars (if applicable)
# - General market perception

# ## 6. Risks and Challenges
# - Competitive threats
# - Regulatory concerns
# - Market risks
# - Operational challenges
# - Financial risks
# - Security or legal issues

# ## 7. Outlook
# - Future plans and roadmap
# - Market opportunities
# - Expected growth trajectory
# - Potential exits or IPO timeline
# - Strategic initiatives

# ## 8. Disclosure Gaps
# List of information not found or disclosed:
# - Missing financial metrics
# - Undisclosed partnerships
# - Unknown customer details
# - Other data gaps

# **Important**: Use "Not disclosed" for any information not found in source data.
# Do not hallucinate or speculate on missing information."""

#     return PromptResponse(
#         prompt_id="pe-dashboard",
#         template=template,
#         description="8-section PE due diligence dashboard template with mandatory sections"
#     )

# # ============================================================================
# # MCP DISCOVERY ENDPOINT
# # ============================================================================

# @app.get("/mcp/discover")
# async def mcp_discover():
#     """
#     MCP Discovery: Lists all available tools, resources, and prompts
#     """
#     return {
#         "mcp_version": "2024-11-05",
#         "server_info": {
#             "name": "PE Due Diligence MCP Server",
#             "version": "1.0.0",
#             "description": "Provides tools for AI agent-driven PE analysis"
#         },
#         "capabilities": {
#             "tools": [
#                 {
#                     "name": "generate_structured_dashboard",
#                     "description": "Generate dashboard using structured Pydantic data from payloads",
#                     "endpoint": "/tool/generate_structured_dashboard",
#                     "method": "POST",
#                     "input_schema": {
#                         "company_id": "string (required)"
#                     },
#                     "implementation": "tools/payload_tool.py"
#                 },
#                 {
#                     "name": "generate_rag_dashboard",
#                     "description": "Generate dashboard using RAG with ChromaDB vector search",
#                     "endpoint": "/tool/generate_rag_dashboard",
#                     "method": "POST",
#                     "input_schema": {
#                         "company_id": "string (required)",
#                         "top_k": "integer (optional, default=5)",
#                         "query": "string (optional)"
#                     },
#                     "implementation": "tools/rag_tool.py"
#                 },
#                 {
#                     "name": "generate_unified_dashboard",
#                     "description": "Generate dashboard combining structured Pydantic data with RAG fallback for missing sections. DEFAULT: Uses structured data first (prefer_structured=true). Most users don't need to change this.",
#                     "endpoint": "/tool/generate_unified_dashboard",
#                     "method": "POST",
#                     "input_schema": {
#                         "company_id": "string (required)",
#                         "top_k": "integer (optional, default=5)",
#                         "prefer_structured": "boolean (optional, default=true) - Most users should use default. Set to false only if you want RAG-first mode."
#                     },
#                     "implementation": "Combines tools/payload_tool.py + tools/rag_tool.py"
#                 },
#                 {
#                     "name": "report_risk",
#                     "description": "Log risk signals that may require human review (HITL)",
#                     "endpoint": "/tool/report_risk",
#                     "method": "POST",
#                     "input_schema": {
#                         "company_id": "string (required)",
#                         "occurred_on": "date (required, ISO format)",
#                         "description": "string (required)",
#                         "source_url": "string (required, valid URL)",
#                         "risk_type": "enum (required): layoff|security_incident|regulatory|financial_distress|leadership_crisis|legal_action|product_recall|market_disruption|other",
#                         "severity": "enum (optional, default=medium): low|medium|high|critical"
#                     },
#                     "implementation": "tools/risk_logger.py"
#                 }
#             ],
#             "resources": [
#                 {
#                     "name": "ai50/companies",
#                     "description": "List of all 50 AI companies available for analysis",
#                     "endpoint": "/resource/ai50/companies",
#                     "method": "GET"
#                 }
#             ],
#             "prompts": [
#                 {
#                     "name": "pe-dashboard",
#                     "description": "8-section PE dashboard template",
#                     "endpoint": "/prompt/pe-dashboard",
#                     "method": "GET"
#                 }
#             ]
#         }
#     }

# # ============================================================================
# # HELPER FUNCTIONS
# # ============================================================================

# def generate_dashboard_from_payload(payload, company_id: str) -> str:
#     """Generate markdown dashboard from structured payload with CORRECT sections"""
    
#     company_record = payload.company_record
    
#     # Helper for safe access
#     def safe_get(obj, attr, default="Not disclosed"):
#         if obj is None:
#             return default
#         value = getattr(obj, attr, None)
#         return value if value is not None else default
    
#     company_name = safe_get(company_record, 'brand_name') or \
#                   safe_get(company_record, 'legal_name', company_id.title())
    
#     markdown = f"""# PE Dashboard for {company_name}

# ## 1. Company Overview
# **Legal Name:** {safe_get(company_record, 'legal_name')}
# **Brand Name:** {safe_get(company_record, 'brand_name')}
# **Company ID:** {company_id}
# **Website:** {safe_get(company_record, 'website')}
# **Industry:** {', '.join(company_record.categories) if company_record.categories else 'Not disclosed'}
# **Founded:** {safe_get(company_record, 'founded_year')}
# **Headquarters:** {safe_get(company_record, 'hq_city')}, {safe_get(company_record, 'hq_state')}, {safe_get(company_record, 'hq_country')}

# ## 2. Business Model and GTM
# """
    
#     # Extract business model from products and events
#     if payload.products:
#         markdown += "**Products/Services:**\n"
#         for product in payload.products:
#             markdown += f"- **{product.name}**: {product.description or 'No description'}\n"
#             if product.pricing_model:
#                 markdown += f"  - Pricing: {product.pricing_model}\n"
#             if product.pricing_tiers_public:
#                 markdown += f"  - Tiers: {', '.join(product.pricing_tiers_public)}\n"
    
#     # GTM strategy from categories and partnerships
#     if company_record.categories:
#         markdown += f"\n**Target Market:** {', '.join(company_record.categories)}\n"
    
#     partnership_events = [e for e in payload.events if e.event_type == "partnership"]
#     if partnership_events:
#         markdown += "\n**Key Partnerships:**\n"
#         for event in partnership_events[:3]:
#             markdown += f"- {event.title} ({event.occurred_on.isoformat()})\n"
    
#     if not payload.products and not partnership_events:
#         markdown += "Not disclosed\n"
    
#     markdown += "\n## 3. Funding & Investor Profile\n"
    
#     total_raised = safe_get(company_record, 'total_raised_usd')
#     last_valuation = safe_get(company_record, 'last_disclosed_valuation_usd')
#     last_round = safe_get(company_record, 'last_round_name')
    
#     if total_raised != "Not disclosed":
#         markdown += f"**Total Raised:** ${float(total_raised):,.0f} USD\n"
#     if last_valuation != "Not disclosed":
#         markdown += f"**Last Valuation:** ${float(last_valuation):,.0f} USD\n"
#     if last_round != "Not disclosed":
#         markdown += f"**Last Round:** {last_round}\n"
    
#     funding_events = [e for e in payload.events if e.event_type == "funding"]
#     if funding_events:
#         markdown += "\n**Funding Events:**\n"
#         for event in sorted(funding_events, key=lambda e: e.occurred_on, reverse=True):
#             markdown += f"\n**{event.title}** ({event.occurred_on.isoformat()})\n"
#             if event.round_name:
#                 markdown += f"- Round: {event.round_name}\n"
#             if event.amount_usd:
#                 markdown += f"- Amount: ${event.amount_usd:,.0f} USD\n"
#             if event.valuation_usd:
#                 markdown += f"- Valuation: ${event.valuation_usd:,.0f} USD\n"
#             if event.investors:
#                 markdown += f"- Investors: {', '.join(event.investors)}\n"
    
#     markdown += "\n## 4. Growth Momentum\n"
    
#     if payload.snapshots:
#         latest = max(payload.snapshots, key=lambda s: s.as_of)
        
#         if latest.headcount_total:
#             markdown += f"**Headcount:** {latest.headcount_total:,} employees\n"
#         if latest.headcount_growth_pct:
#             markdown += f"**Headcount Growth:** {latest.headcount_growth_pct:.1f}%\n"
#         if latest.job_openings_count:
#             markdown += f"**Active Job Openings:** {latest.job_openings_count}\n"
#         if latest.hiring_focus:
#             markdown += f"**Hiring Focus:** {', '.join(latest.hiring_focus)}\n"
#     else:
#         markdown += "Not disclosed\n"
    
#     markdown += "\n## 5. Visibility & Market Sentiment\n"
    
#     if payload.visibility:
#         latest_vis = max(payload.visibility, key=lambda v: v.as_of)
        
#         if latest_vis.news_mentions_30d:
#             markdown += f"**News Mentions (30 days):** {latest_vis.news_mentions_30d}\n"
#         if latest_vis.avg_sentiment:
#             markdown += f"**Average Sentiment:** {latest_vis.avg_sentiment:.2f}\n"
#         if latest_vis.github_stars:
#             markdown += f"**GitHub Stars:** {latest_vis.github_stars:,}\n"
#         if latest_vis.glassdoor_rating:
#             markdown += f"**Glassdoor Rating:** {latest_vis.glassdoor_rating:.1f}/5.0\n"
#     else:
#         markdown += "Not disclosed\n"
    
#     markdown += "\n## 6. Risks and Challenges\n"
    
#     # Find risk events
#     risk_events = [e for e in payload.events if e.event_type in [
#         "layoff", "security_incident", "regulatory", "legal_action", 
#         "leadership_change"
#     ]]
    
#     if risk_events:
#         for event in sorted(risk_events, key=lambda e: e.occurred_on, reverse=True):
#             event_type_display = event.event_type.replace("_", " ").title()
#             markdown += f"- **{event_type_display}** ({event.occurred_on.isoformat()}): {event.title}\n"
#             if event.description:
#                 markdown += f"  - {event.description}\n"
#     else:
#         markdown += "No significant risks identified\n"
    
#     markdown += "\n## 7. Outlook\n"
    
#     # Recent strategic events
#     strategic_events = [e for e in payload.events if e.event_type in [
#         "product_release", "partnership", "mna", "office_open"
#     ]]
    
#     if strategic_events:
#         markdown += "**Recent Strategic Initiatives:**\n"
#         for event in sorted(strategic_events, key=lambda e: e.occurred_on, reverse=True)[:5]:
#             markdown += f"- {event.title} ({event.occurred_on.isoformat()})\n"
#     else:
#         markdown += "Not disclosed\n"
    
#     markdown += "\n## 8. Disclosure Gaps\n"
    
#     gaps = []
    
#     if not company_record.website or company_record.website == "Not disclosed":
#         gaps.append("Company website")
#     if not company_record.founded_year:
#         gaps.append("Founded year")
#     if not company_record.categories:
#         gaps.append("Industry categories")
#     if not company_record.total_raised_usd:
#         gaps.append("Total funding raised")
#     if not payload.leadership:
#         gaps.append("Leadership team details")
#     if not payload.products:
#         gaps.append("Product information")
#     if not payload.snapshots:
#         gaps.append("Employee and growth metrics")
#     if not payload.visibility:
#         gaps.append("Visibility and sentiment data")
    
#     if gaps:
#         markdown += "**Missing Information:**\n"
#         for gap in gaps:
#             markdown += f"- {gap}\n"
#     else:
#         markdown += "All key information available\n"
    
#     markdown += f"\n---\n*Generated from structured payload | Schema Version: {company_record.schema_version}*\n"
    
#     return markdown

# def generate_dashboard_from_rag(rag_results: dict, company_id: str, top_k: int) -> str:
#     """Generate markdown dashboard from RAG search results"""
    
#     markdown = f"""# PE Dashboard for {company_id.title()} (RAG-Generated)

# ## 1. Company Overview
# """
    
#     overview_chunks = rag_results.get("Company Overview", [])
#     if overview_chunks and len(overview_chunks) > 0:
#         markdown += f"{overview_chunks[0].get('text', 'Not disclosed')}\n"
#     else:
#         markdown += "Not disclosed\n"
    
#     markdown += "\n## 2. Funding History\n"
#     funding_chunks = rag_results.get("Funding History", [])
#     if funding_chunks:
#         for chunk in funding_chunks[:3]:
#             markdown += f"- {chunk.get('text', 'Not disclosed')}\n"
#     else:
#         markdown += "Not disclosed\n"
    
#     markdown += "\n## 3. Leadership\n"
#     leadership_chunks = rag_results.get("Leadership", [])
#     if leadership_chunks:
#         for chunk in leadership_chunks[:3]:
#             markdown += f"- {chunk.get('text', 'Not disclosed')}\n"
#     else:
#         markdown += "Not disclosed\n"
    
#     markdown += "\n## 4. Product/Technology\n"
#     product_chunks = rag_results.get("Product/Technology", [])
#     if product_chunks and len(product_chunks) > 0:
#         markdown += f"{product_chunks[0].get('text', 'Not disclosed')}\n"
#     else:
#         markdown += "Not disclosed\n"
    
#     markdown += "\n## 5. Market Position\n"
#     market_chunks = rag_results.get("Market Position", [])
#     if market_chunks and len(market_chunks) > 0:
#         markdown += f"{market_chunks[0].get('text', 'Not disclosed')}\n"
#     else:
#         markdown += "Not disclosed\n"
    
#     markdown += "\n## 6. Recent Developments\n"
#     news_chunks = rag_results.get("Recent Developments", [])
#     if news_chunks:
#         for chunk in news_chunks[:3]:
#             markdown += f"- {chunk.get('text', 'Not disclosed')}\n"
#     else:
#         markdown += "Not disclosed\n"
    
#     markdown += "\n## 7. Key Metrics\n"
#     metrics_chunks = rag_results.get("Key Metrics", [])
#     if metrics_chunks and len(metrics_chunks) > 0:
#         markdown += f"{metrics_chunks[0].get('text', 'Not disclosed')}\n"
#     else:
#         markdown += "Not disclosed\n"
    
#     markdown += "\n## 8. Risk Factors\n"
#     risk_chunks = rag_results.get("Risk Factors", [])
#     if risk_chunks:
#         for chunk in risk_chunks[:3]:
#             markdown += f"- {chunk.get('text', 'Not disclosed')}\n"
#     else:
#         markdown += "Not disclosed\n"
    
#     markdown += f"\n---\n*Generated using RAG with top_k={top_k}*\n"
    
#     return markdown

# def clean_rag_text(text: str, max_length: int = 500) -> str:
#     """Clean and truncate RAG text for better readability"""
#     if not text:
#         return "Not disclosed"
    
#     # Remove excessive whitespace
#     text = " ".join(text.split())
    
#     # Truncate if too long
#     if len(text) > max_length:
#         text = text[:max_length].rsplit(' ', 1)[0] + "..."
    
#     return text

# def generate_unified_dashboard_structured_first(
#     structured_payload,
#     rag_results: dict,
#     company_id: str,
#     data_sources: dict
# ) -> str:
#     """Generate unified dashboard preferring structured data, using RAG as fallback"""
    
#     company_record = structured_payload.company_record
    
#     def safe_get(obj, attr, default="Not disclosed"):
#         if obj is None:
#             return default
#         value = getattr(obj, attr, None)
#         return value if value is not None else default
    
#     company_name = safe_get(company_record, 'brand_name') or \
#                   safe_get(company_record, 'legal_name', company_id.title())
    
#     markdown = f"""# PE Dashboard for {company_name} (Unified)

# ## 1. Company Overview
# """
    
#     # Try structured first
#     website = safe_get(company_record, 'website')
#     legal_name = safe_get(company_record, 'legal_name')
#     brand_name = safe_get(company_record, 'brand_name')
    
#     has_structured_overview = (
#         website != "Not disclosed" or 
#         legal_name != "Not disclosed" or
#         company_record.categories
#     )
    
#     if has_structured_overview:
#         if legal_name != "Not disclosed":
#             markdown += f"**Legal Name:** {legal_name}\n"
#         if brand_name != "Not disclosed" and brand_name != legal_name:
#             markdown += f"**Brand Name:** {brand_name}\n"
#         if website != "Not disclosed":
#             markdown += f"**Website:** {website}\n"
#         markdown += f"**Industry:** {', '.join(company_record.categories) if company_record.categories else 'Not disclosed'}\n"
        
#         founded = safe_get(company_record, 'founded_year')
#         if founded != "Not disclosed":
#             markdown += f"**Founded:** {founded}\n"
        
#         hq_city = safe_get(company_record, 'hq_city')
#         hq_state = safe_get(company_record, 'hq_state')
#         hq_country = safe_get(company_record, 'hq_country')
        
#         location_parts = [p for p in [hq_city, hq_state, hq_country] if p != "Not disclosed"]
#         if location_parts:
#             markdown += f"**Headquarters:** {', '.join(location_parts)}\n"
        
#         data_sources["Company Overview"] = "structured"
#     else:
#         # Fallback to RAG
#         overview_chunks = rag_results.get("Company Overview", [])
#         if overview_chunks:
#             cleaned_text = clean_rag_text(overview_chunks[0].get('text', ''))
#             markdown += f"{cleaned_text}\n"
#             data_sources["Company Overview"] = "rag"
#         else:
#             markdown += "Not disclosed\n"
#             data_sources["Company Overview"] = "none"
    
#     markdown += "\n## 2. Business Model and GTM\n"
    
#     # Try products from structured
#     has_structured_gtm = structured_payload.products or any(
#         e.event_type == "partnership" for e in structured_payload.events
#     )
    
#     if has_structured_gtm:
#         if structured_payload.products:
#             markdown += "**Products/Services:**\n"
#             for product in structured_payload.products:
#                 markdown += f"- **{product.name}**"
#                 if product.description:
#                     markdown += f": {product.description[:200]}{'...' if len(product.description) > 200 else ''}\n"
#                 else:
#                     markdown += "\n"
#                 if product.pricing_model:
#                     markdown += f"  - Pricing Model: {product.pricing_model}\n"
        
#         # Add partnerships
#         partnership_events = [e for e in structured_payload.events if e.event_type == "partnership"]
#         if partnership_events:
#             markdown += "\n**Key Partnerships:**\n"
#             for event in partnership_events[:3]:
#                 markdown += f"- {event.title}"
#                 if hasattr(event, 'occurred_on') and event.occurred_on:
#                     markdown += f" ({event.occurred_on.isoformat()})"
#                 markdown += "\n"
        
#         data_sources["Business Model and GTM"] = "structured"
#     else:
#         # Fallback to RAG
#         gtm_chunks = rag_results.get("Business Model and GTM", [])
#         if gtm_chunks:
#             markdown += "**Business Overview:**\n"
#             for i, chunk in enumerate(gtm_chunks[:2]):
#                 cleaned = clean_rag_text(chunk.get('text', ''), max_length=300)
#                 if cleaned != "Not disclosed":
#                     markdown += f"{cleaned}\n\n"
#             data_sources["Business Model and GTM"] = "rag"
#         else:
#             markdown += "Not disclosed\n"
#             data_sources["Business Model and GTM"] = "none"
    
#     markdown += "\n## 3. Funding & Investor Profile\n"
    
#     # Try structured funding data
#     total_raised = safe_get(company_record, 'total_raised_usd')
#     has_structured_funding = total_raised != "Not disclosed" or any(
#         e.event_type == "funding" for e in structured_payload.events
#     )
    
#     if has_structured_funding:
#         if total_raised != "Not disclosed":
#             markdown += f"**Total Raised:** ${float(total_raised):,.0f} USD\n"
        
#         last_valuation = safe_get(company_record, 'last_disclosed_valuation_usd')
#         if last_valuation != "Not disclosed":
#             markdown += f"**Last Valuation:** ${float(last_valuation):,.0f} USD\n"
        
#         last_round = safe_get(company_record, 'last_round_name')
#         if last_round != "Not disclosed":
#             markdown += f"**Last Round:** {last_round}\n"
        
#         funding_events = [e for e in structured_payload.events if e.event_type == "funding"]
#         if funding_events:
#             markdown += "\n**Funding History:**\n"
#             for event in sorted(funding_events, key=lambda e: e.occurred_on, reverse=True)[:5]:
#                 markdown += f"- **{event.title}**"
#                 if hasattr(event, 'occurred_on') and event.occurred_on:
#                     markdown += f" ({event.occurred_on.isoformat()})"
#                 if hasattr(event, 'amount_usd') and event.amount_usd:
#                     markdown += f" - ${event.amount_usd:,.0f}"
#                 if hasattr(event, 'investors') and event.investors:
#                     investors_short = event.investors[:3]
#                     markdown += f" - {', '.join(investors_short)}"
#                     if len(event.investors) > 3:
#                         markdown += f" +{len(event.investors)-3} more"
#                 markdown += "\n"
        
#         data_sources["Funding & Investor Profile"] = "structured"
#     else:
#         # Fallback to RAG
#         funding_chunks = rag_results.get("Funding & Investor Profile", [])
#         if funding_chunks:
#             markdown += "**Funding Information:**\n"
#             for chunk in funding_chunks[:3]:
#                 cleaned = clean_rag_text(chunk.get('text', ''), max_length=250)
#                 if cleaned != "Not disclosed":
#                     markdown += f"- {cleaned}\n"
#             data_sources["Funding & Investor Profile"] = "rag"
#         else:
#             markdown += "Not disclosed\n"
#             data_sources["Funding & Investor Profile"] = "none"
    
#     markdown += "\n## 4. Growth Momentum\n"
    
#     # Try structured metrics
#     has_structured_growth = bool(structured_payload.snapshots)
    
#     if has_structured_growth:
#         latest = max(structured_payload.snapshots, key=lambda s: s.as_of)
        
#         metrics_found = False
#         if hasattr(latest, 'headcount_total') and latest.headcount_total:
#             markdown += f"**Employee Count:** {latest.headcount_total:,}\n"
#             metrics_found = True
#         if hasattr(latest, 'headcount_growth_pct') and latest.headcount_growth_pct:
#             markdown += f"**Headcount Growth:** {latest.headcount_growth_pct:.1f}%\n"
#             metrics_found = True
#         if hasattr(latest, 'job_openings_count') and latest.job_openings_count:
#             markdown += f"**Active Job Openings:** {latest.job_openings_count}\n"
#             metrics_found = True
#         if hasattr(latest, 'hiring_focus') and latest.hiring_focus:
#             markdown += f"**Hiring Focus:** {', '.join(latest.hiring_focus)}\n"
#             metrics_found = True
        
#         if metrics_found:
#             data_sources["Growth Momentum"] = "structured"
#         else:
#             markdown += "Not disclosed\n"
#             data_sources["Growth Momentum"] = "none"
#     else:
#         # Fallback to RAG
#         growth_chunks = rag_results.get("Growth Momentum", [])
#         if growth_chunks:
#             cleaned = clean_rag_text(growth_chunks[0].get('text', ''), max_length=400)
#             markdown += f"{cleaned}\n"
#             data_sources["Growth Momentum"] = "rag"
#         else:
#             markdown += "Not disclosed\n"
#             data_sources["Growth Momentum"] = "none"
    
#     markdown += "\n## 5. Visibility & Market Sentiment\n"
    
#     # Try structured visibility data
#     has_structured_visibility = bool(structured_payload.visibility)
    
#     if has_structured_visibility:
#         latest_vis = max(structured_payload.visibility, key=lambda v: v.as_of)
        
#         visibility_found = False
#         if hasattr(latest_vis, 'news_mentions_30d') and latest_vis.news_mentions_30d:
#             markdown += f"**News Mentions (30 days):** {latest_vis.news_mentions_30d}\n"
#             visibility_found = True
#         if hasattr(latest_vis, 'avg_sentiment') and latest_vis.avg_sentiment:
#             sentiment_label = "Positive" if latest_vis.avg_sentiment > 0.6 else "Neutral" if latest_vis.avg_sentiment > 0.4 else "Negative"
#             markdown += f"**Market Sentiment:** {sentiment_label} ({latest_vis.avg_sentiment:.2f})\n"
#             visibility_found = True
#         if hasattr(latest_vis, 'github_stars') and latest_vis.github_stars:
#             markdown += f"**GitHub Stars:** {latest_vis.github_stars:,}\n"
#             visibility_found = True
#         if hasattr(latest_vis, 'glassdoor_rating') and latest_vis.glassdoor_rating:
#             markdown += f"**Glassdoor Rating:** {latest_vis.glassdoor_rating:.1f}/5.0\n"
#             visibility_found = True
        
#         if visibility_found:
#             data_sources["Visibility & Market Sentiment"] = "structured"
#         else:
#             markdown += "Not disclosed\n"
#             data_sources["Visibility & Market Sentiment"] = "none"
#     else:
#         # Fallback to RAG
#         visibility_chunks = rag_results.get("Visibility & Market Sentiment", [])
#         if visibility_chunks:
#             cleaned = clean_rag_text(visibility_chunks[0].get('text', ''), max_length=400)
#             markdown += f"{cleaned}\n"
#             data_sources["Visibility & Market Sentiment"] = "rag"
#         else:
#             markdown += "Not disclosed\n"
#             data_sources["Visibility & Market Sentiment"] = "none"
    
#     markdown += "\n## 6. Risks and Challenges\n"
    
#     # Try structured risk events
#     risk_events = [e for e in structured_payload.events if e.event_type in [
#         "layoff", "security_incident", "regulatory", "legal_action", "leadership_change"
#     ]]
    
#     if risk_events:
#         for event in sorted(risk_events, key=lambda e: e.occurred_on, reverse=True)[:5]:
#             event_type = event.event_type.replace("_", " ").title()
#             markdown += f"- **{event_type}**"
#             if hasattr(event, 'occurred_on') and event.occurred_on:
#                 markdown += f" ({event.occurred_on.isoformat()})"
#             markdown += f": {event.title}\n"
#             if hasattr(event, 'description') and event.description:
#                 desc = event.description[:150] + "..." if len(event.description) > 150 else event.description
#                 markdown += f"  {desc}\n"
#         data_sources["Risks and Challenges"] = "structured"
#     else:
#         # Fallback to RAG
#         risk_chunks = rag_results.get("Risks and Challenges", [])
#         if risk_chunks and any(chunk.get('text') for chunk in risk_chunks):
#             markdown += "**Identified Challenges:**\n"
#             for chunk in risk_chunks[:3]:
#                 cleaned = clean_rag_text(chunk.get('text', ''), max_length=200)
#                 if cleaned != "Not disclosed" and len(cleaned) > 20:  # Filter out noise
#                     markdown += f"- {cleaned}\n"
#             data_sources["Risks and Challenges"] = "rag"
#         else:
#             markdown += "No significant risks identified in available data\n"
#             data_sources["Risks and Challenges"] = "none"
    
#     markdown += "\n## 7. Outlook\n"
    
#     # Try strategic events from structured
#     strategic_events = [e for e in structured_payload.events if e.event_type in [
#         "product_release", "partnership", "mna", "office_open"
#     ]]
    
#     if strategic_events:
#         markdown += "**Recent Strategic Initiatives:**\n"
#         for event in sorted(strategic_events, key=lambda e: e.occurred_on, reverse=True)[:5]:
#             markdown += f"- {event.title}"
#             if hasattr(event, 'occurred_on') and event.occurred_on:
#                 markdown += f" ({event.occurred_on.isoformat()})"
#             markdown += "\n"
#         data_sources["Outlook"] = "structured"
#     else:
#         # Fallback to RAG
#         outlook_chunks = rag_results.get("Outlook", [])
#         if outlook_chunks:
#             cleaned = clean_rag_text(outlook_chunks[0].get('text', ''), max_length=400)
#             if cleaned != "Not disclosed" and len(cleaned) > 20:
#                 markdown += f"{cleaned}\n"
#                 data_sources["Outlook"] = "rag"
#             else:
#                 markdown += "Not disclosed\n"
#                 data_sources["Outlook"] = "none"
#         else:
#             markdown += "Not disclosed\n"
#             data_sources["Outlook"] = "none"
    
#     markdown += "\n## 8. Disclosure Gaps\n"
    
#     gaps = []
#     if not company_record.website or company_record.website == "Not disclosed":
#         gaps.append("Company website")
#     if not company_record.founded_year:
#         gaps.append("Founded year")
#     if not structured_payload.leadership:
#         gaps.append("Leadership team details")
#     if not structured_payload.products:
#         gaps.append("Product information")
    
#     if gaps:
#         markdown += "**Missing from Structured Data:**\n"
#         for gap in gaps:
#             markdown += f"- {gap}\n"
#     else:
#         markdown += "All key structured information available\n"
    
#     data_sources["Disclosure Gaps"] = "analysis"
    
#     # Add data source summary
#     markdown += f"\n---\n**Data Sources Used:**\n"
#     for section, source in data_sources.items():
#         emoji = "📊" if source == "structured" else "🔍" if source == "rag" else "❌"
#         markdown += f"- {emoji} {section}: {source}\n"
    
#     markdown += f"\n*Generated with unified pipeline (prefer_structured=True)*\n"
    
#     return markdown


# def generate_unified_dashboard_rag_first(
#     rag_results: dict,
#     structured_payload,
#     company_id: str,
#     data_sources: dict
# ) -> str:
#     """Generate unified dashboard preferring RAG, using structured as enhancement"""
#     from openai import OpenAI
    
#     company_name = company_id.title()
#     founded_year = None
    
#     # If we have structured data, get company name and basic info
#     if structured_payload:
#         company_record = structured_payload.company_record
#         company_name = getattr(company_record, 'brand_name', None) or \
#                       getattr(company_record, 'legal_name', company_name)
#         founded_year = getattr(company_record, 'founded_year', None)
    
#     # Format RAG context for LLM
#     context = f"# Company Data: {company_name}\n\n"
    
#     for section_name, chunks in rag_results.items():
#         if chunks:
#             context += f"## {section_name}\n"
#             for i, chunk in enumerate(chunks[:3], 1):
#                 text = chunk.get('text', '')
#                 if text and len(text) > 50:  # Filter out noise
#                     context += f"**Source {i}:** {text[:400]}...\n\n"
    
#     # Add structured data enhancements
#     if structured_payload:
#         context += "\n## Additional Structured Data\n"
#         company_record = structured_payload.company_record
        
#         if company_record.website:
#             context += f"- Website: {company_record.website}\n"
#         if founded_year:
#             context += f"- Founded: {founded_year}\n"
#         if company_record.total_raised_usd:
#             context += f"- Total Raised: ${company_record.total_raised_usd:,.0f}\n"
    
#     # Call OpenAI to generate structured dashboard
#     system_prompt = """You are a PE analyst generating investor dashboards. Create a professional, well-structured 8-section dashboard.

# Rules:
# - Synthesize information from multiple sources into coherent narratives
# - If information is missing, write "Not disclosed"
# - Be concise and factual
# - Format numbers properly (e.g., $100M, 500 employees)
# - Use bullet points for lists
# - Avoid repeating information across sections

# Generate exactly these 8 sections:
# 1. Company Overview
# 2. Business Model and GTM  
# 3. Funding & Investor Profile
# 4. Growth Momentum
# 5. Visibility & Market Sentiment
# 6. Risks and Challenges
# 7. Outlook
# 8. Disclosure Gaps"""

#     user_prompt = f"""Generate a PE dashboard for {company_name}.

# {context}

# Create a professional markdown dashboard with all 8 sections. Synthesize the information coherently."""

#     try:
#         client = OpenAI(api_key=os.getenv('OPENAI_KEY'))
#         response = client.chat.completions.create(
#             model="gpt-4o",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_prompt}
#             ],
#             temperature=0.3,
#             max_tokens=4000
#         )
        
#         markdown = response.choices[0].message.content
        
#         # Track data sources
#         for section in ["Company Overview", "Business Model and GTM", "Funding & Investor Profile",
#                        "Growth Momentum", "Visibility & Market Sentiment", "Risks and Challenges",
#                        "Outlook", "Disclosure Gaps"]:
#             data_sources[section] = "rag+structured" if structured_payload else "rag"
        
#         # Add data source summary
#         markdown += f"\n\n---\n**Data Sources Used:**\n"
#         for section, source in data_sources.items():
#             emoji = "🔍" if "rag" in source else "📊" if source == "structured" else "❌"
#             markdown += f"- {emoji} {section}: {source}\n"
        
#         markdown += f"\n*Generated with unified pipeline (prefer_structured=False) using GPT-4o*\n"
        
#         return markdown
        
#     except Exception as e:
#         print(f"Error calling OpenAI: {e}")
#         # Fallback to simple formatting
#         return f"# PE Dashboard for {company_name}\n\nError generating dashboard: {str(e)}"

# # ============================================================================
# # RUN SERVER
# # ============================================================================

# if __name__ == "__main__":
#     import uvicorn
    
#     port = int(os.getenv("MCP_SERVER_PORT", "8100"))
    
#     print(f"""
#     ╔═══════════════════════════════════════════════════════════╗
#     ║           MCP SERVER STARTING                             ║
#     ║  Model Context Protocol for PE Due Diligence              ║
#     ╠═══════════════════════════════════════════════════════════╣
#     ║  Port:        {port}                                       ║
#     ║  Tools:       4 (structured, rag, unified, risk)          ║
#     ║  Resources:   1 (company list)                            ║
#     ║  Prompts:     1 (dashboard template)                      ║
#     ╚═══════════════════════════════════════════════════════════╝
    
#     📍 Endpoints:
#        GET  http://localhost:{port}/
#        GET  http://localhost:{port}/health
#        GET  http://localhost:{port}/mcp/discover
#        GET  http://localhost:{port}/resource/ai50/companies
#        GET  http://localhost:{port}/prompt/pe-dashboard
#        POST http://localhost:{port}/tool/generate_structured_dashboard
#        POST http://localhost:{port}/tool/generate_rag_dashboard
#        POST http://localhost:{port}/tool/generate_unified_dashboard
#        POST http://localhost:{port}/tool/report_risk
    
#     📚 Docs: http://localhost:{port}/docs
    
#     🔧 Connected Tools:
#        ✓ tools/payload_tool.py (get_latest_structured_payload)
#        ✓ tools/rag_tool.py (rag_search_company)
#        ✓ tools/risk_logger.py (report_risk_signal)
#        ✓ Unified Dashboard (combines structured + RAG)
#     """)
    
#     uvicorn.run(
#         app,
#         host="0.0.0.0",
#         port=port,
#         reload=True
#     )

"""
MCP Server - Model Context Protocol Implementation
Exposes tools, resources, and prompts for AI agents
Now fetches data from GCS and uses GPT for structured output
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Dict, Optional, Literal
from datetime import date, datetime, timezone
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Import GCS storage client
try:
    from storage.gcs_client import DashboardStorage
    GCS_AVAILABLE = True
    logger.info("✅ GCS module loaded")
except ImportError as e:
    logger.warning(f"⚠️ GCS not available: {e}")
    DashboardStorage = None
    GCS_AVAILABLE = False

# Import your tools
from tools.payload_tool import get_latest_structured_payload
from tools.rag_tool import rag_search_company
from tools.risk_logger import report_risk_signal, RiskSignal

app = FastAPI(
    title="MCP Server - PE Due Diligence",
    description="Model Context Protocol server for AI agent tool access with GCS integration",
    version="2.0.0"
)

# Initialize GCS storage
gcs_storage = None
if GCS_AVAILABLE:
    try:
        bucket_name = os.getenv('GCS_BUCKET_NAME', 'ai-pe-dashboard')
        gcs_storage = DashboardStorage(bucket_name)
        print(f"✅ GCS Storage initialized: {bucket_name}")
    except Exception as e:
        print(f"⚠️ GCS initialization failed: {e}")

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ToolRequest(BaseModel):
    company_id: str = Field(..., description="Company identifier (e.g., 'abridge')")

class StructuredDashboardRequest(ToolRequest):
    pass

class RAGDashboardRequest(ToolRequest):
    top_k: int = Field(default=5, description="Number of chunks to retrieve per query")
    query: Optional[str] = Field(default=None, description="Optional search query")

class UnifiedDashboardRequest(ToolRequest):
    top_k: int = Field(default=10, description="Number of RAG chunks to retrieve per query")
    prefer_structured: bool = Field(default=True, description="Prefer structured data when available")
    save_to_gcs: bool = Field(default=True, description="Save dashboard to GCS bucket")
    restructure_with_gpt: bool = Field(default=True, description="Use GPT to restructure fetched dashboard")

class RiskReportRequest(BaseModel):
    company_id: str = Field(..., description="Company identifier")
    occurred_on: date = Field(..., description="Date when risk event occurred")
    description: str = Field(..., description="Description of the risk")
    source_url: HttpUrl = Field(..., description="Source URL of the risk information")
    risk_type: Literal[
        "layoff", "security_incident", "regulatory", "financial_distress",
        "leadership_crisis", "legal_action", "product_recall", 
        "market_disruption", "other"
    ] = Field(..., description="Type of risk")
    severity: Literal["low", "medium", "high", "critical"] = Field(
        default="medium", 
        description="Severity level"
    )

class ToolResponse(BaseModel):
    success: bool
    company_id: str
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict] = None

class UnifiedDashboardResponse(BaseModel):
    success: bool
    company_id: str
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict] = None
    data_sources: Dict[str, str] = Field(default_factory=dict)
    gcs_uri: Optional[str] = None

class CompanyListResponse(BaseModel):
    companies: List[str]
    count: int

class PromptResponse(BaseModel):
    prompt_id: str
    template: str
    description: str

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/")
async def root():
    return {
        "service": "MCP Server",
        "status": "healthy",
        "version": "2.0.0",
        "gcs_enabled": GCS_AVAILABLE,
        "endpoints": {
            "tools": 4,
            "resources": 1,
            "prompts": 1
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "mcp_version": "2024-11-05",
        "gcs_available": GCS_AVAILABLE,
        "tools_available": [
            "generate_structured_dashboard",
            "generate_rag_dashboard",
            "generate_unified_dashboard",
            "report_risk"
        ],
        "resources_available": ["ai50/companies"],
        "prompts_available": ["pe-dashboard"]
    }

# ============================================================================
# TOOL ENDPOINTS
# ============================================================================

@app.post("/tool/generate_unified_dashboard", response_model=UnifiedDashboardResponse)
async def tool_generate_unified_dashboard(request: UnifiedDashboardRequest):
    """
    Fetch pre-generated unified dashboard from GCS bucket
    Optionally restructure it using GPT for better formatting
    
    This endpoint retrieves dashboards that were already generated and saved to GCS
    by the supervisor agent or batch processing pipeline.
    """
    try:
        from openai import OpenAI
        from datetime import datetime
        
        company_id = request.company_id
        
        # Check if GCS is available
        if not gcs_storage:
            raise HTTPException(
                status_code=503,
                detail="GCS storage not configured. Check GCS_BUCKET_NAME in .env"
            )
        
        print(f"📥 Fetching dashboard from GCS for: {company_id}")
        
        # Fetch latest unified dashboard from GCS
        dashboard_content = gcs_storage.get_latest_dashboard(
            company_id=company_id,
            dashboard_type="unified"
        )
        
        if not dashboard_content:
            # Dashboard not found in GCS
            return UnifiedDashboardResponse(
                success=False,
                company_id=company_id,
                error=f"No unified dashboard found in GCS for '{company_id}'",
                data_sources={},
                metadata={
                    "error_type": "DashboardNotFound",
                    "suggestion": "Run supervisor agent to generate dashboard first",
                    "command": f"python src/agents/supervisor_mcp.py {company_id}"
                }
            )
        
        print(f"✓ Dashboard retrieved from GCS ({len(dashboard_content)} chars)")
        
        # Parse data sources from dashboard if available
        data_sources = {}
        if "**Data Sources Used:**" in dashboard_content:
            lines = dashboard_content.split("**Data Sources Used:**")[1].split("\n")
            for line in lines:
                if ":" in line and any(emoji in line for emoji in ["📊", "🔍", "❌", "🔄"]):
                    parts = line.split(":")
                    if len(parts) >= 2:
                        section = parts[0].strip("- 📊🔍❌🔄 ")
                        source = parts[1].strip()
                        data_sources[section] = source
        
        # Optionally restructure with GPT
        if request.restructure_with_gpt:
            print(f"🤖 Restructuring dashboard with GPT-4o...")
            
            system_prompt = """You are a PE analyst improving dashboard formatting.

Take the existing dashboard and:
- Clean up any formatting issues
- Ensure all 8 sections are properly formatted
- Remove duplicate information
- Format numbers consistently ($100M, 1,500 employees)
- Improve bullet point structure
- Keep "Not disclosed" for missing data
- Make it more readable and professional

Maintain all factual information - only improve structure and formatting."""

            user_prompt = f"""Improve the formatting and structure of this dashboard:

{dashboard_content}

Return a clean, well-formatted version with all 8 sections properly structured."""

            client = OpenAI(api_key=os.getenv('OPENAI_KEY'))
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,  # Lower temperature for consistency
                max_tokens=4000
            )
            
            dashboard_content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
            print(f"✓ Dashboard restructured ({tokens_used} tokens)")
            
            # Add restructuring note
            dashboard_content += f"\n\n---\n*Fetched from GCS and restructured with GPT-4o ({tokens_used} tokens)*\n"
        else:
            tokens_used = 0
        
        # Return dashboard
        return UnifiedDashboardResponse(
            success=True,
            company_id=company_id,
            result=dashboard_content,
            data_sources=data_sources,
            gcs_uri=f"gs://{os.getenv('GCS_BUCKET_NAME')}/data/dashboards/{company_id}/unified_*.md",
            metadata={
                "source": "gcs_bucket",
                "tool": "unified_dashboard",
                "fetched_from": "google_cloud_storage",
                "dashboard_type": "unified",
                "fetched_at": datetime.now().isoformat(),
                "restructured_with_gpt": request.restructure_with_gpt,
                "tokens_used": tokens_used if request.restructure_with_gpt else 0
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        return UnifiedDashboardResponse(
            success=False,
            company_id=request.company_id,
            error=f"Failed to fetch from GCS: {str(e)}",
            data_sources={},
            metadata={"error_type": type(e).__name__}
        )

@app.post("/tool/generate_structured_dashboard", response_model=ToolResponse)
async def tool_generate_structured_dashboard(request: StructuredDashboardRequest):
    """Generate structured dashboard from Pydantic payloads"""
    try:
        company_id = request.company_id
        
        payload = await get_latest_structured_payload(company_id)
        dashboard_markdown = generate_dashboard_from_payload(payload, company_id)
        
        return ToolResponse(
            success=True,
            company_id=company_id,
            result=dashboard_markdown,
            metadata={
                "source": "structured_pipeline",
                "tool": "payload_tool",
                "sections": 8,
                "type": "markdown",
                "has_events": len(payload.events) > 0,
                "has_leadership": len(payload.leadership) > 0,
                "has_products": len(payload.products) > 0
            }
        )
    
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Company '{request.company_id}' not found in structured data: {str(e)}"
        )
    except Exception as e:
        return ToolResponse(
            success=False,
            company_id=request.company_id,
            error=str(e),
            metadata={"error_type": type(e).__name__}
        )

@app.post("/tool/generate_rag_dashboard", response_model=ToolResponse)
async def tool_generate_rag_dashboard(request: RAGDashboardRequest):
    """Generate RAG dashboard using GPT to structure content"""
    try:
        from openai import OpenAI
        
        company_id = request.company_id
        top_k = request.top_k
        
        sections = [
            ("Company Overview", "company overview business model mission"),
            ("Funding History", "funding history investors series round valuation"),
            ("Leadership", "leadership team executives CEO founder management"),
            ("Product/Technology", "product technology platform features innovation"),
            ("Market Position", "market position competitors industry landscape"),
            ("Recent Developments", "recent news developments announcements updates"),
            ("Key Metrics", "metrics revenue growth employees customers headcount"),
            ("Risk Factors", "risks challenges problems issues concerns")
        ]
        
        # Collect RAG results
        context = f"# Company Data: {company_id}\n\n"
        all_chunks_count = 0
        
        for section_name, query in sections:
            chunks = await rag_search_company(
                company_id=company_id,
                query=request.query or query,
                top_k=top_k
            )
            
            if chunks:
                context += f"## {section_name}\n"
                for i, chunk in enumerate(chunks[:3], 1):
                    text = chunk.get('text', '')
                    if text and len(text) > 30:
                        context += f"**Source {i}:** {text[:500]}...\n\n"
                all_chunks_count += len(chunks)
        
        # Generate with GPT
        system_prompt = """You are a PE analyst generating investor dashboards.

Create a professional, well-structured 8-section dashboard.

Rules:
- Use ONLY information from the provided context
- If information is missing, write "Not disclosed"
- Be concise and factual
- Format numbers properly (e.g., $100M, 500 employees)
- Use bullet points for lists
- Synthesize information coherently

Generate exactly these 8 sections:
1. Company Overview
2. Business Model and GTM
3. Funding & Investor Profile
4. Growth Momentum
5. Visibility & Market Sentiment
6. Risks and Challenges
7. Outlook
8. Disclosure Gaps"""

        user_prompt = f"""Generate a PE dashboard for {company_id}.

{context}

Create a professional markdown dashboard with all 8 sections."""

        client = OpenAI(api_key=os.getenv('OPENAI_KEY'))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        dashboard_markdown = response.choices[0].message.content
        
        return ToolResponse(
            success=True,
            company_id=company_id,
            result=dashboard_markdown,
            metadata={
                "source": "rag_pipeline",
                "tool": "rag_tool",
                "model": "gpt-4o",
                "top_k": top_k,
                "sections": 8,
                "total_chunks_retrieved": all_chunks_count,
                "tokens_used": response.usage.total_tokens
            }
        )
    
    except Exception as e:
        return ToolResponse(
            success=False,
            company_id=request.company_id,
            error=str(e),
            metadata={"error_type": type(e).__name__}
        )

@app.post("/tool/report_risk", response_model=ToolResponse)
async def tool_report_risk(request: RiskReportRequest):
    """Report risk signal and save to GCS"""
    try:
        risk_signal = RiskSignal(
            company_id=request.company_id,
            occurred_on=request.occurred_on,
            description=request.description,
            source_url=request.source_url,
            risk_type=request.risk_type,
            severity=request.severity
        )
        
        success = await report_risk_signal(risk_signal)
        
        if not success:
            return ToolResponse(
                success=False,
                company_id=request.company_id,
                error="Failed to log risk signal"
            )
        
        hitl_required = request.severity in ["high", "critical"]
        
        # Save to GCS if available
        gcs_uri = None
        if gcs_storage:
            try:
                risk_data = [{
                    "company_id": request.company_id,
                    "occurred_on": request.occurred_on.isoformat(),
                    "description": request.description,
                    "source_url": str(request.source_url),
                    "risk_type": request.risk_type,
                    "severity": request.severity,
                    "hitl_required": hitl_required
                }]
                
                gcs_uri = gcs_storage.save_risk_log(request.company_id, risk_data)
            except Exception as e:
                print(f"⚠️ Failed to save risk to GCS: {e}")
        
        return ToolResponse(
            success=True,
            company_id=request.company_id,
            result=f"Risk logged: {request.risk_type} - {request.description}",
            metadata={
                "tool": "risk_logger",
                "hitl_required": hitl_required,
                "severity": request.severity,
                "risk_type": request.risk_type,
                "occurred_on": request.occurred_on.isoformat(),
                "gcs_uri": gcs_uri
            }
        )
    
    except Exception as e:
        return ToolResponse(
            success=False,
            company_id=request.company_id,
            error=str(e),
            metadata={"error_type": type(e).__name__}
        )

# ============================================================================
# RESOURCE ENDPOINTS
# ============================================================================

@app.get("/resource/ai50/companies", response_model=CompanyListResponse)
async def resource_list_companies():
    """List all AI50 companies from forbes_ai50_seed.json"""
    
    companies = []
    
    # Method 1: Read from forbes_ai50_seed.json
    try:
        seed_file = Path(__file__).resolve().parents[2] / "data" / "forbes_ai50_seed.json"
        
        if seed_file.exists():
            with open(seed_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                for item in data:
                    if 'company_name' in item:
                        # Normalize: lowercase, replace spaces with hyphens
                        company_name = item['company_name'].lower().replace(' ', '-')
                        companies.append(company_name)
            
            print(f"✓ Loaded {len(companies)} companies from forbes_ai50_seed.json")
        else:
            print(f"❌ forbes_ai50_seed.json not found at: {seed_file}")
    except Exception as e:
        print(f"Error reading forbes_ai50_seed.json: {e}")
    
    # Method 2: Fallback to payloads directory
    if not companies:
        try:
            data_dir = Path(__file__).resolve().parents[1] / "data" / "payloads"
            if data_dir.exists():
                companies = [f.stem for f in data_dir.glob("*.json")]
                print(f"✓ Found {len(companies)} companies from payloads")
        except Exception as e:
            print(f"Could not scan payloads: {e}")
    
    companies = sorted(list(set(companies)))
    
    return CompanyListResponse(
        companies=companies,
        count=len(companies)
    )

# ============================================================================
# PROMPT ENDPOINTS
# ============================================================================

@app.get("/prompt/pe-dashboard", response_model=PromptResponse)
async def prompt_pe_dashboard():
    """PE Dashboard Template"""
    template = """Generate a Private Equity due diligence dashboard with exactly 8 sections:

## 1. Company Overview
- Company description, industry, founded date, headquarters

## 2. Business Model and GTM
- Revenue model, go-to-market strategy, customer segments, partnerships

## 3. Funding & Investor Profile
- Total funding, series rounds, lead investors, valuation

## 4. Growth Momentum
- Revenue growth, customer growth, employee headcount, expansion

## 5. Visibility & Market Sentiment
- Media mentions, awards, ratings, market perception

## 6. Risks and Challenges
- Competitive threats, regulatory concerns, operational challenges

## 7. Outlook
- Future plans, roadmap, market opportunities, strategic initiatives

## 8. Disclosure Gaps
- Missing financial metrics, undisclosed partnerships, data gaps

Use "Not disclosed" for missing information. Never hallucinate."""

    return PromptResponse(
        prompt_id="pe-dashboard",
        template=template,
        description="8-section PE due diligence dashboard template"
    )

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_dashboard_from_payload(payload, company_id: str) -> str:
    """Generate markdown dashboard from structured payload"""
    
    company_record = payload.company_record
    
    def safe_get(obj, attr, default="Not disclosed"):
        if obj is None:
            return default
        value = getattr(obj, attr, None)
        return value if value is not None else default
    
    company_name = safe_get(company_record, 'brand_name') or \
                  safe_get(company_record, 'legal_name', company_id.title())
    
    markdown = f"""# PE Dashboard for {company_name}

## 1. Company Overview
**Legal Name:** {safe_get(company_record, 'legal_name')}
**Website:** {safe_get(company_record, 'website')}
**Industry:** {', '.join(company_record.categories) if company_record.categories else 'Not disclosed'}
**Founded:** {safe_get(company_record, 'founded_year')}
**Headquarters:** {safe_get(company_record, 'hq_city')}, {safe_get(company_record, 'hq_country')}

## 2. Business Model and GTM
"""
    
    if payload.products:
        markdown += "**Products/Services:**\n"
        for product in payload.products:
            markdown += f"- **{product.name}**: {product.description or 'No description'}\n"
            if product.pricing_model:
                markdown += f"  - Pricing: {product.pricing_model}\n"
    else:
        markdown += "Not disclosed\n"
    
    markdown += "\n## 3. Funding & Investor Profile\n"
    
    total_raised = safe_get(company_record, 'total_raised_usd')
    if total_raised != "Not disclosed":
        markdown += f"**Total Raised:** ${float(total_raised):,.0f} USD\n"
    
    funding_events = [e for e in payload.events if e.event_type == "funding"]
    if funding_events:
        markdown += "\n**Funding History:**\n"
        for event in sorted(funding_events, key=lambda e: e.occurred_on, reverse=True)[:5]:
            markdown += f"- **{event.title}** ({event.occurred_on.isoformat()})"
            if event.amount_usd:
                markdown += f" - ${event.amount_usd:,.0f}"
            if event.investors:
                markdown += f" - {', '.join(event.investors[:3])}"
            markdown += "\n"
    
    markdown += "\n## 4. Growth Momentum\n"
    
    if payload.snapshots:
        latest = max(payload.snapshots, key=lambda s: s.as_of)
        if latest.headcount_total:
            markdown += f"**Employee Count:** {latest.headcount_total:,}\n"
        if latest.headcount_growth_pct:
            markdown += f"**Growth Rate:** {latest.headcount_growth_pct:.1f}%\n"
    else:
        markdown += "Not disclosed\n"
    
    markdown += "\n## 5. Visibility & Market Sentiment\n"
    
    if payload.visibility:
        latest_vis = max(payload.visibility, key=lambda v: v.as_of)
        if latest_vis.news_mentions_30d:
            markdown += f"**News Mentions (30d):** {latest_vis.news_mentions_30d}\n"
        if latest_vis.github_stars:
            markdown += f"**GitHub Stars:** {latest_vis.github_stars:,}\n"
    else:
        markdown += "Not disclosed\n"
    
    markdown += "\n## 6. Risks and Challenges\n"
    
    risk_events = [e for e in payload.events if e.event_type in [
        "layoff", "security_incident", "regulatory", "legal_action"
    ]]
    
    if risk_events:
        for event in sorted(risk_events, key=lambda e: e.occurred_on, reverse=True):
            markdown += f"- **{event.event_type.title()}** ({event.occurred_on.isoformat()}): {event.title}\n"
    else:
        markdown += "No significant risks identified\n"
    
    markdown += "\n## 7. Outlook\n"
    
    strategic_events = [e for e in payload.events if e.event_type in [
        "product_release", "partnership", "mna"
    ]]
    
    if strategic_events:
        markdown += "**Recent Strategic Initiatives:**\n"
        for event in sorted(strategic_events, key=lambda e: e.occurred_on, reverse=True)[:5]:
            markdown += f"- {event.title} ({event.occurred_on.isoformat()})\n"
    else:
        markdown += "Not disclosed\n"
    
    markdown += "\n## 8. Disclosure Gaps\n"
    
    gaps = []
    if not company_record.website or company_record.website == "Not disclosed":
        gaps.append("Company website")
    if not payload.leadership:
        gaps.append("Leadership team details")
    if not payload.products:
        gaps.append("Product information")
    
    if gaps:
        markdown += "**Missing Information:**\n"
        for gap in gaps:
            markdown += f"- {gap}\n"
    else:
        markdown += "All key information available\n"
    
    markdown += f"\n---\n*Generated from structured payload*\n"
    
    return markdown

# ============================================================================
# MCP DISCOVERY
# ============================================================================

@app.get("/mcp/discover")
async def mcp_discover():
    """MCP Discovery endpoint"""
    return {
        "mcp_version": "2024-11-05",
        "server_info": {
            "name": "PE Due Diligence MCP Server",
            "version": "2.0.0",
            "description": "AI agent tools with GCS integration"
        },
        "capabilities": {
            "tools": [
                {
                    "name": "generate_unified_dashboard",
                    "description": "Generate unified dashboard (structured + RAG) with GPT synthesis",
                    "endpoint": "/tool/generate_unified_dashboard",
                    "method": "POST",
                    "features": ["gcs_storage", "gpt_synthesis", "dual_source"]
                },
                {
                    "name": "generate_structured_dashboard",
                    "description": "Generate dashboard from structured payloads",
                    "endpoint": "/tool/generate_structured_dashboard",
                    "method": "POST"
                },
                {
                    "name": "generate_rag_dashboard",
                    "description": "Generate dashboard using RAG with GPT",
                    "endpoint": "/tool/generate_rag_dashboard",
                    "method": "POST"
                },
                {
                    "name": "report_risk",
                    "description": "Log risk signals to GCS",
                    "endpoint": "/tool/report_risk",
                    "method": "POST"
                }
            ],
            "resources": [
                {
                    "name": "ai50/companies",
                    "description": "List of AI50 companies from forbes_ai50_seed.json",
                    "endpoint": "/resource/ai50/companies"
                }
            ]
        }
    }

# ============================================================================
# APPROVAL ENDPOINTS (Option 1: External HITL)
# ============================================================================

class ApprovalRequest(BaseModel):
    """Request to approve/reject a dashboard"""
    company_id: str
    run_id: str
    action: Literal["approve", "reject"]
    approved_by: Optional[str] = None
    notes: Optional[str] = None

@app.get("/api/pending-approvals")
async def list_pending_approvals():
    """List all dashboards pending approval"""
    try:
        data_dir = Path(__file__).parent.parent.parent / "data" / "dashboards"
        pending_dashboards = []
        
        if not data_dir.exists():
            return {"pending": []}
        
        # Scan for pending_approval folders
        seen_runs = set()  # Track seen company_id + run_id combinations to avoid duplicates
        
        for company_dir in data_dir.iterdir():
            if not company_dir.is_dir():
                continue
            
            pending_dir = company_dir / "pending_approval"
            if not pending_dir.exists():
                continue
            
            # Find all .md files with corresponding .json metadata
            for md_file in pending_dir.glob("*.md"):
                json_file = md_file.with_suffix('.json')
                if json_file.exists():
                    try:
                        with open(json_file, 'r') as f:
                            metadata = json.load(f)
                        
                        # Create unique key to avoid duplicates
                        company_id = metadata.get("company_id")
                        run_id = metadata.get("run_id")
                        unique_key = f"{company_id}_{run_id}"
                        
                        if unique_key in seen_runs:
                            continue  # Skip duplicate
                        seen_runs.add(unique_key)
                        
                        # Read dashboard content preview
                        with open(md_file, 'r') as f:
                            content = f.read()
                            preview = content[:500] + "..." if len(content) > 500 else content
                        
                        pending_dashboards.append({
                            "company_id": company_id,
                            "run_id": run_id,
                            "evaluation_score": metadata.get("evaluation_score", 0.0),
                            "risk_detected": metadata.get("risk_detected", False),
                            "generated_at": metadata.get("generated_at"),
                            "file_path": str(md_file),
                            "preview": preview,
                            "metadata": metadata
                        })
                    except Exception as e:
                        logger.warning(f"Error reading {md_file}: {e}")
                        continue
        
        return {"pending": pending_dashboards}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing pending approvals: {str(e)}")

@app.post("/api/approve-dashboard")
async def approve_dashboard(request: ApprovalRequest):
    """Approve or reject a pending dashboard - GCS-based"""
    try:
        # Use GCS as primary source, local filesystem as fallback
        bucket_name = os.getenv('GCS_BUCKET_NAME', 'ai-pe-dashboard')
        data_dir = Path(__file__).parent.parent.parent / "data" / "dashboards"
        
        # Find files in GCS first
        source_blob = None
        source_metadata_blob = None
        dashboard_content = None
        metadata = {}
        
        if GCS_AVAILABLE and DashboardStorage is not None:
            try:
                storage = DashboardStorage(bucket_name)
                
                # Find the GCS blob in pending_approval folder by run_id
                pending_prefix = f"data/dashboards/{request.company_id}/pending_approval/"
                blobs = list(storage.bucket.list_blobs(prefix=pending_prefix))
                
                # Find matching blob by run_id (more flexible than exact filename)
                for blob in blobs:
                    if request.run_id in blob.name:
                        if blob.name.endswith('.md'):
                            source_blob = blob
                            dashboard_content = blob.download_as_text()
                        elif blob.name.endswith('.json'):
                            source_metadata_blob = blob
                            metadata = json.loads(blob.download_as_text())
                
                if not source_blob:
                    raise HTTPException(status_code=404, detail=f"Dashboard not found in GCS for run_id: {request.run_id}")
                
                logger.info(f"Found GCS blob: {source_blob.name}")
                
            except Exception as e:
                logger.warning(f"GCS lookup failed: {e}, trying local filesystem...")
                # Fallback to local filesystem
                company_dir = data_dir / request.company_id / "pending_approval"
                
                if not company_dir.exists():
                    raise HTTPException(status_code=404, detail=f"No pending approvals found for {request.company_id}")
                
                # Find the dashboard file
                md_file = None
                json_file = None
                
                for f in company_dir.glob(f"*{request.run_id}*.md"):
                    md_file = f
                    json_file = f.with_suffix('.json')
                    break
                
                if not md_file or not md_file.exists():
                    raise HTTPException(status_code=404, detail=f"Dashboard not found for run_id: {request.run_id}")
                
                # Read dashboard content
                with open(md_file, 'r') as f:
                    dashboard_content = f.read()
                
                # Read metadata
                if json_file.exists():
                    with open(json_file, 'r') as f:
                        metadata = json.load(f)
        else:
            # No GCS available, use local filesystem only
            company_dir = data_dir / request.company_id / "pending_approval"
            
            if not company_dir.exists():
                raise HTTPException(status_code=404, detail=f"No pending approvals found for {request.company_id}")
            
            # Find the dashboard file
            md_file = None
            json_file = None
            
            for f in company_dir.glob(f"*{request.run_id}*.md"):
                md_file = f
                json_file = f.with_suffix('.json')
                break
            
            if not md_file or not md_file.exists():
                raise HTTPException(status_code=404, detail=f"Dashboard not found for run_id: {request.run_id}")
            
            # Read dashboard content
            with open(md_file, 'r') as f:
                dashboard_content = f.read()
            
            # Read metadata
            if json_file.exists():
                with open(json_file, 'r') as f:
                    metadata = json.load(f)
        
        if request.action == "approve":
            # Update metadata
            metadata["status"] = "approved"
            metadata["approved_by"] = request.approved_by or "unknown"
            metadata["approved_at"] = datetime.now(timezone.utc).isoformat()
            metadata["notes"] = request.notes
            
            # Move files in GCS (primary operation)
            gcs_moved = False
            new_gcs_path = None
            if GCS_AVAILABLE and DashboardStorage is not None and source_blob:
                try:
                    storage = DashboardStorage(bucket_name)
                    
                    # Extract filename from source blob
                    md_filename = source_blob.name.split('/')[-1]
                    json_filename = source_metadata_blob.name.split('/')[-1] if source_metadata_blob else None
                    
                    # Copy to company root directory (no subfolder)
                    new_blob_name = f"data/dashboards/{request.company_id}/{md_filename}"
                    new_blob = storage.bucket.copy_blob(source_blob, storage.bucket, new_blob_name)
                    
                    # Update blob metadata
                    new_blob.metadata = metadata
                    new_blob.patch()
                    
                    # Handle metadata blob if exists
                    if source_metadata_blob and json_filename:
                        new_metadata_blob_name = f"data/dashboards/{request.company_id}/{json_filename}"
                        new_metadata_blob = storage.bucket.copy_blob(source_metadata_blob, storage.bucket, new_metadata_blob_name)
                        
                        # Update metadata content
                        metadata_content = metadata.copy()
                        new_metadata_blob.upload_from_string(
                            json.dumps(metadata_content, indent=2),
                            content_type='application/json'
                        )
                        
                        # Delete old metadata blob
                        source_metadata_blob.delete()
                    
                    # Delete old blob from pending_approval
                    source_blob.delete()
                    
                    gcs_moved = True
                    new_gcs_path = f"gs://{bucket_name}/{new_blob_name}"
                    logger.info(f"✅ Moved GCS blob from {source_blob.name} to {new_blob_name}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to move GCS file: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    raise HTTPException(status_code=500, detail=f"Failed to move GCS file: {str(e)}")
            else:
                if not GCS_AVAILABLE:
                    raise HTTPException(status_code=500, detail="GCS not available - cannot process approval")
                if not source_blob:
                    raise HTTPException(status_code=404, detail="Source blob not found in GCS")
            
            # Also update local filesystem if files exist (optional, for backup)
            try:
                data_dir = Path(__file__).parent.parent.parent / "data" / "dashboards"
                local_pending_dir = data_dir / request.company_id / "pending_approval"
                local_company_dir = data_dir / request.company_id
                
                if local_pending_dir.exists():
                    local_company_dir.mkdir(parents=True, exist_ok=True)
                    for f in local_pending_dir.glob(f"*{request.run_id}*"):
                        import shutil
                        shutil.move(str(f), str(local_company_dir / f.name))
                        logger.info(f"Also moved local file: {f.name}")
            except Exception as e:
                logger.warning(f"Local file move failed (non-critical): {e}")
            
            return {
                "status": "approved",
                "message": f"Dashboard for {request.company_id} approved",
                "gcs_path": new_gcs_path,
                "gcs_moved": gcs_moved
            }
        else:
            # Reject - move to rejected folder
            # Update metadata
            metadata["status"] = "rejected"
            metadata["rejected_by"] = request.approved_by or "unknown"
            metadata["rejected_at"] = datetime.now(timezone.utc).isoformat()
            metadata["notes"] = request.notes
            
            # Move files in GCS (primary operation)
            gcs_moved = False
            new_gcs_path = None
            if GCS_AVAILABLE and DashboardStorage is not None and source_blob:
                try:
                    storage = DashboardStorage(bucket_name)
                    
                    # Extract filename from source blob
                    md_filename = source_blob.name.split('/')[-1]
                    json_filename = source_metadata_blob.name.split('/')[-1] if source_metadata_blob else None
                    
                    # Copy to rejected folder
                    new_blob_name = f"data/dashboards/{request.company_id}/rejected/{md_filename}"
                    new_blob = storage.bucket.copy_blob(source_blob, storage.bucket, new_blob_name)
                    
                    # Update blob metadata
                    new_blob.metadata = metadata
                    new_blob.patch()
                    
                    # Handle metadata blob if exists
                    if source_metadata_blob and json_filename:
                        new_metadata_blob_name = f"data/dashboards/{request.company_id}/rejected/{json_filename}"
                        new_metadata_blob = storage.bucket.copy_blob(source_metadata_blob, storage.bucket, new_metadata_blob_name)
                        
                        # Update metadata content
                        metadata_content = metadata.copy()
                        new_metadata_blob.upload_from_string(
                            json.dumps(metadata_content, indent=2),
                            content_type='application/json'
                        )
                        
                        # Delete old metadata blob
                        source_metadata_blob.delete()
                    
                    # Delete old blob from pending_approval
                    source_blob.delete()
                    
                    gcs_moved = True
                    new_gcs_path = f"gs://{bucket_name}/{new_blob_name}"
                    logger.info(f"✅ Moved GCS blob from {source_blob.name} to {new_blob_name}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to move GCS file: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    raise HTTPException(status_code=500, detail=f"Failed to move GCS file: {str(e)}")
            else:
                if not GCS_AVAILABLE:
                    raise HTTPException(status_code=500, detail="GCS not available - cannot process rejection")
                if not source_blob:
                    raise HTTPException(status_code=404, detail="Source blob not found in GCS")
            
            # Also update local filesystem if files exist (optional, for backup)
            try:
                data_dir = Path(__file__).parent.parent.parent / "data" / "dashboards"
                local_pending_dir = data_dir / request.company_id / "pending_approval"
                local_rejected_dir = data_dir / request.company_id / "rejected"
                
                if local_pending_dir.exists():
                    local_rejected_dir.mkdir(parents=True, exist_ok=True)
                    for f in local_pending_dir.glob(f"*{request.run_id}*"):
                        import shutil
                        shutil.move(str(f), str(local_rejected_dir / f.name))
                        logger.info(f"Also moved local file: {f.name}")
            except Exception as e:
                logger.warning(f"Local file move failed (non-critical): {e}")
            
            return {
                "status": "rejected",
                "message": f"Dashboard for {request.company_id} rejected",
                "gcs_path": new_gcs_path,
                "gcs_moved": gcs_moved
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing approval: {str(e)}")

# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("MCP_SERVER_PORT", "8100"))
    
    print(f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║           MCP SERVER v2.0 - GCS ENABLED                   ║
    ║  Model Context Protocol for PE Due Diligence              ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  Port:        {port}                                       ║
    ║  Tools:       4 (unified, structured, rag, risk)          ║
    ║  GCS:         {'✅ Connected' if GCS_AVAILABLE else '❌ Disabled'}                                    ║
    ║  Bucket:      {os.getenv('GCS_BUCKET_NAME', 'ai-pe-dashboard')}                            ║
    ╚═══════════════════════════════════════════════════════════╝
    
    📍 Endpoints:
       POST http://localhost:{port}/tool/generate_unified_dashboard
       POST http://localhost:{port}/tool/generate_rag_dashboard
       POST http://localhost:{port}/tool/report_risk
       GET  http://localhost:{port}/resource/ai50/companies
       GET  http://localhost:{port}/api/pending-approvals
       POST http://localhost:{port}/api/approve-dashboard
    
    📚 Docs: http://localhost:{port}/docs
    
    🔧 Features:
       ✓ GPT-4o synthesis for all dashboards
       ✓ Structured + RAG data combination
       ✓ Automatic GCS storage
       ✓ Forbes AI50 company list
    """)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=True
    )