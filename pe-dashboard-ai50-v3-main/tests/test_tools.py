"""
Unit tests for Lab 12 - Core Agent Tools

Test suites:
- tool1: get_latest_structured_payload tests
- tool2: rag_search_company tests
- tool3: risk_logger tests (both report_layoff_signal and report_risk_signal)
"""

import json
import pytest
from datetime import date
from pathlib import Path

from src.tools.payload_tool import get_latest_structured_payload
from src.tools.rag_tool import rag_search_company
from src.tools.risk_logger import report_layoff_signal, report_risk_signal, LayoffSignal, RiskSignal
from src.models import Payload


# ========== Tool 1: Payload Tool Tests ==========

@pytest.mark.asyncio
@pytest.mark.tool1
async def test_get_latest_structured_payload_success():
    """
    Test that we can successfully load a real payload file.
    Uses 'anthropic' which should exist in the payloads directory.
    """
    # Call the function with a known company_id
    payload = await get_latest_structured_payload("anthropic")
    
    # Verify it returns a Payload object
    assert isinstance(payload, Payload)
    
    # Verify it has the expected structure
    assert payload.company_record is not None
    assert payload.company_record.company_id == "anthropic"
    assert payload.company_record.legal_name is not None
    
    # Verify all expected fields exist
    assert hasattr(payload, 'company_record')
    assert hasattr(payload, 'events')
    assert hasattr(payload, 'snapshots')
    assert hasattr(payload, 'products')
    assert hasattr(payload, 'leadership')
    assert hasattr(payload, 'visibility')
    
    # Verify events is a list
    assert isinstance(payload.events, list)
    
    # Verify company_record has required fields
    assert payload.company_record.company_id == "anthropic"
    assert payload.company_record.legal_name == "Anthropic"


@pytest.mark.asyncio
@pytest.mark.tool1
async def test_get_latest_structured_payload_not_found():
    """
    Test error handling for non-existent company_id.
    Should raise FileNotFoundError.
    """
    with pytest.raises(FileNotFoundError) as exc_info:
        await get_latest_structured_payload("nonexistent-company-12345")
    
    # Verify error message is informative
    assert "nonexistent-company-12345" in str(exc_info.value)
    assert "Payload not found" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.tool1
async def test_get_latest_structured_payload_empty_company_id():
    """
    Test error handling for empty or None company_id.
    Should raise ValueError.
    """
    with pytest.raises(ValueError) as exc_info:
        await get_latest_structured_payload("")
    
    assert "company_id cannot be empty" in str(exc_info.value)
    
    with pytest.raises(ValueError) as exc_info:
        await get_latest_structured_payload("   ")  # Whitespace only
    
    assert "company_id cannot be empty" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.tool1
async def test_get_latest_structured_payload_structure():
    """
    Test that the loaded payload has the correct structure and types.
    """
    payload = await get_latest_structured_payload("anthropic")
    
    # Verify company_record structure
    assert payload.company_record.company_id is not None
    assert isinstance(payload.company_record.company_id, str)
    
    # Verify events is a list (can be empty)
    assert isinstance(payload.events, list)
    
    # Verify snapshots is a list
    assert isinstance(payload.snapshots, list)
    
    # Verify products is a list
    assert isinstance(payload.products, list)
    
    # Verify leadership is a list
    assert isinstance(payload.leadership, list)
    
    # Verify visibility is a list
    assert isinstance(payload.visibility, list)
    
    # Verify provenance_policy exists
    assert hasattr(payload, 'provenance_policy')


# ========== Tool 2: RAG Search Tests ==========

import os
from dotenv import load_dotenv

# Load .env file so credentials are available
load_dotenv()


def _has_rag_credentials():
    """Check if ChromaDB credentials are available."""
    return all([
        os.getenv('CHROMA_API_KEY'),
        os.getenv('CHROMA_TENANT'),
        os.getenv('CHROMA_DB'),
        os.getenv('OPENAI_KEY')
    ])


