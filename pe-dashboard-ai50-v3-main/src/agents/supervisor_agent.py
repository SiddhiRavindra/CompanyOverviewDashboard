"""
Supervisor Agent for Assignment 5.

Lab 13: Creates a Due Diligence Supervisor Agent using LangChain.
Shows Thought → Action → Observation sequence in console logs.
"""

import os
import asyncio
from datetime import date
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langchain_core.messages import AIMessage, ToolMessage
from langchain.agents import create_agent
from dotenv import load_dotenv

from src.tools.payload_tool import get_latest_structured_payload
from src.tools.rag_tool import rag_search_company
from src.tools.risk_logger import report_risk_signal, RiskSignal

load_dotenv()


# Helper functions for formatting
def _format_args(args: Dict) -> str:
    """Format tool arguments for display."""
    if not args:
        return ""
    parts = []
    for key, value in args.items():
        if isinstance(value, str) and len(value) > 50:
            parts.append(f"{key}='{value[:50]}...'")
        else:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def _truncate(text: str, max_len: int) -> str:
    """Truncate text for display."""
    if not text:
        return "None"
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


# Lab 13: Simple ReAct console logging
def format_react_logs(messages: List) -> None:
    """Format agent messages as clear Thought → Action → Observation logs (Lab 13)."""
    step = 0
    i = 0
    
    while i < len(messages):
        msg = messages[i]
        
        # AI message with tool calls = Thought + Action
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            step += 1
            
            # Extract thought
            thought = msg.content.strip() if (hasattr(msg, 'content') and msg.content) else "Using tools to gather information"
            if thought and len(thought) > 10:
                print(f"\nThought: {thought}")
            
            # Show actions
            for tool_call in msg.tool_calls:
                tool_name = tool_call.get('name', 'unknown')
                tool_args = tool_call.get('args', {})
                args_str = ", ".join([f"{k}={v}" for k, v in tool_args.items()])
                print(f"Action: {tool_name}({args_str})")
            
            # Look ahead for observations
            i += 1
            while i < len(messages) and isinstance(messages[i], ToolMessage):
                tool_msg = messages[i]
                content = tool_msg.content if hasattr(tool_msg, 'content') else str(tool_msg)
                print(f"Observation: {_truncate(content, 200)}")
                i += 1
            continue
        
        i += 1


# Helper to run async functions in sync context (for LangChain tools)
def _run_async(coro):
    """Run async function in sync context."""
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            new_loop = asyncio.new_event_loop()
            future = executor.submit(lambda: new_loop.run_until_complete(coro))
            try:
                return future.result()
            finally:
                new_loop.close()
    except RuntimeError:
        return asyncio.run(coro)


# Tool wrappers for LangChain
# def get_payload_wrapper(company_id: str) -> str:
#     """Wrapper for get_latest_structured_payload."""
#     try:
#         payload = _run_async(get_latest_structured_payload(company_id))
#         return f"Company: {payload.company_record.legal_name}, HQ: {payload.company_record.hq_city}, Total Raised: ${payload.company_record.total_raised_usd:,.0f}"
#     except Exception as e:
#         return f"Error: {str(e)}"

def get_payload_wrapper(company_id: str) -> str:
    """Wrapper that returns comprehensive payload data in structured format."""
    try:
        payload = _run_async(get_latest_structured_payload(company_id))
        
        # Build structured data
        import json
        from datetime import date
        
        data = {
            "company_id": payload.company_record.company_id,
            "company": {
                "legal_name": payload.company_record.legal_name,
                "brand_name": payload.company_record.brand_name,
                "website": str(payload.company_record.website) if payload.company_record.website else None,
                "hq": {
                    "city": payload.company_record.hq_city,
                    "state": payload.company_record.hq_state,
                    "country": payload.company_record.hq_country
                },
                "founded_year": payload.company_record.founded_year,
                "categories": payload.company_record.categories,
                "funding": {
                    "total_raised_usd": payload.company_record.total_raised_usd,
                    "last_valuation_usd": payload.company_record.last_disclosed_valuation_usd,
                    "last_round": payload.company_record.last_round_name,
                    "last_round_date": payload.company_record.last_round_date.isoformat() if payload.company_record.last_round_date else None
                }
            },
            "events": {
                "count": len(payload.events),
                "recent_funding": [
                    {
                        "date": e.occurred_on.isoformat(),
                        "type": e.event_type,
                        "round": e.round_name,
                        "amount_usd": e.amount_usd,
                        "investors": e.investors,
                        "title": e.title
                    }
                    for e in sorted(
                        [e for e in payload.events if e.event_type == "funding"],
                        key=lambda x: x.occurred_on,
                        reverse=True
                    )[:5]
                ],
                "risk_events": [
                    {
                        "date": e.occurred_on.isoformat(),
                        "type": e.event_type,
                        "title": e.title,
                        "description": e.description
                    }
                    for e in payload.events
                    if e.event_type in ["layoff", "security_incident", "regulatory", "legal_action"]
                ],
                "recent_events": [
                    {
                        "date": e.occurred_on.isoformat(),
                        "type": e.event_type,
                        "title": e.title
                    }
                    for e in sorted(payload.events, key=lambda x: x.occurred_on, reverse=True)[:10]
                ]
            },
            "snapshots": {
                "count": len(payload.snapshots),
                "latest": {
                    "as_of": payload.snapshots[0].as_of.isoformat(),
                    "headcount": payload.snapshots[0].headcount_total,
                    "headcount_growth_pct": payload.snapshots[0].headcount_growth_pct,
                    "job_openings": payload.snapshots[0].job_openings_count,
                    "hiring_focus": payload.snapshots[0].hiring_focus
                } if payload.snapshots else None
            },
            "products": {
                "count": len(payload.products),
                "list": [
                    {
                        "name": p.name,
                        "description": p.description,
                        "pricing_model": p.pricing_model
                    }
                    for p in payload.products
                ]
            },
            "leadership": {
                "count": len(payload.leadership),
                "key_leaders": [
                    {
                        "name": l.name,
                        "role": l.role,
                        "is_founder": l.is_founder,
                        "previous_affiliation": l.previous_affiliation
                    }
                    for l in payload.leadership
                ]
            },
            "visibility": {
                "latest": {
                    "as_of": payload.visibility[0].as_of.isoformat(),
                    "news_mentions_30d": payload.visibility[0].news_mentions_30d,
                    "avg_sentiment": payload.visibility[0].avg_sentiment,
                    "github_stars": payload.visibility[0].github_stars
                } if payload.visibility else None
            }
        }
        
        # Return as JSON string (agent can parse and use all this data)
        return json.dumps(data, indent=2, default=str)
        
    except Exception as e:
        return f"Error: {str(e)}"


