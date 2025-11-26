# pe-dashboard-ai50-v3
Agentic PE intelligence platform for the Forbes AI 50: Airflow-orchestrated ETL + RAG + structured extraction, wrapped with MCP tools, a ReAct-based supervisor agent, HITL review, and Dockerized FastAPI/Streamlit dashboards.

# Project ORBIT - AI Intelligence Dashboard

> **Agentic PE Intelligence Platform for Forbes AI 50**  
> Airflow-orchestrated ETL + RAG + Structured Extraction, wrapped with MCP tools, ReAct supervisor agent, HITL review, and Dockerized FastAPI/Streamlit dashboards.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 Overview

Project ORBIT is an **autonomous PE intelligence system** that generates comprehensive due diligence dashboards for Forbes AI 50 companies. The platform combines:

- **📊 Structured Data Extraction** - Pydantic-validated company payloads
- **🔍 RAG Pipeline** - ChromaDB vector search with semantic retrieval
- **🤖 AI Synthesis** - GPT-4o powered dashboard generation
- **☁️ Cloud Storage** - Google Cloud Storage integration
- **⚙️ Airflow Orchestration** - Automated daily/weekly data pipelines
- **🎨 Interactive UI** - Streamlit dashboard for easy access

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT DASHBOARD                       │
│              (User Interface - Port 8501)                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP SERVER (FastAPI)                      │
│               Model Context Protocol - Port 8100             │
├─────────────────────────────────────────────────────────────┤
│  Tools:                                                      │
│  • generate_unified_dashboard  (Fetch from GCS + GPT)        │
│  • generate_structured_dashboard  (Pydantic payloads)        │
│  • generate_rag_dashboard  (ChromaDB + GPT)                  │
│  • report_risk  (Risk signal logging)                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌──────────────┐ ┌─────────┐ ┌──────────────┐
│   ChromaDB   │ │   GCS   │ │   Payloads   │
│ (Vector DB)  │ │ Bucket  │ │ (Structured) │
└──────────────┘ └─────────┘ └──────────────┘
        ▲             ▲             ▲
        │             │             │
┌───────┴─────────────┴─────────────┴────────┐
│            AIRFLOW PIPELINES                │
│  • Daily: Scrape + Ingest + Dashboard Gen  │
│  • Weekly: Full refresh + Risk detection   │
└─────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

## Demo Link - https://northeastern.zoom.us/rec/share/tBMWxiMLEBekGQ6krQ7umfo70psI0sOCwSdNyQ6SKoDWm_KVMDQIyxyzqd_pugwq.RiWuTVeEDAXhr1ds?startTime=1763755219000
Passcode: Mc2Jx8%q

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Google Cloud account (for GCS)
- OpenAI API key
- ChromaDB Cloud account

### 1. Clone & Setup

```bash
git clone <your-repo>
cd pe-dashboard-ai50-v3

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create `src/.env`:

```env
# OpenAI
OPENAI_KEY=sk-proj-...

# ChromaDB Cloud
CHROMA_API_KEY=your_chroma_key
CHROMA_TENANT=your_tenant
CHROMA_DB=your_database

# Google Cloud Storage
GOOGLE_APPLICATION_CREDENTIALS=src/storage/pe-dashboard-sa-key.json
GOOGLE_CLOUD_PROJECT=pe-dashboard
GCS_BUCKET_NAME=ai-pe-dashboard

# API Settings
MCP_SERVER_PORT=8100
API_BASE_URL=http://localhost:8000
MCP_SERVER_URL=http://localhost:8100
```

### 3. Run Services

**Option A: Using Docker Compose (Recommended)**

```bash
# Start Airflow
cd airflow
docker-compose up -d

# Access Airflow UI
# URL: http://localhost:8080
# Username: admin
# Password: admin
```

**Option B: Manual Setup**

```bash
# Terminal 1 - MCP Server
python src/server/mcp_server.py

# Terminal 2 - Streamlit Dashboard
streamlit run src/streamlit_app.py

