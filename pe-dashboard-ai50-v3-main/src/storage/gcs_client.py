"""
Cloud Storage client for saving dashboards to GCS
Fixed to use GOOGLE_APPLICATION_CREDENTIALS from .env
"""

import os
from google.cloud import storage
from datetime import datetime
from pathlib import Path
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DashboardStorage:
    """Client for storing dashboards in Google Cloud Storage"""
    
    def __init__(self, bucket_name: str = None):
        """Initialize GCS client using credentials from environment"""
        
        self.bucket_name = bucket_name or os.getenv("GCS_BUCKET_NAME", "ai-pe-dashboard")
        
        try:
            # Get credentials path from environment
            creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            
            if creds_path:
                # Convert to absolute path if relative
                if not os.path.isabs(creds_path):
                    # Get project root (3 levels up from gcs_client.py)
                    project_root = Path(__file__).resolve().parents[2]
                    creds_path = project_root / creds_path
                
                creds_path = str(creds_path)
                
                # Verify file exists
                if not os.path.exists(creds_path):
                    raise FileNotFoundError(f"Credentials file not found: {creds_path}")
                
                # Set environment variable to absolute path
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path
                print(f"  🔑 Using credentials: {creds_path}")
            
            # Initialize GCS client (will use GOOGLE_APPLICATION_CREDENTIALS automatically)
            self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)
            
            # Verify bucket exists
            if not self.bucket.exists():
                raise ValueError(f"GCS bucket '{self.bucket_name}' does not exist")
            
            logger.info(f"GCS client initialized with bucket: {self.bucket_name}")
            print(f"  ✅ Connected to GCS bucket: {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {e}")
            raise
    
    def save_dashboard(
        self,
        company_id: str,
        content: str,
        dashboard_type: str = "unified",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save dashboard to GCS
        
        Args:
            company_id: Company identifier
            content: Dashboard markdown content
            dashboard_type: Type ('unified', 'structured', 'rag')
            metadata: Optional metadata dict
        
        Returns:
            GCS URI (gs://bucket/path)
        """
        
        try:
            # Create blob path: data/dashboards/{company_id}/unified_20251120_143022.md
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            blob_name = f"data/dashboards/{company_id}/{dashboard_type}_{timestamp}.md"
            
            # Upload dashboard
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(
                content,
                content_type='text/markdown'
            )
            
            logger.info(f"Dashboard uploaded: {blob_name}")
            print(f"  ✅ Uploaded: gs://{self.bucket_name}/{blob_name}")
            
            # Save metadata if provided
            if metadata:
                metadata_blob_name = f"data/dashboards/{company_id}/{dashboard_type}_{timestamp}_metadata.json"
                metadata_blob = self.bucket.blob(metadata_blob_name)
                metadata_blob.upload_from_string(
                    json.dumps(metadata, indent=2, default=str),
                    content_type='application/json'
                )
                logger.info(f"Metadata uploaded: {metadata_blob_name}")
            
            gcs_uri = f"gs://{self.bucket_name}/{blob_name}"
            return gcs_uri
        
        except Exception as e:
            logger.error(f"Failed to save dashboard to GCS: {e}")
            raise
    
    def save_risk_log(self, company_id: str, risks: list) -> str:
        """Save risk log to GCS"""
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            blob_name = f"data/risks/{company_id}/risks_{timestamp}.json"
            
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(
                json.dumps(risks, indent=2, default=str),
                content_type='application/json'
            )
            
            logger.info(f"Risk log uploaded: {blob_name}")
            
            return f"gs://{self.bucket_name}/{blob_name}"
        
        except Exception as e:
            logger.error(f"Failed to save risks to GCS: {e}")
            raise
    
    def get_latest_dashboard(self, company_id: str, dashboard_type: str = "unified") -> Optional[str]:
        """Get most recent dashboard for a company from GCS"""
        
        try:
            prefix = f"data/dashboards/{company_id}/{dashboard_type}_"
            blobs = list(self.bucket.list_blobs(prefix=prefix))
            
            if not blobs:
                logger.warning(f"No dashboards found for {company_id} with type {dashboard_type}")
                return None
            
            # Filter to only .md files (exclude metadata.json)
            md_blobs = [b for b in blobs if b.name.endswith('.md')]
            
            if not md_blobs:
                logger.warning(f"No .md files found for {company_id}")
                return None
            
            # Get most recent .md file by creation time
            latest_blob = max(md_blobs, key=lambda b: b.time_created)
            content = latest_blob.download_as_text()
            
            logger.info(f"Retrieved dashboard: {latest_blob.name}")
            print(f"  ✅ Retrieved from GCS: {latest_blob.name}")
            
            return content
        
        except Exception as e:
            logger.error(f"Failed to retrieve dashboard: {e}")
            return None
    
    def list_dashboards(self, company_id: str = None) -> list:
        """List all dashboards (optionally filtered by company)"""
        
        try:
            prefix = f"data/dashboards/{company_id}/" if company_id else "data/dashboards/"
            blobs = list(self.bucket.list_blobs(prefix=prefix))
            
            dashboards = [
                {
                    "name": blob.name,
                    "size": blob.size,
                    "created": blob.time_created.isoformat(),
                    "uri": f"gs://{self.bucket_name}/{blob.name}",
                    "public_url": blob.public_url
                }
                for blob in blobs
                if blob.name.endswith('.md')
            ]
            
            return dashboards
        
        except Exception as e:
            logger.error(f"Failed to list dashboards: {e}")
            return []