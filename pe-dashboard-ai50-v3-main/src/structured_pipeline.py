# # import os
# # import dotenv
# # from pathlib import Path
# # from typing import Optional
# # from models import Payload
# # from utils import gcs_util as gcs_utils 

# # dotenv.load_dotenv()
# # ENVIRONMENT = os.getenv("ENVIRONMENT", 'local')

# # if ENVIRONMENT == "local":
# #     DATA_DIR = Path(__file__).resolve().parent / "data" / "payloads"
# #     print(DATA_DIR)

# import os
# import dotenv
# from pathlib import Path
# from typing import Optional
# from models import Payload
# from utils import gcs_util as gcs_utils 

# dotenv.load_dotenv()
# ENVIRONMENT = os.getenv("ENVIRONMENT", 'local')  # Set to local for testing

# if ENVIRONMENT == "local":
#     DATA_DIR = Path(__file__).resolve().parents[1]/ "data" / "payloads"


# # def load_payload(company_id: str) -> Optional[Payload]:
# #     """Load payload with proper encoding handling."""
    
# #     if ENVIRONMENT == "local":
# #         fp = DATA_DIR / f"{company_id}.json"
# #         # print("fp:{fp}")
        
# #         if not fp.exists():
# #             # Fallback to starter
# #             starter = Path(__file__).resolve().parents[1] / "data" / "starter_payload.json"
# #             if starter.exists():
# #                 try:
# #                     # Use UTF-8 encoding explicitly
# #                     return Payload.model_validate_json(starter.read_text(encoding='utf-8'))
# #                 except Exception as e:
# #                     print(f"Error loading starter: {e}")
# #                     return None
# #             return None
        
#     #     try:
#     #         # FIXED: Use UTF-8 encoding to handle special characters
#     #         json_content = fp.read_text(encoding='utf-8')
#     #         return Payload.model_validate_json(json_content)
#     #     except UnicodeDecodeError as e:
#     #         print(f"❌ Unicode error in {fp}: {e}")
#     #         # Try with different encoding
#     #         try:
#     #             json_content = fp.read_text(encoding='latin-1')
#     #             return Payload.model_validate_json(json_content)
#     #         except Exception as e2:
#     #             print(f"❌ Failed with latin-1 too: {e2}")
#     #             return None
#     #     except Exception as e:
#     #         print(f"❌ Error loading payload {company_id}: {e}")
#     #         return None
    
#     # else:
#     #     # GCS mode
#     #     try:
#     #         json_str = gcs_utils.read_gcs_json_string(f"payloads/{company_id}.json")
#     #         if json_str:
#     #             return Payload.model_validate_json(json_str)
#     #         return None
#     #     except Exception as e:
#     #         print(f"Error loading from GCS: {e}")
#     #         return None    


# # def load_payload(company_id: str) -> Optional[Payload]:
# #     if ENVIRONMENT == "local":
# #         fp = DATA_DIR / f"{company_id}.json"
# #     else:
# #         fp = gcs_utils.read_gcs_json_string(f"payloads/{company_id}.json")
# #     if not fp.exists():
# #         # fallback to starter
# #         starter = Path(__file__).resolve().parents[1] / "data" / "starter_payload.json"
# #         return Payload.model_validate_json(starter.read_text())
# #     return Payload.model_validate_json(fp.read_text())


# def load_payload(company_id: str) -> Optional[Payload]:
#     # Try to load the specific company payload from GCS
#     # 'read_gcs_json_string' returns the raw text, which Pydantic needs
#     payload_str = gcs_utils.read_gcs_json_string(f"payloads/{company_id}.json")
    
#     if not payload_str:
#         # If it doesn't exist, fall back to the starter payload from GCS
#         print(f"Payload {company_id}.json not found. Falling back to starter.")
#         payload_str = gcs_utils.read_gcs_json_string("starter_payload.json")

#     if not payload_str:
#         # If *neither* exists, we have a problem.
#         print(f"CRITICAL: starter_payload.json not found in GCS.")
#         return None

#     # Use the raw string to validate with Pydantic
#     try:
#         return Payload.model_validate_json(payload_str)
#     except Exception as e:
#         print(f"Error validating payload {company_id} or starter: {e}")
#         return None



import os
import dotenv
from pathlib import Path
from typing import Optional
from src.models import Payload
from src.utils import gcs_util as gcs_utils 
# from models import Payload
# from utils import gcs_util as gcs_utils 

dotenv.load_dotenv()
ENVIRONMENT = os.getenv("ENVIRONMENT", 'production')

if ENVIRONMENT == "local":
    DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "payloads"


def load_payload(company_id: str) -> Optional[Payload]:
    if ENVIRONMENT == "local":
        fp = DATA_DIR / f"{company_id}.json"
        if not fp.exists():
            # Return None if company file doesn't exist (don't fall back to starter)
            return None
        try:
            return Payload.model_validate_json(fp.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"Error loading payload {company_id}: {e}")
            return None
    else:
        # GCS mode - read_gcs_json_string returns a string or None
        payload_str = gcs_utils.read_gcs_json_string(f"payloads/{company_id}.json")
        
        if not payload_str:
            # Return None if company file doesn't exist (don't fall back to starter)
            return None
        
        try:
            return Payload.model_validate_json(payload_str)
        except Exception as e:
            print(f"Error validating payload {company_id}: {e}")
            return None