# Terminal 3 - Airflow (optional)
cd airflow
airflow standalone
```

### 4. Access Dashboards

- **Streamlit UI**: http://localhost:8501
- **MCP API Docs**: http://localhost:8100/docs
- **Airflow UI**: http://localhost:8080

---

## 📋 Project Structure

```
pe-dashboard-ai50-v3/
├── src/
│   ├── server/
│   │   └── mcp_server.py          # MCP FastAPI server
│   ├── storage/
│   │   ├── gcs_client.py          # Google Cloud Storage client
│   │   └── pe-dashboard-sa-key.json  # GCS credentials
│   ├── tools/
│   │   ├── payload_tool.py        # Structured data retrieval
│   │   ├── rag_tool.py            # ChromaDB RAG search
│   │   └── risk_logger.py         # Risk signal logging
│   ├── agents/
│   │   └── supervisor_mcp.py      # Supervisor agent
│   ├── streamlit_app.py           # Streamlit dashboard
│   └── .env                       # Environment variables
├── airflow/
│   ├── dags/
│   │   ├── orbit_initial_load_dag.py
│   │   ├── orbit_daily_update_dag.py
│   │   └── ai50_full_ingest_dag.py
│   └── docker-compose.yml         # Airflow setup
├── data/
│   ├── forbes_ai50_seed.json      # AI 50 company list
│   ├── payloads/                  # Structured payloads
│   └── dashboards/                # Generated dashboards (local)
├── requirements.txt
└── README.md
```

---

## 🔧 Core Components

### 1. **MCP Server** (Port 8100)

Model Context Protocol server exposing 4 main tools:

**Endpoints:**

| Tool | Endpoint | Description |
|------|----------|-------------|
| Unified Dashboard | `POST /tool/generate_unified_dashboard` | Fetches pre-generated dashboard from GCS |
| Structured Dashboard | `POST /tool/generate_structured_dashboard` | Generates from Pydantic payloads |
| RAG Dashboard | `POST /tool/generate_rag_dashboard` | ChromaDB search + GPT synthesis |
| Report Risk | `POST /tool/report_risk` | Logs risk signals to GCS |

**Resources:**
- `GET /resource/ai50/companies` - List of 47 Forbes AI 50 companies

### 2. **Airflow Pipelines**

Automated data orchestration running on schedule:

| DAG | Schedule | Purpose |
|-----|----------|---------|
| `orbit_initial_load_dag` | Manual | Initial company data ingestion |
| `orbit_daily_update_dag` | Daily @ 4 AM | Incremental updates |
| `ai50_full_ingest_dag` | Weekly | Full refresh of all companies |

### 3. **Streamlit Dashboard** (Port 8501)

Interactive UI for:
- Generating unified dashboards
- Viewing company intelligence
- Downloading reports (Markdown)

### 4. **Google Cloud Storage**

Persistent storage for:
- Generated dashboards (`data/dashboards/{company}/`)
- Risk logs (`data/risks/{company}/`)
- Metadata files

---

## 📊 Dashboard Sections

Every generated dashboard contains **8 mandatory sections**:

1. **Company Overview** - Basic info, industry, location
2. **Business Model and GTM** - Revenue model, customers, partnerships
3. **Funding & Investor Profile** - Funding rounds, investors, valuation
4. **Growth Momentum** - Employee growth, hiring, expansion
5. **Visibility & Market Sentiment** - News mentions, ratings, sentiment
6. **Risks and Challenges** - Identified risks, challenges
7. **Outlook** - Future plans, roadmap, opportunities
8. **Disclosure Gaps** - Missing or undisclosed information

---

## 🔄 Data Flow

### Unified Dashboard Generation

```
1. User requests dashboard via Streamlit
        ↓
2. MCP Server receives request
        ↓
3. Fetch pre-generated dashboard from GCS
        ↓
4. (Optional) Restructure with GPT-4o
        ↓
5. Return formatted dashboard to user
```

### Airflow ETL Pipeline

```
1. Airflow triggers daily/weekly DAG
        ↓
2. Scrape company websites (homepage, about, careers, etc.)
        ↓
3. Extract structured data → Pydantic payloads
        ↓
4. Chunk text → Embed with OpenAI → Store in ChromaDB
        ↓
5. Supervisor Agent generates unified dashboard
        ↓
6. Save to GCS bucket
```

---

## 🛠️ API Usage Examples

### Fetch Unified Dashboard

```bash
curl -X POST http://localhost:8100/tool/generate_unified_dashboard \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "anthropic",
    "restructure_with_gpt": false
  }'
```

### List All Companies

```bash
curl http://localhost:8100/resource/ai50/companies
```

### Generate RAG Dashboard

```bash
curl -X POST http://localhost:8100/tool/generate_rag_dashboard \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "openai",
    "top_k": 10
  }'
