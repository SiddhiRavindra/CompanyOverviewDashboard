"""
Test GCS upload functionality
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ✅ FIX 1: Load .env from src/.env
env_path = project_root / '.env'
print(f"📂 Loading .env from: {env_path}")
print(f"   .env exists: {env_path.exists()}")

load_dotenv(dotenv_path=env_path, override=True)

# ✅ FIX 2: Explicitly set credentials path
credentials_relative = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
print(f"\n🔍 Debug - From .env:")
print(f"   GOOGLE_APPLICATION_CREDENTIALS: {credentials_relative}")
print(f"   GOOGLE_CLOUD_PROJECT: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
print(f"   GCS_BUCKET_NAME: {os.getenv('GCS_BUCKET_NAME')}")

# ✅ FIX 3: Build absolute path to credentials
if credentials_relative:
    # Your .env says: src/storage/pedashboard-dfbfc3ba07de.json
    # We need absolute path
    credentials_path = project_root / credentials_relative
    
    print(f"\n🔑 Credentials Path:")
    print(f"   Relative: {credentials_relative}")
    print(f"   Absolute: {credentials_path}")
    print(f"   Exists: {credentials_path.exists()}")
    
    if credentials_path.exists():
        # Set environment variable with absolute path
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_path)
        print(f"   ✅ Set GOOGLE_APPLICATION_CREDENTIALS")
    else:
        print(f"   ❌ Credentials file not found!")
        print(f"   Looking at: {credentials_path}")
        
        # Debug: Show what's in src/storage/
        storage_dir = project_root / 'src' / 'storage'
        if storage_dir.exists():
            print(f"\n   Files in src/storage/:")
            for file in storage_dir.iterdir():
                print(f"     - {file.name}")
        sys.exit(1)
else:
    print(f"\n❌ GOOGLE_APPLICATION_CREDENTIALS not found in .env")
    sys.exit(1)

# Set project ID
project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
if project_id:
    os.environ['GOOGLE_CLOUD_PROJECT'] = project_id
    print(f"📦 Project ID: {project_id}")
else:
    print(f"⚠️ GOOGLE_CLOUD_PROJECT not set")

# Now import GCS client
from src.storage.gcs_client import DashboardStorage

# Test connection
print("\n" + "="*60)
print("🧪 Testing GCS Upload")
print("="*60)

# Get bucket name from env
bucket_name = os.getenv('GCS_BUCKET_NAME', 'pe-dashboard-storage')
print(f"\n🪣 Bucket: {bucket_name}")

try:
    storage = DashboardStorage(bucket_name)
    print("✅ GCS client initialized successfully\n")
except Exception as e:
    print(f"\n❌ Failed to initialize GCS client: {e}")
    print("\nTroubleshooting:")
    print(f"  - Credentials path: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
    print(f"  - File exists: {Path(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')).exists() if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') else False}")
    print(f"  - Project ID: {os.environ.get('GOOGLE_CLOUD_PROJECT')}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test upload
test_dashboard = """# Test Dashboard

## 1. Company Overview
Test content from automated test script

## 2. Business Model and GTM
Test business model content

## 3. Funding & Investor Profile
Test funding information

## 4. Growth Momentum
Test growth metrics

## 5. Visibility & Market Sentiment
Test visibility data

## 6. Risks and Challenges
Test risk analysis

## 7. Outlook
Test outlook information

## 8. Disclosure Gaps
- Missing test data
- Unknown test metrics
"""

print("📤 Uploading test dashboard...")

try:
    # Upload
    uri = storage.save_dashboard(
        company_id="test-company",
        content=test_dashboard,
        dashboard_type="test",
        metadata={
            "test": True,
            "generator": "test_script",
            "sections": 8
        }
    )
    
    print(f"\n✅ Successfully saved to: {uri}")
    
except Exception as e:
    print(f"\n❌ Upload failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# List dashboards
print("\n📋 Listing dashboards for test-company...")

try:
    dashboards = storage.list_dashboards("test-company")
    print(f"✅ Found {len(dashboards)} dashboard(s):")
    for d in dashboards:
        print(f"\n  📄 {d['name']}")
        print(f"     Size: {d['size']} bytes")
        print(f"     Created: {d['created']}")
        print(f"     URI: {d['uri']}")
    
except Exception as e:
    print(f"❌ List failed: {e}")

print("\n✅ All tests completed!")