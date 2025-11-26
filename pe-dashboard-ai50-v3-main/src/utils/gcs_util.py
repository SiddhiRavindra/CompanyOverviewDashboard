import os
import json
from typing import Optional, List
from google.cloud import storage

# This will be set by an environment variable in Cloud Run
BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

# Initialize the client.
# This automatically uses the Cloud Run service account for authentication.
storage_client = None
_bucket = None

def get_bucket():
    """Gets the GCS bucket object, initializing the client if needed."""
    global storage_client, _bucket
    if not BUCKET_NAME:
        print("CRITICAL: GCS_BUCKET_NAME environment variable is not set.")
        raise ValueError("GCS_BUCKET_NAME environment variable is not set.")
    
    if not storage_client:
        storage_client = storage.Client()

    if not _bucket:
        try:
            _bucket = storage_client.get_bucket(BUCKET_NAME)
        except Exception as e:
            print(f"CRITICAL: Failed to get bucket '{BUCKET_NAME}': {e}")
            return None
    return _bucket

def read_gcs_json_string(blob_name: str) -> Optional[str]:
    """
    Reads a file from GCS and returns its raw text content.
    Expects blob_name relative to the 'data/' folder.
    e.g., 'payloads/company_id.json' or 'forbes_ai50_seed.json'
    """
    try:
        bucket = get_bucket()
        if not bucket:
            return None
        
        # We assume all data is inside the 'data/' folder in the bucket
        full_blob_name = f"data/{blob_name}"
        blob = bucket.blob(full_blob_name)
        
        if not blob.exists():
            print(f"File not found in GCS: {full_blob_name}")
            return None

        return blob.download_as_text()
    except Exception as e:
        print(f"Error reading GCS file {blob_name}: {e}")
        return None

def read_gcs_json(blob_name: str) -> Optional[dict]:
    """Reads a JSON file from GCS and returns its parsed content."""
    data_string = read_gcs_json_string(blob_name)
    if not data_string:
        return None
    
    try:
        return json.loads(data_string)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {blob_name}: {e}")
        return None

def list_gcs_files(prefix: str) -> List[str]:
    """
    Lists file 'stems' (filenames without extension) in a GCS 'folder'.
    Expects prefix relative to the 'data/' folder.
    e.g., 'payloads'
    """
    try:
        bucket = get_bucket()
        if not bucket:
            return []
        
        # We assume all data is inside the 'data/' folder in the bucket
        full_prefix = f"data/{prefix}"
        # Ensure the prefix ends with a '/' to treat it as a folder
        if not full_prefix.endswith('/'):
            full_prefix += '/'
            
        blobs = storage_client.list_blobs(bucket, prefix=full_prefix)
        
        filenames = set()
        for blob in blobs:
            if blob.name.endswith('.json'):
                # Get just the filename (e.g., "abridge.json")
                file_name_with_ext = blob.name.split('/')[-1]
                if file_name_with_ext: # Avoid empty strings if prefix is a file
                    # Get the stem (e.g., "abridge")
                    stem = file_name_with_ext.rsplit('.', 1)[0]
                    filenames.add(stem)
                
        return sorted(list(filenames))
    except Exception as e:
        print(f"Error listing GCS files {prefix}: {e}")
        return []