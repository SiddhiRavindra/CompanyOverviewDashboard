"""
Ingestion Script - Load data, chunk with LangChain, and store in ChromaDB
"""

import os
import sys
from pathlib import Path
import time
from typing import List
from dotenv import load_dotenv
from rag_pipeline import VectorStore, load_company_data_from_disk

# Load .env from project root - FORCE OVERRIDE
env_path = Path(__file__).parent.parent / 'src'/'.env'
print(f"Loading .env from: {env_path}")
load_dotenv(dotenv_path=env_path, override=True)  # ← Add override=True


project_root=Path(__file__).parent.parent
print("This is project root -",project_root)
datapath=project_root/'data'/'raw'
print("Data Path is - ",datapath)
#'C:/Users/dhama/OneDrive/Desktop/pe_dasdboard/data/raw')
# getdatapath = datapath
#os.getenv('DATA_PATH','C:/Users/dhama/OneDrive/Desktop/pe_dasdboard/data/raw',override=True)


def clean_env_value(value):
    """Remove quotes from environment variable values."""
    if value is None:
        return None
    value = value.strip()
    if (value.startswith("'") and value.endswith("'")) or \
       (value.startswith('"') and value.endswith('"')):
        value = value[1:-1]
    return value


def get_all_companies(base_path: str) -> List[str]:
    """Get list of all company directories."""
    base = Path(base_path)
    companies = []

    # Debug: Show what we're looking for
    print(f"  Scanning directory: {base_path}")
    
    if not base_path.exists():
        print(f"  ⚠️ Directory doesn't exist: {base_path}")
        return []
    
    for item in base.iterdir():
        if item.is_dir():
            initial_path = item
            if initial_path.exists():
                companies.append(item.name)
    
    return sorted(companies)