@pytest.mark.asyncio
@pytest.mark.tool2
async def test_rag_search_company_empty_inputs():
    """
    Test that empty inputs return empty list (graceful degradation).
    """
    # Empty company_id
    results = await rag_search_company("", "funding")
    assert results == []
    
    # Empty query
    results = await rag_search_company("anthropic", "")
    assert results == []
    
    # Whitespace only
    results = await rag_search_company("   ", "funding")
    assert results == []
    
    results = await rag_search_company("anthropic", "   ")
    assert results == []


@pytest.mark.asyncio
@pytest.mark.tool2
@pytest.mark.skipif(not _has_rag_credentials(), reason="ChromaDB credentials not available")
async def test_rag_search_company_actual_search():
    """
    Test that RAG search actually works and returns results.
    Requires ChromaDB credentials to be set.
    """
    results = await rag_search_company("anthropic", "funding", top_k=5)
    
    # Should return a list
    assert isinstance(results, list)
    
    # Should have results (not empty)
    assert len(results) > 0, "RAG search should return results when credentials are available"
    
    # Verify result structure
    result = results[0]
    assert 'text' in result, "Result should have 'text' field"
    assert 'source_url' in result, "Result should have 'source_url' field"
    assert 'score' in result, "Result should have 'score' field"
    assert isinstance(result['score'], (int, float)), "Score should be a number"
    assert 0 <= result['score'] <= 1, "Score should be between 0 and 1"
    assert result['text'], "Text should not be empty"
    assert result['source_url'], "Source URL should not be empty"


@pytest.mark.asyncio
@pytest.mark.tool2
@pytest.mark.skipif(not _has_rag_credentials(), reason="ChromaDB credentials not available")
async def test_rag_search_company_result_quality():
    """
    Test that RAG search returns relevant results.
    Requires ChromaDB credentials to be set.
    """
    # Search for something that should exist
    results = await rag_search_company("anthropic", "funding", top_k=3)
    
    assert len(results) > 0, "Should return results for valid query"
    
    # Verify all results have required fields
    for result in results:
        assert 'text' in result
        assert 'source_url' in result
        assert 'score' in result
        assert isinstance(result['score'], (int, float))
        assert 0 <= result['score'] <= 1


# ========== Tool 3: Risk Logger Tests ==========


