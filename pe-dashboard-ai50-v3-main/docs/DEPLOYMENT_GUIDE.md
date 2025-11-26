# Deployment Guide 
# Deployment Guide - Project ORBIT

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Docker Deployment](#docker-deployment)
4. [Production Deployment](#production-deployment)
5. [Environment Configuration](#environment-configuration)
6. [Troubleshooting](#troubleshooting)

---

## 🔧 Prerequisites

### Required Tools

- **Python 3.12+** - [Download](https://www.python.org/downloads/)
- **Docker Desktop** - [Download](https://www.docker.com/products/docker-desktop/)
- **Git** - [Download](https://git-scm.com/downloads)

### Required Accounts

- **OpenAI** - [Get API Key](https://platform.openai.com/api-keys)
- **ChromaDB Cloud** - [Sign Up](https://trychroma.com/)
- **Google Cloud Platform** - [Console](https://console.cloud.google.com/)

---

## 💻 Local Development Setup

### Step 1: Clone Repository

```bash
git clone <your-repo-url>
cd pe-dashboard-automation
```

### Step 2: Create Virtual Environment

```bash
# Create venv
python -m venv .venv

# Activate
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

Create `src/.env`:

```env
# OpenAI API
OPENAI_KEY=sk-proj-your-key-here

# ChromaDB Cloud
CHROMA_API_KEY=your-chroma-api-key
CHROMA_TENANT=your-tenant-id
CHROMA_DB=your-database-name

# Google Cloud Storage
GOOGLE_APPLICATION_CREDENTIALS=src/storage/pe-dashboard-sa-key.json
GOOGLE_CLOUD_PROJECT=your-project-id
GCS_BUCKET_NAME=ai-pe-dashboard

# Service Ports
MCP_SERVER_PORT=8100
API_BASE_URL=http://localhost:8000
MCP_SERVER_URL=http://localhost:8100
```

### Step 5: Setup GCS Credentials

1. Create GCS service account in [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Download JSON key file
3. Save as `src/storage/pe-dashboard-sa-key.json`
4. Grant "Storage Object Admin" role

### Step 6: Run Services

**Terminal 1 - MCP Server:**
```bash
python src/server/mcp_server.py
```

**Terminal 2 - Streamlit Dashboard:**
```bash
streamlit run src/streamlit_app.py
```

**Terminal 3 - Airflow (Optional):**
```bash
cd airflow
airflow standalone
```

### Step 7: Verify Setup

- MCP Server: http://localhost:8100/docs
- Streamlit: http://localhost:8501
- Airflow: http://localhost:8080

---

## 🐳 Docker Deployment

### Step 1: Create Dockerfiles

Create `docker/Dockerfile.mcp`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY data/ data/

# Expose port
EXPOSE 8100

# Run MCP server
CMD ["python", "-m", "uvicorn", "src.server.mcp_server:app", "--host", "0.0.0.0", "--port", "8100"]
```

Create `docker/Dockerfile.api`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY data/ data/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Create `docker/Dockerfile.streamlit`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

EXPOSE 8501

CMD ["streamlit", "run", "src/streamlit_app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
```

### Step 2: Create Environment File

Create `.env` in project root (NOT inside src):

```env
OPENAI_KEY=sk-proj-...
CHROMA_API_KEY=...
CHROMA_TENANT=...
CHROMA_DB=...
GCS_BUCKET_NAME=ai-pe-dashboard
GOOGLE_CLOUD_PROJECT=your-project
```

### Step 3: Build and Run

```bash
# Build all services
docker-compose -f airflow/docker_compose_airflow.yaml build

# Start all services
docker-compose -f airflow/docker_compose_airflow.yaml up -d

# View logs
docker-compose -f airflow/docker_compose_airflow.yaml logs -f

# Stop all services
docker-compose -f airflow/docker_compose_airflow.yaml down
```

### Step 4: Access Services

- **Airflow UI**: http://localhost:8080 (admin/admin)
- **MCP Server**: http://localhost:8100
- **API**: http://localhost:8000
- **Streamlit**: http://localhost:8501

---

## 🌐 Production Deployment

### Option 1: Google Cloud Run

#### Deploy MCP Server

```bash
# Build image
gcloud builds submit --tag gcr.io/your-project/mcp-server

# Deploy to Cloud Run
gcloud run deploy mcp-server \
  --image gcr.io/your-project/mcp-server \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "OPENAI_KEY=$OPENAI_KEY,CHROMA_API_KEY=$CHROMA_API_KEY"
```

#### Deploy Streamlit

```bash
gcloud builds submit --tag gcr.io/your-project/streamlit-app

gcloud run deploy streamlit-dashboard \
  --image gcr.io/your-project/streamlit-app \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "MCP_SERVER_URL=https://mcp-server-xxx.run.app"
```

### Option 2: AWS ECS/Fargate

1. Push images to ECR
2. Create ECS task definitions
3. Create ECS services
4. Configure Application Load Balancer
5. Set environment variables in task definition

### Option 3: Kubernetes

```yaml
# k8s/mcp-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mcp-server
  template:
    metadata:
      labels:
        app: mcp-server
    spec:
      containers:
      - name: mcp-server
        image: your-registry/mcp-server:latest
        ports:
        - containerPort: 8100
        env:
        - name: OPENAI_KEY
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: openai-key
```

---

## ⚙️ Environment Configuration

### Development

```env
# Development settings
ENVIRONMENT=local
LOG_LEVEL=DEBUG
AIRFLOW__CORE__LOAD_EXAMPLES=True
```

### Staging

```env
ENVIRONMENT=staging
LOG_LEVEL=INFO
GCS_BUCKET_NAME=ai-pe-dashboard-staging
```

### Production

```env
ENVIRONMENT=production
LOG_LEVEL=WARNING
GCS_BUCKET_NAME=ai-pe-dashboard-prod
AIRFLOW__CORE__LOAD_EXAMPLES=False
```

---

## 🔐 Security Checklist

- [ ] All API keys stored in environment variables
- [ ] GCS service account has minimal permissions
- [ ] `.env` files in `.gitignore`
- [ ] Secrets managed with Google Secret Manager (production)
- [ ] HTTPS enabled for all services
- [ ] Authentication enabled for Airflow
- [ ] Network policies configured
- [ ] Regular credential rotation

---

## 📊 Monitoring

### Health Checks

```bash
# MCP Server
curl http://localhost:8100/health

# API
curl http://localhost:8000/health

# Airflow
curl http://localhost:8080/health
```

### Logs

```bash
# Docker logs
docker-compose logs -f airflow
docker-compose logs -f mcp-server

# Airflow task logs
docker exec airflow airflow tasks logs <dag_id> <task_id> <execution_date>
```

### Metrics to Monitor

- API response times
- Dashboard generation success rate
- RAG search latency
- GCS storage usage
- Airflow DAG success/failure rate

---

## 🐛 Troubleshooting

### Issue: Docker Compose `.env` error on Windows

**Error:** `Incorrect function` when reading `.env`

**Solution:** Use environment variables directly in docker-compose.yaml instead of `env_file`

```yaml
environment:
  OPENAI_KEY: ${OPENAI_KEY}
  # instead of:
  # env_file: - ../.env
```

### Issue: GCS credentials not found

**Error:** `File pe-dashboard-sa-key.json was not found`

**Solution:**
```bash
# Check file exists
ls src/storage/pe-dashboard-sa-key.json

# Verify .env path
cat src/.env | grep GOOGLE_APPLICATION_CREDENTIALS

# Should be relative path: src/storage/pe-dashboard-sa-key.json
```

### Issue: Airflow DAGs not appearing

**Error:** "0 Dags" in Airflow UI

**Solution:**
```bash
# Check DAG files exist
docker exec airflow ls -la /opt/airflow/dags

# Check for import errors
docker exec airflow airflow dags list-import-errors

# Restart scheduler
docker-compose restart airflow
```

### Issue: ChromaDB connection failed

**Error:** Connection timeout to ChromaDB

**Solution:**
```bash
# Verify credentials
echo $CHROMA_API_KEY

# Test connection
python -c "from chromadb import HttpClient; client = HttpClient(host='api.trychroma.com', api_key='$CHROMA_API_KEY')"
```

### Issue: MCP Server returns 404 for dashboard

**Error:** "No unified dashboard found in GCS"

**Solution:**
```bash
# Generate dashboard first using supervisor agent
python src/agents/supervisor_mcp.py anthropic

# Or generate for all companies
python src/agents/supervisor_mcp.py --all
```

---

## 🔄 Update & Maintenance

### Update Dependencies

```bash
pip install --upgrade -r requirements.txt
pip freeze > requirements.txt
```

### Update Docker Images

```bash
# Rebuild images
docker-compose build --no-cache

# Pull latest base images
docker-compose pull
```

### Database Migrations

```bash
# Airflow database
docker exec airflow airflow db migrate

# Check migration status
docker exec airflow airflow db check
```

---

## 📈 Scaling

### Horizontal Scaling

- Deploy multiple MCP server instances behind load balancer
- Use Redis for caching frequently accessed dashboards
- Scale Airflow workers for parallel DAG execution

### Optimization

- Enable dashboard caching (TTL: 1 hour)
- Batch process companies during off-peak hours
- Use Cloud CDN for static assets
- Implement rate limiting on API endpoints

---

## 🧪 Testing Deployment

### Smoke Tests

```bash
# Test MCP Server
curl http://localhost:8100/health

# Test companies endpoint
curl http://localhost:8100/resource/ai50/companies

# Test dashboard generation
curl -X POST http://localhost:8100/tool/generate_unified_dashboard \
  -H "Content-Type: application/json" \
  -d '{"company_id": "anthropic"}'

# Test Streamlit
curl http://localhost:8501
```

### Load Testing

```bash
# Install Apache Bench
apt-get install apache2-utils

# Test API performance
ab -n 100 -c 10 http://localhost:8100/health
```

---

## 📝 Deployment Checklist

### Pre-Deployment

- [ ] All environment variables configured
- [ ] GCS bucket created and accessible
- [ ] Service account credentials downloaded
- [ ] ChromaDB collection initialized
- [ ] Docker images built successfully
- [ ] All services pass health checks

### Post-Deployment

- [ ] Verify all services are running
- [ ] Test dashboard generation
- [ ] Check Airflow DAG execution
- [ ] Monitor logs for errors
- [ ] Test end-to-end workflow
- [ ] Setup monitoring alerts

---

## 🆘 Support

For deployment issues:

1. Check logs: `docker-compose logs -f`
2. Verify environment variables: `docker-compose config`
3. Review troubleshooting section above
4. Open GitHub issue with error details

---

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Airflow Documentation](https://airflow.apache.org/docs/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Streamlit Deployment](https://docs.streamlit.io/deploy)
- [Google Cloud Storage](https://cloud.google.com/storage/docs)

---

**Last Updated:** November 2025  
**Maintained By:** Your Team Name