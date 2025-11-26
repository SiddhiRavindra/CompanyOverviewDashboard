"""
Integration test for Lab 15: Agent → MCP → Dashboard round trip
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
import requests
from src.agents.mcp_client import MCPClient  # ✅ Now this will work


def test_mcp_server_health():
    """Test MCP server is running"""
    response = requests.get("http://localhost:8100/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    print("✅ MCP server is healthy")


def test_mcp_discovery():
    """Test MCP discovery endpoint"""
    client = MCPClient()
    result = client.discover()
    
    assert "capabilities" in result
    assert len(result["capabilities"]["tools"]) >= 2
    print(f"✅ Discovered {len(result['capabilities']['tools'])} tools")


def test_structured_dashboard_via_mcp():
    """Test structured dashboard generation via MCP"""
    client = MCPClient()
    
    result = client.call_tool(
        "generate_structured_dashboard",
        {"company_id": "anthropic"}
    )
    
    assert result.get("success") == True
    assert "anthropic" in result.get("company_id", "").lower()
    assert result.get("result") is not None
    assert len(result.get("result", "")) > 100
    print("✅ Structured dashboard generated via MCP")


def test_rag_dashboard_via_mcp():
    """Test RAG dashboard generation via MCP"""
    client = MCPClient()
    
    result = client.call_tool(
        "generate_rag_dashboard",
        {"company_id": "anthropic", "top_k": 5}
    )
    
    assert result.get("success") == True
    assert result.get("metadata", {}).get("top_k") == 5
    print("✅ RAG dashboard generated via MCP")


def test_risk_reporting_via_mcp():
    """Test risk reporting via MCP"""
    client = MCPClient()
    
    result = client.call_tool(
        "report_risk",
        {
            "company_id": "test-company",
            "occurred_on": "2025-11-17",
            "description": "Test risk for integration testing",
            "source_url": "https://example.com/test",
            "risk_type": "other",
            "severity": "low"
        }
    )
    
    assert result.get("success") == True
    assert result.get("metadata", {}).get("hitl_required") == False  # low severity
    print("✅ Risk reported via MCP")


def test_tool_filtering():
    """Test that tool filtering works"""
    client = MCPClient()
    
    # This should work (allowed tool)
    result = client.call_tool(
        "generate_structured_dashboard",
        {"company_id": "anthropic"}
    )
    assert result.get("success") == True
    
    # Test with a blocked tool (if configured)
    # For now, just verify filtering is enabled
    assert client.filtering_enabled == True
    print("✅ Tool filtering is active")


def test_end_to_end_round_trip():
    """Test complete round trip: Agent → MCP → Dashboard → Back"""
    client = MCPClient()
    
    # Step 1: Get companies resource
    companies = client.get_resource("ai50/companies")
    assert "companies" in companies
    assert len(companies["companies"]) == 50
    
    # Step 2: Get dashboard template
    template = client.get_prompt("pe-dashboard")
    assert "template" in template
    assert "8 sections" in template["template"].lower() or "## 1." in template["template"]
    
    # Step 3: Generate dashboard
    result = client.call_tool(
        "generate_structured_dashboard",
        {"company_id": "anthropic"}
    )
    assert result.get("success") == True
    
    # Step 4: Verify dashboard has expected sections
    dashboard = result.get("result", "")
    assert "## 1. Company Overview" in dashboard
    assert "## 2. Funding History" in dashboard
    assert "## 8. Risk Factors" in dashboard
    
    print("✅ End-to-end round trip successful")


if __name__ == "__main__":
    print("\n🧪 Running MCP Integration Tests\n")
    print("="*60)
    
    try:
        test_mcp_server_health()
        test_mcp_discovery()
        test_structured_dashboard_via_mcp()
        test_rag_dashboard_via_mcp()
        test_risk_reporting_via_mcp()
        test_tool_filtering()
        test_end_to_end_round_trip()
        
        print("="*60)
        print("\n✅ All tests passed!\n")
    except Exception as e:
        print(f"\n❌ Test failed: {e}\n")
        import traceback
        traceback.print_exc()