@pytest.mark.asyncio
@pytest.mark.tool3
async def test_report_layoff_signal_success():
    """
    Test that risk signals are logged successfully to a file.
    """
    signal = LayoffSignal(
        company_id="test-company",
        occurred_on=date.today(),
        description="Test layoff signal for unit test",
        source_url="https://example.com/test"
    )
    
    # Log the signal
    success = await report_layoff_signal(signal)
    assert success is True, "Should return True on successful logging"
    
    # Verify file was created
    # From: tests/test_tools.py -> go up 1 level to project root
    project_root = Path(__file__).parent.parent
    risk_log_file = project_root / "data" / "risk_signals" / "risk_signals.jsonl"
    assert risk_log_file.exists(), "Risk log file should be created"
    
    # Verify file contains the logged entry
    with open(risk_log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        assert len(lines) > 0, "File should contain at least one entry"
        
        # Check the last entry (most recent)
        last_entry = json.loads(lines[-1])
        assert last_entry['company_id'] == "test-company"
        assert last_entry['description'] == "Test layoff signal for unit test"
        assert 'timestamp' in last_entry
        assert 'source_url' in last_entry


@pytest.mark.asyncio
@pytest.mark.tool3
async def test_report_layoff_signal_multiple_entries():
    """
    Test that multiple risk signals can be logged (append mode).
    """
    signal1 = LayoffSignal(
        company_id="company-a",
        occurred_on=date.today(),
        description="First risk signal",
        source_url="https://example.com/1"
    )
    
    signal2 = LayoffSignal(
        company_id="company-b",
        occurred_on=date.today(),
        description="Second risk signal",
        source_url="https://example.com/2"
    )
    
    # Log both signals
    success1 = await report_layoff_signal(signal1)
    success2 = await report_layoff_signal(signal2)
    
    assert success1 is True
    assert success2 is True
    
    # Verify both entries exist in file
    project_root = Path(__file__).parent.parent
    risk_log_file = project_root / "data" / "risk_signals" / "risk_signals.jsonl"
    
    with open(risk_log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        assert len(lines) >= 2, "File should contain at least 2 entries"
        
        # Verify both entries
        entries = [json.loads(line) for line in lines[-2:]]
        company_ids = [e['company_id'] for e in entries]
        assert "company-a" in company_ids
        assert "company-b" in company_ids


@pytest.mark.asyncio
@pytest.mark.tool3
async def test_report_layoff_signal_structure():
    """
    Test that logged entries have the correct structure.
    """
    signal = LayoffSignal(
        company_id="structure-test",
        occurred_on=date(2025, 1, 15),
        description="Structure validation test",
        source_url="https://example.com/structure"
    )
    
    success = await report_layoff_signal(signal)
    assert success is True
    
    # Verify entry structure
    project_root = Path(__file__).parent.parent
    risk_log_file = project_root / "data" / "risk_signals" / "risk_signals.jsonl"
    
    with open(risk_log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        entry = json.loads(lines[-1])
        
        # Verify all required fields
        assert 'timestamp' in entry
        assert 'company_id' in entry
        assert 'occurred_on' in entry
        assert 'description' in entry
        assert 'source_url' in entry
        
        # Verify values
        assert entry['company_id'] == "structure-test"
        assert entry['occurred_on'] == "2025-01-15"
        assert entry['description'] == "Structure validation test"
        assert entry['source_url'] == "https://example.com/structure"


@pytest.mark.asyncio
@pytest.mark.tool3
async def test_report_risk_signal_security_incident():
    """
    Test that security incident risks can be logged.
    """
    signal = RiskSignal(
        company_id="test-company",
        occurred_on=date.today(),
        description="Data breach affecting customer data",
        source_url="https://example.com/breach",
        risk_type="security_incident",
        severity="critical"
    )
    
    success = await report_risk_signal(signal)
    assert success is True
    
    # Verify file contains the risk type and severity
    project_root = Path(__file__).parent.parent
    risk_log_file = project_root / "data" / "risk_signals" / "risk_signals.jsonl"
    
    with open(risk_log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        entry = json.loads(lines[-1])
        assert entry['risk_type'] == "security_incident"
        assert entry['severity'] == "critical"


@pytest.mark.asyncio
@pytest.mark.tool3
async def test_report_risk_signal_regulatory():
    """
    Test that regulatory risks can be logged.
    """
    signal = RiskSignal(
        company_id="test-company",
        occurred_on=date.today(),
        description="SEC investigation into financial disclosures",
        source_url="https://sec.gov/filing",
        risk_type="regulatory",
        severity="high"
    )
    
    success = await report_risk_signal(signal)
    assert success is True
    
    # Verify entry
    project_root = Path(__file__).parent.parent
    risk_log_file = project_root / "data" / "risk_signals" / "risk_signals.jsonl"
    
    with open(risk_log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        entry = json.loads(lines[-1])
        assert entry['risk_type'] == "regulatory"
        assert entry['severity'] == "high"


@pytest.mark.asyncio
@pytest.mark.tool3
async def test_report_risk_signal_all_types():
    """
    Test that all risk types can be logged.
    """
    risk_types = ["layoff", "security_incident", "regulatory", "financial_distress", 
                  "leadership_crisis", "legal_action", "product_recall", "market_disruption", "other"]
    
    for risk_type in risk_types:
        signal = RiskSignal(
            company_id="test-company",
            occurred_on=date.today(),
            description=f"Test {risk_type} risk",
            source_url=f"https://example.com/{risk_type}",
            risk_type=risk_type,
            severity="medium"
        )
        
        success = await report_risk_signal(signal)
        assert success is True, f"Failed to log {risk_type}"
    
    # Verify all types were logged
    project_root = Path(__file__).parent.parent
    risk_log_file = project_root / "data" / "risk_signals" / "risk_signals.jsonl"
    
    with open(risk_log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        # Get last N entries (where N = number of risk types)
        recent_entries = [json.loads(line) for line in lines[-len(risk_types):]]
        logged_types = {entry['risk_type'] for entry in recent_entries}
        
        # Verify all types are present
        for risk_type in risk_types:
            assert risk_type in logged_types, f"Risk type {risk_type} not found in logs"