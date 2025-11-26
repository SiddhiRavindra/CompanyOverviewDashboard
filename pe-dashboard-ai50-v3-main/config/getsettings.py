import yaml

with open('config.yaml') as f:
    config = yaml.safe_load(f)

MCP_BASE = config['mcp']['base_url']
VECTOR_DB_URL = config['vector_db']['url']
STREAMLIT=config['streamlit']['url']