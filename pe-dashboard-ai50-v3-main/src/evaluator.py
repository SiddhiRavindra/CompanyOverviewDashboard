"""
evaluate.py
Unified evaluator for comparing RAG vs Structured pipelines
Scores based on factual correctness, schema adherence, provenance, hallucination control, and readability.
"""

import os
import json
import re
from pathlib import Path
from statistics import mean
from dotenv import load_dotenv
from tabulate import tabulate
from openai import OpenAI

from rag_pipeline import VectorStore
from structured_pipeline import load_payload
from dashboard_generator import generate_dashboard, generate_dashboard_from_rag


# ==========================
# Setup
# ==========================

load_dotenv()
DEFAULT_MODEL = "gpt-4o-mini"
client = OpenAI(api_key='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')


def score_dashboard(factual, schema, provenance, hallucination, readability):
    """Rubric scoring utility"""
    return factual + schema + provenance + hallucination + readability


# ==========================
# Helper functions
# ==========================

def llm_judge(company: str, rag_text: str, structured_text: str) -> dict:
    """
    Use LLM to score both pipelines according to rubric.
    Each criterion (0–3 or 0–2) scored by GPT evaluator prompt.
    """
    rubric_prompt = f"""
You are a professional evaluator comparing two dashboards (RAG and Structured) for the same company.
Each dashboard summarizes company information for investors.

Evaluate each dashboard on:
1. Factual correctness (0–3): Are the claims verifiable and accurate?
2. Schema adherence (0–2): Does the output match a fixed investor dashboard structure (8 sections)?
3. Provenance use (0–2): Does it show or reflect evidence or citation from sources?
4. Hallucination control (0–2): Does it avoid making up facts not in source data?
5. Readability / investor usefulness (0–1): Is the content readable, structured, and actionable?

Return a JSON object like:
{{
  "RAG": {{"factual": int, "schema": int, "provenance": int, "hallucination": int, "readability": int}},
  "Structured": {{"factual": int, "schema": int, "provenance": int, "hallucination": int, "readability": int}}
}}

Company: {company}

=== RAG DASHBOARD ===
{rag_text[:5000]}

=== STRUCTURED DASHBOARD ===
{structured_text[:5000]}
"""

    completion = client.chat.completions.create(
        model=DEFAULT_MODEL,
        temperature=0.0,
        messages=[
            {"role": "system", "content": "You are a strict JSON-only evaluator."},
            {"role": "user", "content": rubric_prompt}
        ],
        max_tokens=400
    )

    raw = completion.choices[0].message.content.strip()
    try:
        scores = json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group())
        return scores
    except Exception:
        print(f"⚠️ Could not parse evaluation JSON for {company}. Response:\n{raw[:300]}")
        return {}


# ==========================
# Main evaluation loop
# ==========================

def evaluate_company(company_name: str, vs: VectorStore):
    """Run evaluation for a single company comparing both pipelines."""

    print(f"\n🏢 Evaluating {company_name} ...")

    # Get RAG context + dashboard
    rag_context = vs.search(company_name, query="company overview and investors", top_k=8)
    rag_dashboard = generate_dashboard_from_rag(company_name, rag_context)

    # Get structured payload + dashboard
    payload = load_payload(company_name)
    if not payload:
        print(f"⚠️ No structured payload found for {company_name}")
        return None

    structured_dashboard = generate_dashboard(payload)

    # Get LLM evaluation
    scores = llm_judge(company_name, rag_dashboard, structured_dashboard)
    if not scores:
        return None

    rag = scores.get("RAG", {})
    structured = scores.get("Structured", {})

    rag_total = score_dashboard(**rag)
    structured_total = score_dashboard(**structured)

    return {
        "company": company_name,
        "RAG": {**rag, "total": rag_total},
        "Structured": {**structured, "total": structured_total},
    }


def main():
    vs = VectorStore(
        api_key=os.getenv("CHROMA_API_KEY"),
        tenant=os.getenv("CHROMA_TENANT"),
        database=os.getenv("CHROMA_DB"),
        openai_api_key=os.getenv("OPENAI_KEY")
    )

    companies = vs.get_company_list()
    print(f"Found {len(companies)} companies: {companies[:5]}{'...' if len(companies) > 5 else ''}")

    results = []
    for company in companies[:5]:  # limit to 5 for evaluation
        res = evaluate_company(company, vs)
        if res:
            results.append(res)

    if not results:
        print("No results generated.")
        return

    # Build table
        # Build well-aligned table
    rows = []
    for r in results:
        rag = r["RAG"]
        structured = r["Structured"]
        rows.append([
            r["company"],
            rag["total"],
            structured["total"],
            f"{rag['factual']} / {structured['factual']}",
            f"{rag['schema']} / {structured['schema']}",
            f"{rag['provenance']} / {structured['provenance']}",
            f"{rag['hallucination']} / {structured['hallucination']}",
            f"{rag['readability']} / {structured['readability']}",
        ])

    headers = [
        "Company",
        "RAG Total",
        "Structured Total",
        "Factual (R/S)",
        "Schema (R/S)",
        "Provenance (R/S)",
        "Hallucination (R/S)",
        "Readability (R/S)",
    ]

    print("\n📊 Evaluation Summary\n")
    print(tabulate(rows, headers=headers, tablefmt="github", numalign="center", stralign="center"))

    # Save as EVAL.md
    eval_md = "# Evaluation Results\n\n" + tabulate(
        rows, headers=headers, tablefmt="github", numalign="center", stralign="center"
    )
    Path("EVAL.md").write_text(eval_md)
    print("\n✅ Results saved to EVAL.md")


if __name__ == "__main__":
    main()
