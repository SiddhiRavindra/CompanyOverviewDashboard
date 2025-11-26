"""
Tool: get_latest_structured_payload

Retrieves the latest fully assembled structured payload for a company from the data/payloads directory.
This payload includes company_record, events, snapshots, products, leadership, and visibility data.
"""

from typing import Optional
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, HttpUrl


# from src.models import Payload
#windows
from models import Payload


async def get_latest_structured_payload(company_id: str) -> Payload:
    """
    Tool: get_latest_structured_payload

    Retrieve the latest fully assembled structured payload for a company.
    The payload should include:
      - company_record
      - events
      - snapshots
      - products
      - leadership
      - visibility

    Args:
        company_id: The canonical company_id used in your data pipeline.

    Returns:
        A Payload object for the requested company.

    Raises:
        ValueError: If company_id is empty or None.
        FileNotFoundError: If the payload file does not exist for the given company_id.
        ValueError: If the JSON file is invalid or cannot be parsed.
        ValidationError: If the JSON data does not match the Payload schema (raised by Pydantic).
    """
    # Validate input
    if not company_id or not company_id.strip():
        raise ValueError("company_id cannot be empty or None")
    
    # Construct path to payload file
    # From: src/tools/payload_tool.py
    # To:   data/payloads/{company_id}.json
    project_root = Path(__file__).parent.parent.parent
    payload_dir = project_root / "data" / "payloads"
    payload_file = payload_dir / f"{company_id}.json"
    
    # Check if file exists
    if not payload_file.exists():
        raise FileNotFoundError(
            f"Payload not found for company_id: {company_id}. "
            f"Expected file at: {payload_file}"
        )
    
    # Load and parse JSON
    try:
        with open(payload_file, 'r', encoding='utf-8') as f:
            payload_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in payload file for company_id: {company_id}. "
            f"Error: {str(e)}"
        ) from e
    except Exception as e:
        raise ValueError(
            f"Error reading payload file for company_id: {company_id}. "
            f"Error: {str(e)}"
        ) from e
    
    # Validate and return Pydantic model
    # Pydantic will raise ValidationError if the data doesn't match the schema
    try:
        return Payload(**payload_data)
    except Exception as e:
        raise ValueError(
            f"Payload validation failed for company_id: {company_id}. "
            f"Error: {str(e)}"
        ) from e