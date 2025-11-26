"""
Simple Streamlit UI for Dashboard Approvals
Option 1: External HITL - Approve/Reject pending dashboards
"""

import streamlit as st
import requests
import os
from pathlib import Path
from typing import List, Dict
import json

# Configuration
API_BASE = os.environ.get("MCP_SERVER_URL", "http://localhost:8100")
if not API_BASE.startswith("http"):
    API_BASE = f"http://{API_BASE}"

st.set_page_config(
    page_title="Dashboard Approvals",
    page_icon="✅",
    layout="wide"
)

st.title("📋 Dashboard Approval Center")
st.caption("Review and approve/reject dashboards with detected risks")

# Check API connection
try:
    health = requests.get(f"{API_BASE}/health", timeout=2)
    if health.status_code == 200:
        st.success("✅ Connected to MCP Server")
    else:
        st.error(f"❌ API returned status {health.status_code}")
        st.stop()
except Exception as e:
    st.error(f"❌ Cannot connect to API at {API_BASE}")
    st.info(f"Error: {e}")
    st.info("Make sure MCP server is running: `python src/server/mcp_server.py`")
    st.stop()

# Fetch pending approvals
try:
    response = requests.get(f"{API_BASE}/api/pending-approvals", timeout=5)
    if response.status_code == 200:
        data = response.json()
        pending_dashboards = data.get("pending", [])
    else:
        st.error(f"Failed to fetch approvals: {response.status_code}")
        pending_dashboards = []
except Exception as e:
    st.error(f"Error fetching approvals: {e}")
    pending_dashboards = []

if not pending_dashboards:
    st.info("🎉 No pending approvals! All dashboards are approved.")
    st.stop()

st.header(f"Pending Approvals ({len(pending_dashboards)})")

# Display each pending dashboard
for idx, dashboard in enumerate(pending_dashboards):
    company_id = dashboard.get("company_id", "unknown")
    run_id = dashboard.get("run_id", "unknown")
    evaluation_score = dashboard.get("evaluation_score", 0.0)
    risk_detected = dashboard.get("risk_detected", False)
    generated_at = dashboard.get("generated_at", "")
    preview = dashboard.get("preview", "")
    metadata = dashboard.get("metadata", {})
    
    with st.expander(f"🏢 {company_id.upper()} - Run: {run_id} | Score: {evaluation_score:.2f} | Risk: {'⚠️ YES' if risk_detected else '✅ NO'}", expanded=True):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Dashboard Preview")
            st.markdown(f"**Generated:** {generated_at}")
            st.markdown(f"**Evaluation Score:** {evaluation_score:.2f}")
            st.markdown(f"**Risk Detected:** {'⚠️ Yes' if risk_detected else '✅ No'}")
            
            if risk_detected and "risk_details" in metadata:
                st.markdown("**Risk Details:**")
                risk_details = metadata.get("risk_details", [])
                for risk in risk_details:
                    st.markdown(f"- **{risk.get('type', 'Unknown')}**: {risk.get('description', '')}")
            
            st.markdown("---")
            st.markdown("**Dashboard Content:**")
            st.text_area(
                "Preview",
                preview,
                height=300,
                key=f"preview_{idx}",
                disabled=True
            )
        
        with col2:
            st.subheader("Actions")
            
            # Approval form
            with st.form(key=f"approval_form_{idx}"):
                approved_by = st.text_input("Your Name", key=f"approved_by_{idx}", value="Admin")
                notes = st.text_area("Notes (optional)", key=f"notes_{idx}", height=100)
                
                col_approve, col_reject = st.columns(2)
                
                with col_approve:
                    approve_clicked = st.form_submit_button("✅ Approve", type="primary", use_container_width=True)
                
                with col_reject:
                    reject_clicked = st.form_submit_button("❌ Reject", use_container_width=True)
                
                if approve_clicked:
                    try:
                        approval_request = {
                            "company_id": company_id,
                            "run_id": run_id,
                            "action": "approve",
                            "approved_by": approved_by,
                            "notes": notes
                        }
                        response = requests.post(f"{API_BASE}/api/approve-dashboard", json=approval_request, timeout=10)
                        
                        if response.status_code == 200:
                            st.success(f"✅ Dashboard approved!")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"❌ Approval failed: {response.text}")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                
                if reject_clicked:
                    try:
                        approval_request = {
                            "company_id": company_id,
                            "run_id": run_id,
                            "action": "reject",
                            "approved_by": approved_by,
                            "notes": notes
                        }
                        response = requests.post(f"{API_BASE}/api/approve-dashboard", json=approval_request, timeout=10)
                        
                        if response.status_code == 200:
                            st.success(f"❌ Dashboard rejected")
                            st.rerun()
                        else:
                            st.error(f"❌ Rejection failed: {response.text}")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

# Refresh button
if st.button("🔄 Refresh"):
    st.rerun()