```

---

## 🐳 Docker Deployment

### Airflow

```bash
cd airflow
docker-compose up -d
```

**Access Airflow:**
- URL: http://localhost:8080
- Username: `admin`
- Password: `admin`

### Custom Dockerfiles (Optional)

You can containerize the entire application:

```dockerfile
# Dockerfile for MCP Server
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ src/
CMD ["python", "src/server/mcp_server.py"]
```

---

## 🔐 Security & Credentials

### Required Credentials

1. **GCS Service Account Key**
   - Place in: `src/storage/pe-dashboard-sa-key.json`
   - Permissions: Storage Object Admin

2. **OpenAI API Key**
   - Set in `.env`: `OPENAI_KEY=sk-proj-...`

3. **ChromaDB Cloud**
   - Get from: https://trychroma.com/
   - Set in `.env`: `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DB`

### Best Practices

- ✅ Never commit `.env` or service account keys to Git
- ✅ Use environment variables for all secrets
- ✅ Rotate API keys regularly
- ✅ Use separate GCS buckets for dev/prod

---

## 📈 Performance

| Metric | Value |
|--------|-------|
| Companies Supported | 47 (Forbes AI 50) |
| Dashboard Generation | ~5-10 seconds (from GCS) |
| RAG Search Latency | ~500ms per query |
| Airflow DAGs | 3 (initial, daily, weekly) |
| Storage Backend | Google Cloud Storage |
| Vector DB | ChromaDB Cloud (1536-dim embeddings) |

---

## 🧪 Testing

### Test MCP Server

```bash
# Health check
curl http://localhost:8100/health

# Get companies
curl http://localhost:8100/resource/ai50/companies

# Generate dashboard
curl -X POST http://localhost:8100/tool/generate_unified_dashboard \
  -H "Content-Type: application/json" \
  -d '{"company_id": "abridge"}'
```

### Test Airflow DAGs

```bash
# List DAGs
docker exec airflow airflow dags list

# Trigger a DAG
docker exec airflow airflow dags trigger orbit_initial_load_dag
```

---

## 🐛 Troubleshooting

### Issue: GCS Connection Failed

```bash
# Verify credentials file exists
ls src/storage/pe-dashboard-sa-key.json

# Check .env file
cat src/.env | grep GOOGLE_APPLICATION_CREDENTIALS

# Test GCS connection
python -c "from google.cloud import storage; storage.Client()"
```

### Issue: Airflow DAGs Not Showing

```bash
# Check DAG files
docker exec airflow ls -la /opt/airflow/dags

# Check for errors
docker exec airflow airflow dags list-import-errors

# Restart Airflow
docker-compose restart airflow
```

### Issue: ChromaDB Connection Failed

```bash
# Verify credentials in .env
cat src/.env | grep CHROMA

# Test connection
python -c "from src.tools.rag_tool import rag_search_company; print('OK')"
```

---

## 📝 Development Guide

### Adding a New Company

1. Add to `data/forbes_ai50_seed.json`:
```json
{
  "company_name": "New Company",
  "website": "https://example.com",
  "linkedin": "https://linkedin.com/company/example",
  "hq_city": "San Francisco",
  "hq_country": "California"
}
```

2. Trigger ingestion:
```bash
docker exec airflow airflow dags trigger orbit_initial_load_dag -c '{"company_id": "new-company"}'
```

### Adding a New Tool to MCP Server

1. Create tool function in `src/tools/`
2. Import in `mcp_server.py`
3. Add endpoint:
```python
@app.post("/tool/your_new_tool")
async def your_new_tool(request: YourRequest):
    # Implementation
    pass
```

4. Update `/mcp/discover` endpoint

---

## 🎓 Labs Implemented

- ✅ **Lab 1-3**: Web scraping & data extraction
- ✅ **Lab 4**: RAG indexing with ChromaDB
- ✅ **Lab 7**: GPT-powered dashboard generation
- ✅ **Lab 10**: Docker deployment with Airflow
- ✅ **Lab 15**: MCP server integration
- ✅ **Lab 20**: GCS storage & batch processing

---

## 📦 Dependencies

### Core

```txt
fastapi>=0.100.0
uvicorn>=0.23.0
streamlit>=1.28.0
apache-airflow>=3.1.0
```

### AI/ML

```txt
openai>=1.0.0
langchain>=0.1.0
langchain-openai>=0.0.5
chromadb>=0.4.0
```

### Cloud

```txt
google-cloud-storage>=2.10.0
```

### Data Processing

```txt
pydantic>=2.5.0
pandas
beautifulsoup4>=4.12.0
feedparser>=6.0.0
```




## 📄 License

This project is licensed under the MIT License.