def rag_search_wrapper(company_id: str, query: str) -> str:
    """Wrapper for rag_search_company."""
    try:
        results = _run_async(rag_search_company(company_id, query, top_k=3))
        if not results:
            return "No relevant information found."
        return f"Found {len(results)} results: " + "; ".join([r.get('text', '')[:100] for r in results[:3]])
    except Exception as e:
        return f"Error: {str(e)}"


def risk_logger_wrapper(company_id: str, occurred_on: str, description: str, source_url: str, risk_type: str, severity: str = "medium") -> str:
    """Wrapper for report_risk_signal."""
    try:
        from pydantic import HttpUrl
        signal = RiskSignal(
            company_id=company_id,
            occurred_on=date.fromisoformat(occurred_on),
            description=description,
            source_url=HttpUrl(source_url),
            risk_type=risk_type,
            severity=severity
        )
        success = _run_async(report_risk_signal(signal))
        return "Risk signal logged successfully" if success else "Failed to log risk signal"
    except Exception as e:
        return f"Error: {str(e)}"


# Create LangChain tools
def create_agent_tools():
    """Create LangChain tools from our async functions."""
    # Extract valid enum values from Pydantic model JSON schema
    risk_signal_schema = RiskSignal.model_json_schema()
    risk_type_enum = risk_signal_schema['properties']['risk_type'].get('enum', [])
    severity_enum = risk_signal_schema['properties']['severity'].get('enum', [])
    
    risk_type_values = ', '.join([f"'{v}'" for v in risk_type_enum])
    severity_values = ', '.join([f"'{v}'" for v in severity_enum])
    
    return [
        StructuredTool.from_function(
            func=get_payload_wrapper,
            name="get_latest_structured_payload",
            description="Retrieve the latest structured payload for a company. Returns company info, funding, events, leadership, and products.",
        ),
        StructuredTool.from_function(
            func=rag_search_wrapper,
            name="rag_search_company",
            description="Search company documents using RAG. Use this to find information about layoffs, security breaches, funding, or other events.",
        ),
        StructuredTool.from_function(
            func=risk_logger_wrapper,
            name="report_risk_signal",
            description=f"""Log a high-risk event for a company. Use this when you detect layoffs, security incidents, regulatory issues, or other risks.
            
REQUIRED PARAMETERS:
- company_id: The company identifier (string)
- occurred_on: Date in ISO format (YYYY-MM-DD)
- description: Description of the risk event (string)
- source_url: Source URL where the risk was found (must be valid HTTP/HTTPS URL)
- risk_type: MUST be one of: {risk_type_values}
- severity: MUST be one of: {severity_values} (default: 'medium')

VALID risk_type VALUES: {risk_type_values}
VALID severity VALUES: {severity_values}""",
        ),
    ]


# Supervisor Agent Class
class DueDiligenceSupervisor:
    """Due Diligence Supervisor Agent using LangChain ReAct pattern."""
    
    def __init__(self):
        """Initialize the supervisor agent with LLM, tools, and prompt."""
        api_key = os.getenv('OPENAI_KEY')
        if not api_key:
            raise ValueError("OPENAI_KEY not found in environment variables")
        
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=api_key)
        self.tools = create_agent_tools()
        
        # System prompt (exact text from Lab 13)
        system_prompt = "You are a PE Due Diligence Supervisor Agent. Use tools to retrieve payloads, run RAG queries, log risks, and generate PE dashboards."
        
        # Create agent
        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=system_prompt,
            debug=False
        )

# Demo function (kept from starter code for testing)
async def demo_supervisor_run(company_id: str):
    """Demo function using the real LangChain agent."""
    from langchain_core.messages import HumanMessage
    
    supervisor = DueDiligenceSupervisor()
    task = f"Conduct due diligence on company_id: {company_id}. Get the payload, search for risks, and log any findings."
    
    print(f"\n{'='*60}")
    print(f"Running Due Diligence for: {company_id}")
    print(f"{'='*60}\n")
    
    result = await supervisor.agent.ainvoke({"messages": [HumanMessage(content=task)]})
    
    if result and "messages" in result:
        # Lab 13: Console logs showing Thought → Action → Observation
        print("ReAct Execution Log:")
        print(f"{'─'*60}")
        format_react_logs(result["messages"])
        
        # Final answer
        print(f"\n{'='*60}")
        print("FINAL OUTPUT:")
        print(f"{'='*60}")
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and hasattr(msg, "content") and msg.content:
                if not (hasattr(msg, 'tool_calls') and msg.tool_calls):
                    print(msg.content)
                    break

if __name__ == "__main__":
    import sys
    cid = sys.argv[1] if len(sys.argv) > 1 else "anthropic"
    asyncio.run(demo_supervisor_run(cid))