"""
Project ORBIT — AI Intelligence Dashboard
Corporate Edition (Accenture / PwC style)
"""

import streamlit as st
import requests
import os
import dotenv
import pandas as pd

dotenv.load_dotenv()

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
MCP_BASE = os.environ.get("MCP_SERVER_URL", "http://localhost:8100")
# -----------------------------------------------------
# PAGE CONFIG
# -----------------------------------------------------
st.set_page_config(
    page_title="Project ORBIT — AI Intelligence Dashboard",
    page_icon="📊",
    layout="wide",
)

# -----------------------------------------------------
# HEADER
# -----------------------------------------------------

col_title, col_status = st.columns([4, 1])

with col_title:
    st.title("Project ORBIT — AI Intelligence Dashboard")
    st.caption("Automated Research & Insights Engine")

with col_status:
    try:
        health_resp = requests.get(f"{MCP_BASE}/health", timeout=2).json()
        connected = health_resp.get("status") == "healthy"

        status_color = "#00CC66" if connected else "#CC0000"
        status_text = "Server Online" if connected else "Server Offline"

    except Exception:
        connected = False
        status_color = "#CC0000"
        status_text = "Server Offline"

    st.markdown(
        f"""
        <div style="margin-top: 16px; display: flex; align-items: center; gap: 10px;">
            <div style="width: 10px; height: 10px; border-radius: 50%; background-color: {status_color};"></div>
            <span style="font-size: 14px; color: #666;">{status_text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# -----------------------------------------------------
# TABS (Only Intelligence Dashboard)
# -----------------------------------------------------
tab1, = st.tabs(["📊 Intelligence Dashboard"])

# -----------------------------------------------------
# TAB 1 — INTELLIGENCE DASHBOARD
# -----------------------------------------------------
with tab1:
    st.header("📊 Generate Intelligence Dashboard")

    st.info(
        """
        The system automatically retrieves the most relevant context 
        and generates a complete insights report across all sections.
        """
    )

    # Company list
    try:
        companies_resp = requests.get(
            f"{MCP_BASE}/resource/ai50/companies", timeout=5
        ).json()
        company_names = companies_resp.get("companies", [])
        if not company_names:
            company_names = ["abridge", "openai", "anthropic"]
    except:
        company_names = ["abridge", "openai", "anthropic"]

    company_name = st.selectbox(
        "Company",
        company_names,
        key="corp_dashboard_company",
    )

    with st.expander("Advanced Settings"):
        top_k = st.slider(
            "Context Window Size",
            5,
            20,
            10,
            help="Controls how many context elements are retrieved during analysis.",
        )

    if st.button(
        "Generate Insights Dashboard",
        type="primary",
        use_container_width=True,
        key="btn_generate",
    ):
        progress_text = st.empty()
        progress_bar = st.progress(0)

        try:
            progress_text.text("Retrieving contextual data…")
            progress_bar.progress(40)

            resp = requests.post(
                f"{MCP_BASE}/tool/generate_unified_dashboard",
                json={
                    "company_id": company_name,
                    "top_k": top_k,
                    "prefer_structured": False,
                },
                timeout=120,
            )

            progress_bar.progress(90)
            data = resp.json()
            resp.raise_for_status()

            progress_bar.progress(100)
            progress_text.empty()

            if not data.get("success"):
                st.error(f"Dashboard generation failed: {data.get('error')}")
                st.stop()

            st.success("Dashboard generated successfully.")

            # Metrics
            data_sources = data.get("data_sources", {})
            generated_count = sum("rag" in v or "ai" in v for v in data_sources.values())
            missing_count = sum(v == "none" for v in data_sources.values())

            colA, colB, colC = st.columns(3)
            colA.metric("Generated Sections", generated_count)
            colB.metric("Sections w/ Insufficient Context", missing_count)
            colC.metric("Total Sections", 8)

            st.markdown("### Context Source Summary")
            cols = st.columns(4)
            for idx, (section, source) in enumerate(data_sources.items()):
                with cols[idx % 4]:
                    st.markdown(f"- **{section}** → `{source}`")

            st.divider()
            st.markdown("### Generated Insights Report")
            st.markdown(data["result"])

            st.divider()
            col_download1, col_download2 = st.columns(2)

            with col_download1:
                st.download_button(
                    "Download Report (Markdown)",
                    data["result"],
                    file_name=f"{company_name}_insights.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

            with col_download2:
                summary = f"""# Insights Summary
Company: {company_name}

Generated Sections: {generated_count}
Sections with Insufficient Context: {missing_count}
Context Window Size: {top_k}
"""
                st.download_button(
                    "Download Summary",
                    summary,
                    file_name=f"{company_name}_summary.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

        except Exception as e:
            progress_text.empty()
            progress_bar.empty()
            st.error(f"Error: {e}")

# -----------------------------------------------------
# SIDEBAR
# -----------------------------------------------------
st.sidebar.header("Utilities")

try:
    st.sidebar.success("Server Online")
except:
    st.sidebar.error("Server Offline")

st.sidebar.divider()
st.sidebar.caption("Project ORBIT — Corporate Edition")
