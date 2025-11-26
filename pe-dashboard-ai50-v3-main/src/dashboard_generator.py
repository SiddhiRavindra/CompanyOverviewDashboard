"""Dashboard generation using LLM for both structured and RAG pipelines."""

import os
from pathlib import Path
from typing import List, Dict

from dotenv import load_dotenv
from openai import OpenAI

# from models import Payload
from src.models import Payload

load_dotenv(override=True)

DEFAULT_MODEL = "gpt-4o-mini"


def _load_dashboard_prompt() -> str:
    """Load the dashboard system prompt."""
    prompt_path = Path(__file__).parent / "prompts" / "dashboard_system.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Dashboard prompt not found at {prompt_path}")
    return prompt_path.read_text()


def _get_openai_client() -> OpenAI:
    """Get OpenAI client from environment."""
    api_key = os.getenv('OPENAI_KEY')
    if not api_key:
        raise RuntimeError("OPENAI_KEY not set; cannot generate dashboard.")
    return OpenAI(api_key=api_key)


def generate_dashboard(payload: Payload) -> str:
    """
    Generate dashboard markdown from structured payload.
    
    Args:
        payload: Payload object containing company data
        
    Returns:
        Markdown string with 8 required sections
    """
    # Load system prompt
    system_prompt = _load_dashboard_prompt()
    
    # Convert payload to JSON string
    payload_json = payload.model_dump_json(indent=2)
    
    # Build messages
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Generate an investor-facing dashboard from this payload:\n\n{payload_json}"
        }
    ]
    
    # Call OpenAI
    client = _get_openai_client()
    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            temperature=0.3,
        )
        markdown = response.choices[0].message.content
        
        if not markdown:
            raise RuntimeError("LLM returned empty response")
        
        return markdown
    except Exception as e:
        raise RuntimeError(f"Failed to generate dashboard: {str(e)}") from e


def generate_dashboard_from_rag(company_name: str, context: List[Dict]) -> str:
    """
    Generate dashboard markdown from RAG context.
    
    This is a placeholder implementation that will be enhanced when vector DB is ready.
    
    Args:
        company_name: Name of the company
        context: List of retrieved context chunks with 'source_url' and 'text' keys
        
    Returns:
        Markdown string with 8 required sections
    """
    # Load system prompt
    system_prompt = _load_dashboard_prompt()
    
    # Format context as text
    context_text = ""
    for chunk in context:
        source_url = chunk.get("source_url", "unknown")
        text = chunk.get("text", "")
        context_text += f"Source: {source_url}\n"
        context_text += f"Content: {text}\n\n"
    
    # Build messages
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Company: {company_name}\n\n"
                f"Retrieved Context:\n{context_text}\n\n"
                "Generate an investor-facing dashboard using ONLY the information provided above. "
                "If information is missing, write 'Not disclosed.'"
            )
        }
    ]
    
    # Call OpenAI
    client = _get_openai_client()
    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            temperature=0.3,
        )
        markdown = response.choices[0].message.content
        
        if not markdown:
            raise RuntimeError("LLM returned empty response")
        
        return markdown
    except Exception as e:
        raise RuntimeError(f"Failed to generate dashboard from RAG: {str(e)}") from e