def ingest_single_company(
    company_name: str,
    base_path: str,
    vector_store: VectorStore,
    force_refresh: bool = False
) -> bool:
    """Ingest a single company's data using LangChain."""
    print(f"\n{'='*70}")
    print(f"📦 Processing: {company_name}")
    print(f"{'='*70}")
    
    try:
        # Load from disk
        print("Loading scraped data...")
        scraped_data = load_company_data_from_disk(company_name, base_path)
        
        if not scraped_data:
            print(f"❌ No data found for {company_name}")
            return False
        
        print(f"✓ Loaded {len(scraped_data)} sources:")
        for source in scraped_data:
            print(f"  - {source['source_type']}: {len(source['text'])} chars")
        
        # Chunk with LangChain and store with OpenAI embeddings
        print("\nChunking with LangChain and embedding with OpenAI...")
        stats = vector_store.ingest_company_data(
            company_name=company_name,
            scraped_data=scraped_data,
            force_refresh=force_refresh
        )
        
        # Print stats
        print(f"\n📊 Ingestion Stats:")
        print(f"  ✓ Sources processed: {stats['sources_processed']}")
        print(f"  ✓ Chunks created: {stats['chunks_created']}")
        print(f"  ✓ Chunks stored: {stats['chunks_stored']}")
        
        if stats['errors']:
            print(f"  ⚠️  Errors: {len(stats['errors'])}")
            for error in stats['errors'][:3]:
                print(f"    - {error}")
        
        return stats['chunks_stored'] > 0
        
    except Exception as e:
        print(f"❌ Failed to ingest {company_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main ingestion process with LangChain."""
    print("="*70)
    print("🚀 Lab 4: LangChain Chunking + OpenAI Embeddings")
    print("="*70)
    
    # Load and clean environment variables
    chroma_api_key = clean_env_value(os.getenv('CHROMA_API_KEY'))
    chroma_tenant = clean_env_value(os.getenv('CHROMA_TENANT'))
    chroma_db = clean_env_value(os.getenv('CHROMA_DB'))
   
    openai_api_key = clean_env_value(os.getenv('OPENAI_KEY'))
    data_path = datapath
    
    # Debug: Show what was loaded (without showing full keys)
    print("\n🔍 Environment Variables:")
    print(f"  CHROMA_API_KEY: {'✓ Set' if chroma_api_key else '✗ Missing'}")
    print(f"  CHROMA_TENANT: {'✓ Set' if chroma_tenant else '✗ Missing'}")
    print(f"  CHROMA_DB: {'✓ Set' if chroma_db else '✗ Missing'}")
    print(f"  OPENAI_KEY: {'✓ Set' if openai_api_key else '✗ Missing'}")
    print(f"  DATA_PATH: {datapath}")
    
    if not all([chroma_api_key, chroma_tenant, chroma_db, openai_api_key]):
        print("\n❌ Missing required credentials in .env")
        print("Required: CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DB, OPENAI_KEY")
        sys.exit(1)
    
    print(f"\n✓ All credentials loaded")
    
    # Verify data path
    if not Path(datapath).exists():
        print(f"❌ Data path does not exist: {datapath}")
        sys.exit(1)
    
    print(f"✓ Data path exists")
    
    # Initialize ChromaDB with LangChain
    try:
        print("\n🔌 Initializing LangChain + ChromaDB + OpenAI...")
        vector_store = VectorStore(
            api_key=chroma_api_key,
            tenant=chroma_tenant,
            database=chroma_db,
            openai_api_key=openai_api_key,  # ← THIS IS REQUIRED NOW
            chunk_size=1000,                 # ~750 tokens
            chunk_overlap=200                # Overlap for context
        )
    except Exception as e:
        print(f"❌ Initialization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Get companies
    print("\n🔍 Discovering companies...")
    companies = get_all_companies(datapath)
    
    if not companies:
        print("❌ No companies found")
        sys.exit(1)
    
    print(f"✓ Found {len(companies)} companies:")
    for i, company in enumerate(companies[:10], 1):
        print(f"  {i}. {company}")
    if len(companies) > 10:
        print(f"  ... and {len(companies) - 10} more")
    
    # Confirm
    print(f"\n⚠️  This will chunk and embed data for {len(companies)} companies using OpenAI.")
    print(f"⚠️  Note: OpenAI embeddings API will be called (costs ~$0.00013 per 1K tokens)")
    response = input("Continue? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("Cancelled.")
        sys.exit(0)
    
    # Ask about refresh
    refresh_response = input("Force refresh (delete existing)? (yes/no): ").strip().lower()
    force_refresh = refresh_response in ['yes', 'y']
    
    # Process all companies
    print(f"\n{'='*70}")
    print("Starting ingestion with LangChain...")
    print(f"{'='*70}")
    
    success = 0
    fail = 0
    start_time = time.time()
    
    for idx, company in enumerate(companies, 1):
        print(f"\n[{idx}/{len(companies)}] {company}")
        
        try:
            if ingest_single_company(company, datapath, vector_store, force_refresh):
                success += 1
            else:
                fail += 1
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            fail += 1
        
        time.sleep(0.5)
    
    # Summary
    elapsed = time.time() - start_time
    print(f"\n{'='*70}")
    print(f"✅ Ingestion Complete")
    print(f"{'='*70}")
    print(f"  Success: {success}")
    print(f"  Failed: {fail}")
    print(f"  Total: {len(companies)}")
    print(f"  Time: {elapsed:.2f}s ({elapsed/60:.2f} min)")
    
    # Show stats
    try:
        stats = vector_store.get_stats()
        print(f"\n📊 Vector Store Stats:")
        print(f"  Total chunks: {stats.get('total_chunks', 0)}")
        print(f"  Companies: {stats.get('total_companies', 0)}")
        print(f"  Embedding model: {stats.get('embedding_model', 'unknown')}")
        print(f"  Chunking method: {stats.get('chunking_method', 'unknown')}")
    except:
        pass


if __name__ == "__main__":
    main()