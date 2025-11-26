# API Reference

## MCP Server API - Model Context Protocol Implementation

**Base URL:** `http://localhost:8100` (default)  
**Version:** 2.0.0  
**Protocol:** HTTP/REST  
**Documentation:** Interactive API docs available at `http://localhost:8100/docs`

---

## Table of Contents

1. [Health & Discovery](#health--discovery)
2. [Tool Endpoints](#tool-endpoints)
3. [Resource Endpoints](#resource-endpoints)
4. [Prompt Endpoints](#prompt-endpoints)
5. [Approval Endpoints (HITL)](#approval-endpoints-hitl)
6. [Request/Response Models](#requestresponse-models)
7. [Error Handling](#error-handling)

---

## Health & Discovery

### GET `/`

Root endpoint providing service information.

**Response:**
```json
{
  "service": "MCP Server",
  "status": "healthy",
  "version": "2.0.0",
  "gcs_enabled": true,
  "endpoints": {
    "tools": 4,
    "resources": 1,
    "prompts": 1
  }
}
```

---

### GET `/health`

Detailed health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "mcp_version": "2024-11-05",
  "gcs_available": true,
  "tools_available": [
    "generate_structured_dashboard",
    "generate_rag_dashboard",
    "generate_unified_dashboard",
    "report_risk"
  ],
  "resources_available": ["ai50/companies"],
  "prompts_available": ["pe-dashboard"]
}
```

---

### GET `/mcp/discover`

MCP Discovery endpoint - returns all available capabilities.

**Response:**
```json
{
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
```

---

## Tool Endpoints

### POST `/tool/generate_structured_dashboard`

Generate dashboard from structured Pydantic payloads.

**Request:**
```json
{
  "company_id": "anthropic"
}
```

**Response (Success):**
```json
{
  "success": true,
  "company_id": "anthropic",
  "result": "# PE Dashboard for Anthropic\n\n## 1. Company Overview\n...",
  "metadata": {
    "source": "structured_pipeline",
    "tool": "payload_tool",
    "sections": 8,
    "type": "markdown",
    "has_events": true,
    "has_leadership": true,
    "has_products": true
  }
}
```

**Response (Error - Company Not Found):**
```json
{
  "status_code": 404,
  "detail": "Company 'nonexistent' not found in structured data: ..."
}
```

**Response (Error - Validation):**
```json
{
  "success": false,
  "company_id": "anthropic",
  "error": "Validation error: ...",
  "metadata": {
    "error_type": "ValueError"
  }
}
```

---

### POST `/tool/generate_rag_dashboard`

Generate dashboard using RAG (Retrieval-Augmented Generation) with GPT synthesis.

**Request:**
```json
{
  "company_id": "anthropic",
  "top_k": 5,
  "query": "optional custom query"
}
```

**Parameters:**
- `company_id` (required): Company identifier
- `top_k` (optional, default: 5): Number of chunks to retrieve per query
- `query` (optional): Custom search query (uses default queries if not provided)

**Response (Success):**
```json
{
  "success": true,
  "company_id": "anthropic",
  "result": "# RAG Dashboard for Anthropic\n\n## 1. Company Overview\n...",
  "metadata": {
    "source": "rag_pipeline",
    "tool": "rag_tool",
    "model": "gpt-4o",
    "top_k": 5,
    "sections": 8,
    "total_chunks_retrieved": 24,
    "tokens_used": 2150
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "company_id": "anthropic",
  "error": "Error message",
  "metadata": {
    "error_type": "ExceptionName"
  }
}
```

---

### POST `/tool/generate_unified_dashboard`

Fetch pre-generated unified dashboard from GCS bucket. Optionally restructure with GPT.

**Request:**
```json
{
  "company_id": "anthropic",
  "top_k": 10,
  "prefer_structured": true,
  "save_to_gcs": true,
  "restructure_with_gpt": false
}
```

**Parameters:**
- `company_id` (required): Company identifier
- `top_k` (optional, default: 10): Number of RAG chunks (if generating new)
- `prefer_structured` (optional, default: true): Prefer structured data when available
- `save_to_gcs` (optional, default: true): Save dashboard to GCS bucket
- `restructure_with_gpt` (optional, default: true): Use GPT to restructure fetched dashboard

**Response (Success):**
```json
{
  "success": true,
  "company_id": "anthropic",
  "result": "# Unified Dashboard for Anthropic\n\n...",
  "data_sources": {
    "Company Overview": "structured",
    "Funding History": "rag"
  },
  "gcs_uri": "gs://ai-pe-dashboard/data/dashboards/anthropic/unified_*.md",
  "metadata": {
    "source": "gcs_bucket",
    "tool": "unified_dashboard",
    "fetched_from": "google_cloud_storage",
    "dashboard_type": "unified",
    "fetched_at": "2025-01-15T10:30:00",
    "restructured_with_gpt": false,
    "tokens_used": 0
  }
}
```

**Response (Error - Dashboard Not Found):**
```json
{
  "success": false,
  "company_id": "anthropic",
  "error": "No unified dashboard found in GCS for 'anthropic'",
  "data_sources": {},
  "metadata": {
    "error_type": "DashboardNotFound",
    "suggestion": "Run supervisor agent to generate dashboard first",
    "command": "python src/agents/supervisor_mcp.py anthropic"
  }
}
```

**Response (Error - GCS Not Configured):**
```json
{
  "status_code": 503,
  "detail": "GCS storage not configured. Check GCS_BUCKET_NAME in .env"
}
```

---

### POST `/tool/report_risk`

Log risk signal and save to GCS. Triggers HITL workflow for high/critical severity.

**Request:**
```json
{
  "company_id": "anthropic",
  "occurred_on": "2025-01-15",
  "description": "Major layoff affecting 20% of workforce",
  "source_url": "https://techcrunch.com/layoff-news",
  "risk_type": "layoff",
  "severity": "high"
}
```

**Parameters:**
- `company_id` (required): Company identifier
- `occurred_on` (required): Date in ISO format (YYYY-MM-DD)
- `description` (required): Description of the risk event
- `source_url` (required): Valid HTTP/HTTPS URL
- `risk_type` (required): One of: `layoff`, `security_incident`, `regulatory`, `financial_distress`, `leadership_crisis`, `legal_action`, `product_recall`, `market_disruption`, `other`
- `severity` (optional, default: `medium`): One of: `low`, `medium`, `high`, `critical`

**Response (Success):**
```json
{
  "success": true,
  "company_id": "anthropic",
  "result": "Risk logged: layoff - Major layoff affecting 20% of workforce",
  "metadata": {
    "tool": "risk_logger",
    "hitl_required": true,
    "severity": "high",
    "risk_type": "layoff",
    "occurred_on": "2025-01-15",
    "gcs_uri": "gs://ai-pe-dashboard/data/risk_signals/anthropic/risk_20250115.jsonl"
  }
}
```

**HITL Requirements:**
- `severity: "high"` → `hitl_required: true`
- `severity: "critical"` → `hitl_required: true`
- `severity: "low"` or `"medium"` → `hitl_required: false`

**Response (Error):**
```json
{
  "success": false,
  "company_id": "anthropic",
  "error": "Failed to log risk signal",
  "metadata": {
    "error_type": "ExceptionName"
  }
}
```

---

## Resource Endpoints

### GET `/resource/ai50/companies`

List all Forbes AI 50 companies.

**Response:**
```json
{
  "companies": [
    "abridge",
    "anthropic",
    "cohere",
    "openai",
    ...
  ],
  "count": 47
}
```

**Data Sources:**
1. Primary: `data/forbes_ai50_seed.json`
2. Fallback: `data/payloads/*.json` (scans payload files)

---

## Prompt Endpoints

### GET `/prompt/pe-dashboard`

Get the PE dashboard template (8-section structure).

**Response:**
```json
{
  "prompt_id": "pe-dashboard",
  "template": "Generate a Private Equity due diligence dashboard with exactly 8 sections:\n\n## 1. Company Overview\n...",
  "description": "8-section PE due diligence dashboard template"
}
```

**Template Structure:**
1. Company Overview
2. Business Model and GTM
3. Funding & Investor Profile
4. Growth Momentum
5. Visibility & Market Sentiment
6. Risks and Challenges
7. Outlook
8. Disclosure Gaps

---

## Approval Endpoints (HITL)

### GET `/api/pending-approvals`

List all dashboards pending human approval (HITL).

**Response:**
```json
{
  "pending": [
    {
      "company_id": "anthropic",
      "run_id": "run_20250115_103000",
      "evaluation_score": 0.85,
      "risk_detected": true,
      "generated_at": "2025-01-15T10:30:00Z",
      "file_path": "/path/to/dashboard.md",
      "preview": "Dashboard content preview...",
      "metadata": {
        "risk_details": [...],
        "evaluation_result": {...}
      }
    }
  ]
}
```

---

### POST `/api/approve-dashboard`

Approve or reject a pending dashboard.

**Request:**
```json
{
  "company_id": "anthropic",
  "run_id": "run_20250115_103000",
  "action": "approve",
  "approved_by": "John Doe",
  "notes": "Approved after review"
}
```

**Parameters:**
- `company_id` (required): Company identifier
- `run_id` (required): Workflow run ID
- `action` (required): `"approve"` or `"reject"`
- `approved_by` (optional): Name of approver
- `notes` (optional): Approval notes

**Response (Success):**
```json
{
  "success": true,
  "company_id": "anthropic",
  "run_id": "run_20250115_103000",
  "action": "approve",
  "status": "approved",
  "approved_by": "John Doe",
  "approved_at": "2025-01-15T10:35:00Z",
  "gcs_uri": "gs://ai-pe-dashboard/data/dashboards/anthropic/due_diligence_*.md"
}
```

**Response (Error):**
```json
{
  "status_code": 404,
  "detail": "Dashboard not found for company_id=anthropic, run_id=run_20250115_103000"
}
```

---

## Request/Response Models

### ToolRequest (Base)
```python
{
  "company_id": str  # Required: Company identifier
}
```

### StructuredDashboardRequest
```python
{
  "company_id": str  # Required
}
```

### RAGDashboardRequest
```python
{
  "company_id": str,      # Required
  "top_k": int,          # Optional, default: 5
  "query": str           # Optional, custom search query
}
```

### UnifiedDashboardRequest
```python
{
  "company_id": str,              # Required
  "top_k": int,                   # Optional, default: 10
  "prefer_structured": bool,     # Optional, default: true
  "save_to_gcs": bool,            # Optional, default: true
  "restructure_with_gpt": bool   # Optional, default: true
}
```

### RiskReportRequest
```python
{
  "company_id": str,      # Required
  "occurred_on": str,     # Required, ISO date (YYYY-MM-DD)
  "description": str,     # Required
  "source_url": str,      # Required, valid HTTP/HTTPS URL
  "risk_type": str,       # Required, see risk types below
  "severity": str         # Optional, default: "medium"
}
```

**Risk Types:**
- `layoff`
- `security_incident`
- `regulatory`
- `financial_distress`
- `leadership_crisis`
- `legal_action`
- `product_recall`
- `market_disruption`
- `other`

**Severity Levels:**
- `low`
- `medium`
- `high`
- `critical`

### ToolResponse
```python
{
  "success": bool,
  "company_id": str,
  "result": str | None,      # Dashboard markdown or result text
  "error": str | None,       # Error message if success=false
  "metadata": dict | None    # Additional metadata
}
```

### UnifiedDashboardResponse
```python
{
  "success": bool,
  "company_id": str,
  "result": str | None,
  "error": str | None,
  "metadata": dict | None,
  "data_sources": dict,      # Which source used for each section
  "gcs_uri": str | None      # GCS URI if saved
}
```

### CompanyListResponse
```python
{
  "companies": List[str],    # List of company IDs
  "count": int              # Number of companies
}
```

### PromptResponse
```python
{
  "prompt_id": str,
  "template": str,
  "description": str
}
```

### ApprovalRequest
```python
{
  "company_id": str,        # Required
  "run_id": str,            # Required
  "action": str,            # Required: "approve" or "reject"
  "approved_by": str,      # Optional
  "notes": str              # Optional
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 404 | Not Found | Company or resource not found |
| 422 | Validation Error | Invalid request parameters |
| 500 | Internal Server Error | Server-side error |
| 503 | Service Unavailable | GCS or external service unavailable |

### Error Response Format

```json
{
  "success": false,
  "company_id": "anthropic",
  "error": "Error message describing what went wrong",
  "metadata": {
    "error_type": "ExceptionName",
    "additional_info": "..."
  }
}
```

### Common Errors

**Company Not Found:**
```json
{
  "status_code": 404,
  "detail": "Company 'nonexistent' not found in structured data: ..."
}
```

**Validation Error:**
```json
{
  "status_code": 422,
  "detail": [
    {
      "loc": ["body", "company_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**GCS Not Configured:**
```json
{
  "status_code": 503,
  "detail": "GCS storage not configured. Check GCS_BUCKET_NAME in .env"
}
```

---

## Authentication

Currently, the MCP server does not require authentication. All endpoints are publicly accessible.

**Future Enhancement:** API key authentication can be enabled via `mcp_server.config.json`:
```json
{
  "security": {
    "require_api_key": true,
    "api_key_header": "X-MCP-API-Key"
  }
}
```

---

## Rate Limiting

No rate limiting is currently implemented. Consider implementing rate limiting for production deployments.

---

## Examples

### Generate Structured Dashboard

```bash
curl -X POST http://localhost:8100/tool/generate_structured_dashboard \
  -H "Content-Type: application/json" \
  -d '{"company_id": "anthropic"}'
```

### Generate RAG Dashboard

```bash
curl -X POST http://localhost:8100/tool/generate_rag_dashboard \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "anthropic",
    "top_k": 10
  }'
```

### Report Risk

```bash
curl -X POST http://localhost:8100/tool/report_risk \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "anthropic",
    "occurred_on": "2025-01-15",
    "description": "Security breach affecting customer data",
    "source_url": "https://example.com/news",
    "risk_type": "security_incident",
    "severity": "critical"
  }'
```

### List Companies

```bash
curl http://localhost:8100/resource/ai50/companies
```

### Get Dashboard Template

```bash
curl http://localhost:8100/prompt/pe-dashboard
```

---

## Interactive API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI:** `http://localhost:8100/docs`
- **ReDoc:** `http://localhost:8100/redoc`
- **OpenAPI Schema:** `http://localhost:8100/openapi.json`

---

## Version History

- **v2.0.0** (Current): GCS integration, unified dashboard, HITL endpoints
- **v1.0.0**: Initial MCP server implementation

---

## Support

For issues or questions:
1. Check the interactive docs at `/docs`
2. Review the system architecture in `docs/SYSTEM_ARCHITECTURE.md`
3. Check logs in `logs/mcp_client.log` (if logging enabled)
