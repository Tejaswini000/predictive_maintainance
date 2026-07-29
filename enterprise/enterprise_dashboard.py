"""
Enterprise Predictive Maintenance Dashboard

An enterprise-level Streamlit dashboard for managing an equipment fleet.
Extends the existing dashboard with multi-category, multi-machine features.
"""

import os
import io
import csv
import random
import re
import zipfile
import textwrap
from urllib.parse import quote
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from models import (
    MachineType, MachineStatus, MachineInfo, AlertSeverity,
    WorkOrderStatus, MaintenanceType, MACHINE_TYPE_SENSORS
)
from simulation import EnterpriseSimulator, FAILURE_CAUSE_LIBRARY, MAINTENANCE_ACTION_LIBRARY
from analytics import AnalyticsEngine, get_analytics_engine, TrendAnalyzer
from services import get_data_store, WorkOrderService, AlertService, infer_alert_cause_from_reason
from reports import ReportGenerator, get_report_generator
from enterprise_chatbot import EnterpriseCopilot
from llm_client import OpenRouterClient

# ==================== PAGE CONFIG ====================

st.set_page_config(
    page_title="🏭 Equipment Predictive Maintenance",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

    # Custom CSS for dark enterprise theme
st.markdown("""
<style>
    /* Analytics badge buttons - match original badge styling exactly */
    .stButton button[kind="analytics-badge"] {
        display: inline-flex !important;
        align-items: center !important;
        gap: 6px !important;
        padding: 6px 12px !important;
        border-radius: 20px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        color: #1F2937 !important;
        background: #F3F4F6 !important;
        border: 1px solid #E5E7EB !important;
        white-space: nowrap !important;
        min-height: 0 !important;
        height: auto !important;
        line-height: normal !important;
        width: auto !important;
        min-width: 0 !important;
        box-shadow: none !important;
        text-align: center !important;
        transition: none !important;
    }
    .stButton button[kind="analytics-badge"]:hover {
        border-color: #4da6ff !important;
        box-shadow: 0 2px 8px rgba(77, 166, 255, 0.2) !important;
        background: #F3F4F6 !important;
    }
    .stButton button[kind="analytics-badge"].healthy-badge { background: #DCFCE7 !important; color: #166534 !important; border-color: #BBF7D0 !important; }
    .stButton button[kind="analytics-badge"].warning-badge { background: #FEF3C7 !important; color: #92400E !important; border-color: #FDE68A !important; }
    .stButton button[kind="analytics-badge"].critical-badge { background: #FEE2E2 !important; color: #991B1B !important; border-color: #FECACA !important; }
    .stButton button[kind="analytics-badge"].health-badge { background: #FCE7F3 !important; color: #9D174D !important; border-color: #FBCFE8 !important; }
    .stButton button[kind="analytics-badge"].alerts-badge { background: #E0F2FE !important; color: #075985 !important; border-color: #BAE6FD !important; }
    .stButton button[kind="analytics-badge"].maint-badge { background: #EDE9FE !important; color: #5B21B6 !important; border-color: #DDD6FE !important; }
    /* Ensure button wrapper doesn't stretch */
    .stButton[kind="analytics-badge-wrapper"] { display: inline-flex !important; width: auto !important; }
    /* Analytics badge row columns - don't force full width */
    .analytics-badge-row .stButton { width: auto !important; display: inline-flex !important; }
    .analytics-badge-row .stButton button { width: auto !important; }
    /* Ensure analytics columns don't force button to stretch */
    div[data-testid="column"]:has(> .stButton button[kind="analytics-badge"]) {
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: 0 !important;
    }
    .main-header { font-size: 2.2rem; font-weight: 700; margin-bottom: 0; }
    .sub-header { font-size: 1.1rem; color: #888; margin-top: 0; }
    .metric-card { 
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px; padding: 18px; margin: 5px;
        border: 1px solid #2a2a4a;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .metric-value { font-size: 1.8rem; font-weight: 700; text-align: center; }
    .metric-label { font-size: 0.8rem; color: #aaa; text-align: center; margin-top: 4px; }
    .status-badge { 
        display: inline-block; padding: 3px 12px; border-radius: 12px;
        font-size: 0.8rem; font-weight: 600;
    }
    .critical-badge { background: #ff4444; color: white; }
    .warning-badge { background: #ffaa00; color: black; }
    .normal-badge { background: #44cc44; color: white; }
    .offline-badge { background: #888; color: white; }
    h3[style*="margin:6px 0 10px 0"] {
        color: #FFFFFF !important;
    }
    .machine-link-btn {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 500;
        color: #4da6ff !important;
        background: transparent;
        border: 1px solid #4da6ff;
        cursor: pointer;
        text-decoration: none;
        transition: all 0.2s;
    }
    .machine-link-btn:hover {
        background: #4da6ff;
        color: #ffffff !important;
    }
    /* Dashboard KPI cards: fixed visual dimensions while preserving button navigation */
    .st-key-dashboard_kpi_cards div[data-testid="column"] {
        min-width: 0 !important;
    }
    .st-key-dashboard_kpi_cards .stButton,
    .st-key-dashboard_kpi_cards div[data-testid="stButton"] {
        width: 100% !important;
        height: 112px !important;
        margin: 0 !important;
    }
    .st-key-dashboard_kpi_cards .stButton button,
    .st-key-dashboard_kpi_cards div[data-testid="stButton"] button,
    .stButton button[kpi-card="true"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%) !important;
        border-radius: 12px !important;
        padding: 14px 10px !important;
        border: 1px solid #2a2a4a !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3) !important;
        color: inherit !important;
        font-family: inherit !important;
        font-size: 1rem !important;
        line-height: 1.25 !important;
        text-align: center !important;
        transition: all 0.2s ease !important;
        min-height: 112px !important;
        height: 112px !important;
        width: 100% !important;
        min-width: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-sizing: border-box !important;
        overflow: hidden !important;
    }
    .st-key-dashboard_kpi_cards .stButton button:hover,
    .st-key-dashboard_kpi_cards div[data-testid="stButton"] button:hover,
    .stButton button[kpi-card="true"]:hover {
        border-color: #4da6ff !important;
        box-shadow: 0 4px 12px rgba(77, 166, 255, 0.3) !important;
    }
    .st-key-dashboard_kpi_cards .stButton button p,
    .st-key-dashboard_kpi_cards div[data-testid="stButton"] button p,
    .stButton button[kpi-card="true"] p {
        width: 100% !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        color: inherit !important;
        margin: 0 !important;
        line-height: 1.25 !important;
        white-space: pre-line !important;
        text-align: center !important;
        font-variant-numeric: tabular-nums !important;
        overflow-wrap: anywhere !important;
    }
    .st-key-dashboard_kpi_cards .st-key-kpi_cat,
    .st-key-dashboard_kpi_cards .st-key-kpi_cat button,
    .st-key-dashboard_kpi_cards .st-key-kpi_cat button *,
    .st-key-dashboard_kpi_cards .st-key-kpi_cat .stButton button,
    .st-key-dashboard_kpi_cards .st-key-kpi_cat .stButton button *,
    .st-key-dashboard_kpi_cards .st-key-kpi_cat div[data-testid="stButton"] button,
    .st-key-dashboard_kpi_cards .st-key-kpi_cat div[data-testid="stButton"] button *,
    .st-key-kpi_cat .stButton button,
    .st-key-kpi_cat .stButton button *,
    .st-key-kpi_cat .stButton button p,
    .st-key-kpi_cat div[data-testid="stButton"] button,
    .st-key-kpi_cat div[data-testid="stButton"] button *,
    .st-key-kpi_cat div[data-testid="stButton"] button p,
    .st-key-kpi_cat button,
    .st-key-kpi_cat button *,
    .st-key-kpi_cat h1,
    .st-key-kpi_cat h2,
    .st-key-kpi_cat h3,
    .st-key-kpi_cat h4,
    .st-key-kpi_cat p,
    .st-key-kpi_cat span,
    .st-key-kpi_cat div {
        color: #F4B400 !important;
        font-weight: 700;
    }
    .st-key-dashboard_kpi_cards .st-key-kpi_mach,
    .st-key-dashboard_kpi_cards .st-key-kpi_mach button,
    .st-key-dashboard_kpi_cards .st-key-kpi_mach button *,
    .st-key-dashboard_kpi_cards .st-key-kpi_mach .stButton button,
    .st-key-dashboard_kpi_cards .st-key-kpi_mach .stButton button *,
    .st-key-dashboard_kpi_cards .st-key-kpi_mach div[data-testid="stButton"] button,
    .st-key-dashboard_kpi_cards .st-key-kpi_mach div[data-testid="stButton"] button *,
    .st-key-kpi_mach .stButton button,
    .st-key-kpi_mach .stButton button *,
    .st-key-kpi_mach .stButton button p,
    .st-key-kpi_mach div[data-testid="stButton"] button,
    .st-key-kpi_mach div[data-testid="stButton"] button *,
    .st-key-kpi_mach div[data-testid="stButton"] button p,
    .st-key-kpi_mach button,
    .st-key-kpi_mach button *,
    .st-key-kpi_mach h1,
    .st-key-kpi_mach h2,
    .st-key-kpi_mach h3,
    .st-key-kpi_mach h4,
    .st-key-kpi_mach p,
    .st-key-kpi_mach span,
    .st-key-kpi_mach div {
        color: #B39DDB !important;
        font-weight: 700;
    }
    .st-key-dashboard_kpi_cards .st-key-kpi_heal,
    .st-key-dashboard_kpi_cards .st-key-kpi_heal button,
    .st-key-dashboard_kpi_cards .st-key-kpi_heal button *,
    .st-key-dashboard_kpi_cards .st-key-kpi_heal .stButton button,
    .st-key-dashboard_kpi_cards .st-key-kpi_heal .stButton button *,
    .st-key-dashboard_kpi_cards .st-key-kpi_heal div[data-testid="stButton"] button,
    .st-key-dashboard_kpi_cards .st-key-kpi_heal div[data-testid="stButton"] button *,
    .st-key-kpi_heal .stButton button,
    .st-key-kpi_heal .stButton button *,
    .st-key-kpi_heal .stButton button p,
    .st-key-kpi_heal div[data-testid="stButton"] button,
    .st-key-kpi_heal div[data-testid="stButton"] button *,
    .st-key-kpi_heal div[data-testid="stButton"] button p,
    .st-key-kpi_heal button,
    .st-key-kpi_heal button *,
    .st-key-kpi_heal h1,
    .st-key-kpi_heal h2,
    .st-key-kpi_heal h3,
    .st-key-kpi_heal h4,
    .st-key-kpi_heal p,
    .st-key-kpi_heal span,
    .st-key-kpi_heal div {
        color: #22C55E !important;
        font-weight: 700;
    }
    .st-key-dashboard_kpi_cards .st-key-kpi_warn,
    .st-key-dashboard_kpi_cards .st-key-kpi_warn button,
    .st-key-dashboard_kpi_cards .st-key-kpi_warn button *,
    .st-key-dashboard_kpi_cards .st-key-kpi_warn .stButton button,
    .st-key-dashboard_kpi_cards .st-key-kpi_warn .stButton button *,
    .st-key-dashboard_kpi_cards .st-key-kpi_warn div[data-testid="stButton"] button,
    .st-key-dashboard_kpi_cards .st-key-kpi_warn div[data-testid="stButton"] button *,
    .st-key-kpi_warn .stButton button,
    .st-key-kpi_warn .stButton button *,
    .st-key-kpi_warn .stButton button p,
    .st-key-kpi_warn div[data-testid="stButton"] button,
    .st-key-kpi_warn div[data-testid="stButton"] button *,
    .st-key-kpi_warn div[data-testid="stButton"] button p,
    .st-key-kpi_warn button,
    .st-key-kpi_warn button *,
    .st-key-kpi_warn h1,
    .st-key-kpi_warn h2,
    .st-key-kpi_warn h3,
    .st-key-kpi_warn h4,
    .st-key-kpi_warn p,
    .st-key-kpi_warn span,
    .st-key-kpi_warn div {
        color: #F59E0B !important;
        font-weight: 700;
    }
    .st-key-dashboard_kpi_cards .st-key-kpi_crit,
    .st-key-dashboard_kpi_cards .st-key-kpi_crit button,
    .st-key-dashboard_kpi_cards .st-key-kpi_crit button *,
    .st-key-dashboard_kpi_cards .st-key-kpi_crit .stButton button,
    .st-key-dashboard_kpi_cards .st-key-kpi_crit .stButton button *,
    .st-key-dashboard_kpi_cards .st-key-kpi_crit div[data-testid="stButton"] button,
    .st-key-dashboard_kpi_cards .st-key-kpi_crit div[data-testid="stButton"] button *,
    .st-key-kpi_crit .stButton button,
    .st-key-kpi_crit .stButton button *,
    .st-key-kpi_crit .stButton button p,
    .st-key-kpi_crit div[data-testid="stButton"] button,
    .st-key-kpi_crit div[data-testid="stButton"] button *,
    .st-key-kpi_crit div[data-testid="stButton"] button p,
    .st-key-kpi_crit button,
    .st-key-kpi_crit button *,
    .st-key-kpi_crit h1,
    .st-key-kpi_crit h2,
    .st-key-kpi_crit h3,
    .st-key-kpi_crit h4,
    .st-key-kpi_crit p,
    .st-key-kpi_crit span,
    .st-key-kpi_crit div {
        color: #EF4444 !important;
        font-weight: 700;
    }
    .st-key-dashboard_kpi_cards .st-key-kpi_avg,
    .st-key-dashboard_kpi_cards .st-key-kpi_avg button,
    .st-key-dashboard_kpi_cards .st-key-kpi_avg button *,
    .st-key-dashboard_kpi_cards .st-key-kpi_avg .stButton button,
    .st-key-dashboard_kpi_cards .st-key-kpi_avg .stButton button *,
    .st-key-dashboard_kpi_cards .st-key-kpi_avg div[data-testid="stButton"] button,
    .st-key-dashboard_kpi_cards .st-key-kpi_avg div[data-testid="stButton"] button *,
    .st-key-kpi_avg .stButton button,
    .st-key-kpi_avg .stButton button *,
    .st-key-kpi_avg .stButton button p,
    .st-key-kpi_avg div[data-testid="stButton"] button,
    .st-key-kpi_avg div[data-testid="stButton"] button *,
    .st-key-kpi_avg div[data-testid="stButton"] button p,
    .st-key-kpi_avg button,
    .st-key-kpi_avg button *,
    .st-key-kpi_avg h1,
    .st-key-kpi_avg h2,
    .st-key-kpi_avg h3,
    .st-key-kpi_avg h4,
    .st-key-kpi_avg p,
    .st-key-kpi_avg span,
    .st-key-kpi_avg div {
        color: #22C55E !important;
        font-weight: 700;
    }
    /* Category card styling for maintenance logs */
    .category-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 16px;
        border: 1px solid #2a2a4a;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        cursor: pointer;
        transition: all 0.2s ease;
        text-align: center;
        height: 100%;
    }
    .category-card:hover {
        border-color: #4da6ff;
        box-shadow: 0 4px 12px rgba(77, 166, 255, 0.3);
    }
    .category-card-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 8px;
    }
    .category-card-stat {
        font-size: 0.85rem;
        color: #aaa;
        margin: 3px 0;
    }
    .category-card-stat span {
        color: #ddd;
        font-weight: 500;
    }
    .category-card-cost {
        font-size: 0.9rem;
        color: #4da6ff;
        font-weight: 600;
        margin-top: 6px;
    }
    .machine-category-card h3,
    .machine-category-card .machine-category-name {
        color: #FFFFFF !important;
        font-weight: 700;
    }
    .machine-category-card .machine-category-count,
    .machine-category-card .machine-category-count strong {
        color: #FFFFFF !important;
        font-weight: 600;
    }
    .machine-category-card .machine-category-health {
        color: #FFFFFF !important;
        font-weight: 700;
    }
    .machine-category-card .machine-category-health strong,
    .machine-category-card .machine-category-healthy {
        color: #22C55E !important;
        font-weight: 700;
    }
    .machine-category-card .machine-category-warning {
        color: #F59E0B !important;
        font-weight: 700;
    }
    .machine-category-card .machine-category-critical {
        color: #EF4444 !important;
        font-weight: 700;
    }
    .summary-section {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 16px 20px;
        border: 1px solid #2a2a4a;
        margin: 10px 0;
    }
    .summary-stat { text-align: center; padding: 8px; }
    .summary-stat-value { font-size: 1.4rem; font-weight: 700; color: #fff; }
    .summary-stat-label { font-size: 0.8rem; color: #aaa; margin-top: 2px; }
    /* Machine list alignment */
    .machine-list-row {
        display: flex;
        align-items: center;
        padding: 6px 0;
        border-bottom: 1px solid #2a2a4a;
    }
    .machine-list-header {
        display: flex;
        align-items: center;
        padding: 6px 0;
        border-bottom: 2px solid #2a2a4a;
        color: #888;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .machine-list-checkbox {
        width: 40px;
        flex-shrink: 0;
        text-align: center;
    }
    .machine-list-id {
        flex: 2;
        padding-left: 8px;
    }
    .machine-list-logs {
        flex: 1.5;
        text-align: left;
    }
    .machine-list-cost {
        flex: 1.5;
        text-align: left;
    }
</style>
""", unsafe_allow_html=True)

# ==================== CONSTANTS ====================

STATUS_COLORS = {
    "CRITICAL": "#FF4444",
    "WARNING": "#FFAA00",
    "NORMAL": "#44CC44",
    "UNKNOWN": "#888888",
    "OFFLINE": "#666666",
    "MAINTENANCE": "#FF8800"
}

MACHINE_TYPE_COLORS = {
    "Refrigerator": "#3498db",
    "Washing Machine": "#2ecc71",
    "Air Conditioner": "#e74c3c",
    "Generator": "#f39c12",
    "Car Engine": "#9b59b6"
}


def format_recent_alert_id_for_display(alert_id: str) -> str:
    """Display dashboard alert IDs as ALT-<MachinePrefix>-<Number> without generated suffixes."""
    text = str(alert_id or "").strip()
    match = re.match(r"^(ALT-[A-Z]+-\d+)(?:-.*)?$", text)
    return match.group(1) if match else text.rstrip("-")


# ==================== NAVIGATION HELPER ====================

def navigate_to_machine(machine_id: str):
    """Navigate to a machine's detail page."""
    st.session_state.page = "machines"
    st.session_state.selected_machine = machine_id


def _handle_row_selection(df: pd.DataFrame, key: str):
    """Handle Streamlit dataframe row selection for machine navigation.
    
    Call this after st.dataframe() with on_select='rerun' and selection_mode='single-row'.
    The selected row's 'Machine ID' column value will trigger navigation to that machine.
    """
    selection = st.session_state.get(key)
    if selection and selection.get("selection") and selection["selection"].get("rows"):
        rows = selection["selection"]["rows"]
        if len(rows) > 0:
            row_idx = rows[0]
            if row_idx < len(df):
                machine_id = df.iloc[row_idx]["Machine ID"]
                navigate_to_machine(machine_id)
                st.rerun()

# ==================== SESSION STATE INIT ====================

def init_session_state():
    """Initialize session state variables."""
    if "page" not in st.session_state:
        st.session_state.page = "dashboard"
    if "selected_machine" not in st.session_state:
        st.session_state.selected_machine = None
    if "selected_factory" not in st.session_state:
        st.session_state.selected_factory = None
    if "selected_line" not in st.session_state:
        st.session_state.selected_line = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "data_refreshed" not in st.session_state:
        st.session_state.data_refreshed = False
    if "simulation_running" not in st.session_state:
        st.session_state.simulation_running = False
    if "simulation_refresh_counter" not in st.session_state:
        st.session_state.simulation_refresh_counter = 0
    # Maintenance Logs enhancement state
    if "maintenance_category" not in st.session_state:
        st.session_state.maintenance_category = None
    if "maintenance_selected_machine" not in st.session_state:
        st.session_state.maintenance_selected_machine = None
    if "maintenance_page" not in st.session_state:
        st.session_state.maintenance_page = "overview"
    if "analytics_category" not in st.session_state:
        st.session_state.analytics_category = None
    if "analytics_chip_filter" not in st.session_state:
        st.session_state.analytics_chip_filter = None
    if "_from_analytics" not in st.session_state:
        st.session_state._from_analytics = False
    if "_analytics_badge_target" not in st.session_state:
        st.session_state._analytics_badge_target = None
    if "_analytics_badge_source" not in st.session_state:
        st.session_state._analytics_badge_source = None
    if "_analytics_badge_route_key" not in st.session_state:
        st.session_state._analytics_badge_route_key = None
    if "data_consistency_checked" not in st.session_state:
        st.session_state.data_consistency_checked = False

init_session_state()

# ==================== GET SINGLETONS ====================

@st.cache_resource
def get_simulator():
    return EnterpriseSimulator()

@st.cache_resource
def get_analytics():
    return get_analytics_engine()

@st.cache_resource
def get_data():
    return get_data_store()

@st.cache_resource
def get_reports():
    return get_report_generator()

@st.cache_resource
def get_copilot():
    return EnterpriseCopilot()

simulator = get_simulator()
analytics = get_analytics()
data_store = get_data()
report_generator = get_reports()
copilot = get_copilot()


def ensure_data_consistency_once():
    """Repair stale derived records once so every page reads the same machine-state truth."""
    if st.session_state.get("data_consistency_checked"):
        return
    from services import get_sync_engine
    sync_engine = get_sync_engine()
    validation = sync_engine.validate_consistency()
    if not validation["consistent"]:
        sync_engine.auto_repair()
    st.session_state.data_consistency_checked = True


def return_to_analytics_from_chip():
    """Return from an Analytics chip destination to the Analytics summary page."""
    st.session_state.page = "analytics"
    st.session_state._from_analytics = False
    st.session_state._analytics_badge_source = None
    st.session_state._analytics_badge_target = None
    st.session_state._analytics_badge_route_key = None
    st.query_params.clear()
    st.rerun()


def came_from_analytics_chip(target_page: str) -> bool:
    """Check whether the current page was opened from an Analytics category chip."""
    return (
        st.session_state.get("_analytics_badge_source") == "analytics"
        and st.session_state.get("_analytics_badge_target") == target_page
    )

# ==================== SIDEBAR ====================

def render_sidebar():
    """Render enterprise sidebar navigation."""
    with st.sidebar:
        st.markdown("<h2 style='text-align: center;'>🏭 Enterprise PM</h2>", unsafe_allow_html=True)
        st.markdown("---")
        
        # Navigation
        st.markdown("### 📍 Navigation")
        
        pages = {
            "🏠 Dashboard": "dashboard",
            "⚙️ Machines": "machines",
            "📊 Analytics": "analytics",
            "🚨 Alerts": "alerts",
            "📋 Work Orders": "work_orders",
            "📈 Reports": "reports",
            "🤖 AI Copilot": "copilot",
            "📝 Maintenance Logs": "maintenance_logs"
        }
        
        for label, page_id in pages.items():
            if st.button(label, use_container_width=True,
                        type="primary" if st.session_state.page == page_id else "secondary"):
                st.session_state.page = page_id
                st.rerun()
        
        st.markdown("---")
        
        # Simulation Controls
        st.markdown("### 🎮 Simulation Controls")
        if st.button("🔄 Refresh Data", use_container_width=True):
            # CRITICAL: Invalidate ALL cached/generated data
            st.session_state.simulation_refresh_counter += 1
            from services import get_sync_engine
            # Purge DB history before regenerating
            db = __import__('enterprise.database', fromlist=['DatabaseManager']).DatabaseManager()
            # Run full health degradation simulation
            simulator.simulate_health_degradation()
            # Validate and repair any inconsistencies after simulation
            sync_engine = get_sync_engine()
            validation = sync_engine.validate_consistency()
            if not validation["consistent"]:
                sync_engine.auto_repair()
            st.session_state.data_refreshed = True
            st.rerun()
        
        if st.button("🎲 Generate Random Events", use_container_width=True):
            _generate_random_events()
            st.rerun()
        
        st.markdown("---")
        
        # Statistics Summary
        stats = simulator.get_stats()
        st.markdown("### 📊 Overview")
        st.markdown(f"""
        - **Categories**: {stats.get('total_categories', stats['total_factories'])}
        - **Machines**: {stats['total_machines']}
        - **Avg Health**: {stats['average_health']}%
        - **Critical**: {stats['critical_count']} 🛑
        - **Warning**: {stats['warning_count']} ⚠️
        - **Open Alerts**: {stats['open_alerts']}
        """)


# ==================== RANDOM EVENT GENERATION ====================

def _generate_random_events():
    """Generate random simulation events.
    
    Uses the simulator's health degradation + full synchronization engine
    to ensure all derived data (alerts, work orders, maintenance logs)
    remains consistent with machine health.
    """
    from services import get_sync_engine
    
    # Step 1: Run one full simulation cycle to get realistic health changes
    simulator.simulate_health_degradation()
    
    # Step 2: Force synchronize all data to ensure consistency
    sync_engine = get_sync_engine()
    sync_engine.synchronize_all()
    
    # Step 3: Validate and auto-repair any inconsistencies
    validation = sync_engine.validate_consistency()
    if not validation["consistent"]:
        sync_engine.auto_repair()


# ==================== DASHBOARD PAGE ====================

def render_dashboard():
    """Render the main enterprise dashboard with KPIs and charts."""
    st.markdown("<h1 class='main-header'>Equipment Fleet Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Real-time monitoring across all equipment categories</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    stats = simulator.get_stats()
    all_machines = simulator.get_all_machines()

    search_term = st.text_input("Global Search", placeholder="Search Equipment...")
    status_color = "#888"
    if search_term:
        needle = search_term.lower()
        matching_machines = [
            m for m in all_machines
            if needle in m.machine_id.lower()
            or needle in m.name.lower()
            or needle in m.machine_category.lower()
            or needle in m.manufacturer.lower()
            or needle in m.status.value.lower()
        ]

        st.markdown(f"**Search Results ({len(matching_machines)})**")
        result_cols = st.columns(3)
        for idx, machine in enumerate(matching_machines):
            with result_cols[idx % 3]:
                status_color = STATUS_COLORS.get(machine.status.value, "#888")
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                            border-radius: 12px; padding: 15px; margin: 8px 0;
                            border-left: 4px solid {status_color};'>
                    <h3 style='margin:0; color:#FFFFFF; font-weight:700;'><a href="?navigate={machine.machine_id}" style="color:#FFFFFF;text-decoration:none;font-weight:700;">{machine.machine_id}</a></h3>
                    <p style='margin:2px 0; color:#FFFFFF; font-weight:700;'>{machine.name}</p>
                    <p style='margin:2px 0; color: #ddd;'>{machine.manufacturer}</p>
                    <p style='margin:2px 0; font-size: 0.85rem; color: #888;'>
                        Health: {machine.health_score:.1f}% | Status: {machine.status.value}
                    </p>
                </div>
                """, unsafe_allow_html=True)

    # === KPI METRICS ===
    with st.container(key="dashboard_kpi_cards"):
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            categories_value = stats.get('total_categories', stats['total_factories'])
            categories_label = f'🏷️ Categories\n{categories_value}'
            if st.button(f"{categories_value}\n\n🏷️ Categories", key="kpi_cat", use_container_width=True):
                st.session_state.page = "kpi_categories"
                st.session_state.selected_factory = None
                st.session_state.selected_machine = None
                st.session_state.kpi_filter = None
                st.rerun()
        
        with col2:
            if st.button(f'{stats["total_machines"]}\n\n⚙️ Total Machines', key="kpi_mach", use_container_width=True):
                st.session_state.page = "kpi_machines"
                st.session_state.selected_factory = None
                st.session_state.selected_machine = None
                st.session_state.kpi_filter = "all"
                st.rerun()
        
        with col3:
            if st.button(f'{stats["healthy_count"]}\n\n✅ Healthy', key="kpi_heal", use_container_width=True):
                st.session_state.page = "kpi_healthy"
                st.session_state.selected_factory = None
                st.session_state.selected_machine = None
                st.session_state.kpi_filter = "healthy"
                st.rerun()
        
        with col4:
            if st.button(f'{stats["warning_count"]}\n\n⚠️ Warning', key="kpi_warn", use_container_width=True):
                st.session_state.page = "kpi_warning"
                st.session_state.selected_factory = None
                st.session_state.selected_machine = None
                st.session_state.kpi_filter = "warning"
                st.rerun()
        
        with col5:
            if st.button(f'{stats["critical_count"]}\n\n🔴 Critical', key="kpi_crit", use_container_width=True):
                st.session_state.page = "kpi_critical"
                st.session_state.selected_factory = None
                st.session_state.selected_machine = None
                st.session_state.kpi_filter = "critical"
                st.rerun()
        
        with col6:
            if st.button(f'{stats["average_health"]}%\n\n💚 Avg Health', key="kpi_avg", use_container_width=True):
                st.session_state.page = "analytics"
                st.session_state.kpi_filter = None
                st.rerun()
    
    st.markdown("---")
    
    # === CHARTS ROW 1 ===
    col1, col2 = st.columns(2)
    
    with col1:
        # Health Distribution Pie Chart
        status_counts = stats['status_distribution']
        fig = go.Figure(data=[go.Pie(
            labels=list(status_counts.keys()),
            values=list(status_counts.values()),
            marker_colors=[STATUS_COLORS.get(s, "#888") for s in status_counts.keys()],
            hole=0.4,
            textinfo='label+percent'
        )])
        fig.update_layout(
            title="Machine Status Distribution",
            height=350,
            margin=dict(t=40, b=10, l=10, r=10),
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#ccc'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Machine Type Distribution
        type_counts = stats['type_distribution']
        colors = [MACHINE_TYPE_COLORS.get(t, '#888') for t in type_counts.keys()]
        fig = go.Figure(data=[go.Bar(
            x=list(type_counts.keys()),
            y=list(type_counts.values()),
            marker_color=colors,
            text=list(type_counts.values()),
            textposition='auto'
        )])
        fig.update_layout(
            title="Machine Type Distribution",
            height=350,
            xaxis_title="Machine Type",
            yaxis_title="Count",
            margin=dict(t=40, b=50),
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#ccc',
            xaxis={'tickangle': -20}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # === CATEGORY OVERVIEW ===
    st.subheader("🏷️ Equipment Category Overview")
    
    category_data = []
    for fid, finfo in simulator.get_all_factories().items():
        f_machines = simulator.get_factory_machines(fid)
        f_critical = sum(1 for m in f_machines if m.status == MachineStatus.CRITICAL)
        f_warning = sum(1 for m in f_machines if m.status == MachineStatus.WARNING)
        f_healthy = sum(1 for m in f_machines if m.status == MachineStatus.NORMAL)
        f_avg_health = sum(m.health_score for m in f_machines) / len(f_machines) if f_machines else 0
        
        category_data.append({
            "Category": finfo.get("name", fid),
            "ID": fid,
            "Units": len(f_machines),
            "Healthy": f_healthy,
            "Warning": f_warning,
            "Critical": f_critical,
            "Avg Health": f"{f_avg_health:.1f}%"
        })
    
    if category_data:
        df = pd.DataFrame(category_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # === ALERTS OVERVIEW ===
    st.subheader("🚨 Recent Alerts")
    open_alerts = data_store.alert_service.get_open_alerts()
    
    # Sort by timestamp descending (newest first), then take top 10
    recent_alerts = sorted(open_alerts, key=lambda a: a.timestamp, reverse=True)[:10]
    
    # Debug check: verify recent_alerts are the latest 10 from the same collection
    total_open = len(open_alerts)
    displayed = len(recent_alerts)
    if total_open > 0 and displayed > 0:
        sorted_open = sorted(open_alerts, key=lambda a: a.timestamp, reverse=True)[:10]
        assert recent_alerts == sorted_open, (
            f"BUG: recent_alerts mismatch! total_open={total_open}, displayed={displayed}"
        )
    
    if open_alerts:
        st.caption(f"Showing latest {min(10, len(open_alerts))} alerts")
        alert_rows = []
        for a in recent_alerts:
            condition = a.severity.value
            condition_color = {"CRITICAL": "#FF4444", "WARNING": "#FFAA00", "INFO": "#4488FF"}.get(condition, "#888")
            alert_rows.append({
                "Machine ID": a.machine_id,
                "Alert ID": format_recent_alert_id_for_display(a.alert_id),
                "Description": a.reason[:60],
                "Date": a.timestamp.strftime('%Y-%m-%d %H:%M'),
                "Condition": condition,
                "__condition_color": condition_color,
                "Status": a.status
            })
        if alert_rows:
            df_alerts = pd.DataFrame(alert_rows)
            df_display = df_alerts.drop(columns=["__condition_color"], errors="ignore")
            sel = st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "Machine ID": st.column_config.Column("Machine ID", width="small"),
                    "Alert ID": st.column_config.Column("Alert ID", width=max(150, int(df_display["Alert ID"].astype(str).map(len).max() * 10 + 50))),
                    "Description": st.column_config.Column("Description", width="large"),
                    "Date": st.column_config.Column("Date", width=150),
                    "Condition": st.column_config.Column("Condition", width="small"),
                    "Status": st.column_config.Column("Status", width="small"),
                }
            )
            if len(sel.selection.rows) > 0:
                row_idx = sel.selection.rows[0]
                machine_id = df_display.iloc[row_idx]["Machine ID"]
                navigate_to_machine(machine_id)
                st.rerun()
    else:
        st.info("✅ No open alerts. All systems normal.")
    
    # === MACHINE HEALTH TABLE ===
    st.markdown("---")
    st.subheader("⚙️ All Machines Health Status")
    
    machine_rows = []
    for m in sorted(all_machines, key=lambda x: x.health_score):
        machine_rows.append({
            "Machine ID": m.machine_id,
            "Category": m.machine_type.value,
            "Health Score": f"{m.health_score:.1f}%",
            "Failure Probability": f"{m.failure_probability*100:.1f}%",
            "Condition": m.status.value
        })
    
    if machine_rows:
        df_machines = pd.DataFrame(machine_rows)
        sel = st.dataframe(
            df_machines,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Machine ID": st.column_config.Column("Machine ID", width="small"),
                "Category": st.column_config.Column("Category", width="medium"),
                "Health Score": st.column_config.Column("Health Score", width="small"),
                "Failure Probability": st.column_config.Column("Failure Probability", width="small"),
                "Condition": st.column_config.Column("Condition", width="small"),
            }
        )
        if len(sel.selection.rows) > 0:
            row_idx = sel.selection.rows[0]
            machine_id = df_machines.iloc[row_idx]["Machine ID"]
            navigate_to_machine(machine_id)
            st.rerun()


# ==================== MACHINES PAGE ====================

def get_category_icon(category_name: str) -> str:
    """Return an icon for the active machine categories."""
    icons = {
        "Refrigerator": "🧊",
        "Washing Machine": "🧺",
        "Air Conditioner": "❄️",
        "Generator": "⚡",
        "Car Engine": "🚗",
    }
    return icons.get(category_name, "⚙️")


def get_health_bucket(machine: MachineInfo) -> str:
    """Map health score to the UI filter buckets."""
    if machine.health_score >= 70:
        return "Healthy"
    if machine.health_score >= 40:
        return "Warning"
    return "Critical"


def render_machine_category_cards():
    """Render the five machine categories as clickable cards."""
    st.markdown("### Equipment Categories")
    factories = simulator.get_all_factories()

    cols = st.columns(3)
    for idx, (factory_id, factory_info) in enumerate(factories.items()):
        machines = simulator.get_factory_machines(factory_id)
        category_name = factory_info.get("name", factory_id)
        avg_health = sum(m.health_score for m in machines) / len(machines) if machines else 0
        healthy = sum(1 for m in machines if m.status == MachineStatus.NORMAL)
        warning = sum(1 for m in machines if m.status == MachineStatus.WARNING)
        critical = sum(1 for m in machines if m.status == MachineStatus.CRITICAL)

        with cols[idx % 3]:
            st.markdown(f"""
            <div class='machine-category-card' style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                        border-radius: 12px; padding: 18px; margin: 8px 0;
                        border: 1px solid #2a2a4a; min-height: 190px;'>
                <div style='font-size:2rem;'>{get_category_icon(category_name)}</div>
                <h3 class='machine-category-name' style='margin:6px 0 10px 0;'>{category_name}</h3>
                <p class='machine-category-count' style='margin:3px 0; color:#ddd;'><strong>{len(machines)}</strong> Machines</p>
                <p class='machine-category-health' style='margin:3px 0; color:#ddd;'>Average Health <strong>{avg_health:.1f}%</strong></p>
                <p style='margin:10px 0 0 0; font-size:0.85rem; color:#aaa;'>
                    <span class='machine-category-healthy'>Healthy {healthy}</span> | <span class='machine-category-warning'>Warning {warning}</span> | <span class='machine-category-critical'>Critical {critical}</span>
                </p>
            </div>
            """, unsafe_allow_html=True)

            if st.button("Open Category", key=f"open_category_{factory_id}", use_container_width=True):
                st.session_state.selected_factory = factory_id
                st.session_state.selected_machine = None
                st.rerun()


def render_machine_category_detail(factory_id: str):
    """Render a single category machine list with search, filters, and sorting."""
    factory_info = simulator.get_all_factories().get(factory_id)
    if not factory_info:
        st.session_state.selected_factory = None
        st.error("Selected category was not found.")
        return

    category_name = factory_info.get("name", factory_id)
    if st.button("← Back to Categories"):
        st.session_state.selected_factory = None
        st.session_state.selected_machine = None
        st.rerun()

    st.markdown(f"## {get_category_icon(category_name)} {category_name}")

    search_term = st.text_input(
        "Search",
        placeholder="Search Machine..."
    )

    machines = simulator.get_factory_machines(factory_id)
    manufacturers = sorted({m.manufacturer for m in machines})

    col1, col2, col3, col4 = st.columns(4)
    selected_manufacturer = col1.selectbox("Manufacturer", ["All"] + manufacturers)
    selected_status = col2.selectbox("Status", ["All", "CRITICAL", "WARNING", "NORMAL", "OFFLINE"])
    selected_health = col3.selectbox("Health", ["All", "Healthy", "Warning", "Critical"])
    sort_by = col4.selectbox("Sort by", ["Machine Name", "Health Score", "Failure Probability"])

    if search_term:
        needle = search_term.lower()
        machines = [
            m for m in machines
            if needle in m.machine_id.lower()
            or needle in m.name.lower()
            or needle in m.manufacturer.lower()
            or needle in m.status.value.lower()
        ]
    if selected_manufacturer != "All":
        machines = [m for m in machines if m.manufacturer == selected_manufacturer]
    if selected_status != "All":
        machines = [m for m in machines if m.status.value == selected_status]
    if selected_health != "All":
        machines = [m for m in machines if get_health_bucket(m) == selected_health]

    if sort_by == "Machine Name":
        machines = sorted(machines, key=lambda m: m.name)
    elif sort_by == "Health Score":
        machines = sorted(machines, key=lambda m: m.health_score, reverse=True)
    else:
        machines = sorted(machines, key=lambda m: m.failure_probability, reverse=True)

    st.markdown("---")
    st.markdown(f"**Showing {len(machines)} {category_name} machines**")

    cols = st.columns(3)
    for idx, machine in enumerate(machines):
        with cols[idx % 3]:
            status_color = STATUS_COLORS.get(machine.status.value, "#888")
            last_maintenance = machine.last_maintenance_date.strftime("%Y-%m-%d") if machine.last_maintenance_date else "N/A"
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                        border-radius: 12px; padding: 15px; margin: 8px 0;
                        border-left: 4px solid {status_color};'>
                <h3 style='margin:0; color:#FFFFFF; font-weight:700;'><a href="?navigate={machine.machine_id}" style="color:#FFFFFF;text-decoration:none;font-weight:700;">{machine.machine_id}</a></h3>
                <p style='margin:2px 0; color:#FFFFFF; font-weight:700;'>{machine.name}</p>
                <p style='margin:2px 0; color: #ddd;'>{machine.manufacturer}</p>
                <p style='margin:6px 0;'>
                    <span style='background:{status_color}; color:white; padding:3px 10px; border-radius:12px; font-size:0.8rem; font-weight:700;'>{machine.status.value}</span>
                </p>
                <p style='margin:2px 0; font-size: 0.85rem; color: #888;'>
                    Health Score: <strong>{machine.health_score:.1f}%</strong><br>
                    Failure Probability: <strong>{machine.failure_probability*100:.1f}%</strong><br>
                    Last Maintenance: <strong>{last_maintenance}</strong>
                </p>
            </div>
            """, unsafe_allow_html=True)

            if st.button("View Details", key=f"machine_detail_{machine.machine_id}", use_container_width=True):
                st.session_state.selected_machine = machine.machine_id
                st.rerun()


def render_machines():
    """Render the machines overview and detail page."""
    if st.session_state.selected_machine:
        render_machine_detail(st.session_state.selected_machine)
        return

    if st.session_state.selected_factory:
        st.markdown("<h1 class='main-header'>Machines</h1>", unsafe_allow_html=True)
        render_machine_category_detail(st.session_state.selected_factory)
        return

    st.markdown("<h1 class='main-header'>Machines</h1>", unsafe_allow_html=True)
    render_machine_category_cards()
    return

def render_machine_detail(machine_id: str):
    """Render detailed view for a specific machine."""
    machine = simulator.get_machine(machine_id)
    if not machine:
        st.error(f"Machine {machine_id} not found.")
        return

    if st.button("← Back to Categories", key=f"back_to_categories_{machine_id}"):
        st.session_state.selected_machine = None
        st.session_state.selected_factory = None
        st.rerun()
    
    st.markdown("---")
    st.markdown(f"## 🔧 {machine.name} ({machine.machine_id})")
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Back to Categories"):
            st.session_state.selected_machine = None
            st.rerun()
    
    # Machine Info Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📋 Info", "📊 Sensors", "🔮 Prediction", 
        "📝 Work Orders", "📜 Maintenance Logs", "🤖 AI Chat"
    ])
    
    with tab1:
        render_machine_info_tab(machine)
    
    with tab2:
        render_sensors_tab(machine)
    
    with tab3:
        render_prediction_tab(machine)
    
    with tab4:
        render_work_orders_tab(machine)
    
    with tab5:
        render_maintenance_logs_tab(machine)
    
    with tab6:
        render_ai_chat_tab(machine)

    st.markdown("---")
    render_machine_alerts_tab(machine)


def render_machine_info_tab(machine: MachineInfo):
    """Render machine information."""
    analytics_data = analytics.get_machine_analytics(machine.machine_id)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### ℹ️ Machine Information")
        info_data = {
            "Machine ID": machine.machine_id,
            "Manufacturer": machine.manufacturer,
            "Category": machine.machine_category,
            "Model": machine.model_number,
            "Installation Date": machine.installation_date.strftime("%Y-%m-%d") if machine.installation_date else "N/A",
            "Purchase Date": machine.purchase_date.strftime("%Y-%m-%d") if machine.purchase_date else "N/A",
        }
        
        for label, value in info_data.items():
            st.markdown(f"**{label}**: {value}")
    
    with col2:
        st.markdown("### 📊 Performance KPIs")
        # Derive Last Maintenance from the NEWEST CLOSED alert in Alert History
        # This ensures KPI always matches the second row in the Alert History table
        alerts = data_store.alert_service.get_alerts_by_machine(machine.machine_id)
        closed_alerts = [a for a in alerts if a.status == "Closed"]
        if closed_alerts:
            # Sort by timestamp descending, take the newest closed alert
            closed_alerts.sort(key=lambda a: a.timestamp, reverse=True)
            last_maint_date = closed_alerts[0].timestamp.strftime("%Y-%m-%d")
        else:
            last_maint_date = "N/A"
        
        kpi_data = {
            "Status": f"🟢 {machine.status.value}" if machine.status == MachineStatus.NORMAL else (
                      f"🟡 {machine.status.value}" if machine.status == MachineStatus.WARNING else
                      f"🔴 {machine.status.value}"),
            "Health Score": f"{machine.health_score}%",
            "Failure Probability": f"{machine.failure_probability*100:.2f}%",
            "Last Maintenance": last_maint_date,
            "Next Maintenance": machine.next_maintenance_date.strftime("%Y-%m-%d") if machine.next_maintenance_date else "N/A"
        }
        
        for label, value in kpi_data.items():
            st.markdown(f"**{label}**: {value}")


def render_sensors_tab(machine: MachineInfo):
    """Render sensor data for a machine."""
    st.markdown("### 📊 Current Sensor Values")
    
    # Get latest readings
    latest_readings = simulator.get_latest_readings(machine.machine_id)
    
    if not latest_readings:
        st.info("Generating sensor data...")
        latest_readings = simulator.get_latest_readings(machine.machine_id)
    
    # Display gauges
    cols = st.columns(3)
    for idx, (sensor_name, reading) in enumerate(latest_readings.items()):
        with cols[idx % 3]:
            value = reading["sensor_value"]
            status = reading["status"]
            unit = reading.get("unit", "")
            
            sensor_config = simulator._get_machine_reading_config(sensor_name) if hasattr(simulator, '_get_machine_reading_config') else {"min": 0, "max": 100}
            
            # Gauge chart
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=value,
                title={'text': f"{sensor_name.replace('_', ' ').title()} ({unit})"},
                delta={'reference': 50},
                gauge={
                    'axis': {'range': [None, None]},
                    'bar': {'color': "#44CC44" if status == "normal" else "#FFAA00" if status == "warning" else "#FF4444"},
                    'steps': [
                        {'range': [0, 33], 'color': "#44CC44"},
                        {'range': [33, 66], 'color': "#FFAA00"},
                        {'range': [66, 100], 'color': "#FF4444"}
                    ]
                }
            ))
            fig.update_layout(height=250, margin=dict(t=50, b=10, l=10, r=10),
                            paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc')
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Historical sensor charts
    st.markdown("### 📈 Historical Sensor Trends")
    
    # Generate historical data
    historical = simulator.generate_historical_data(machine.machine_id, hours=24, readings_per_hour=6)
    
    for sensor_name, readings in historical.items():
        if readings:
            df = pd.DataFrame(readings)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            fig = px.line(
                df, x='timestamp', y='sensor_value',
                title=f"{sensor_name.replace('_', ' ').title()} Trend (24h)",
                color_discrete_sequence=["#3498db"]
            )
            fig.update_layout(
                height=250, margin=dict(t=30, b=10),
                paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc',
                xaxis_title="Time", yaxis_title=readings[0].get('unit', '')
            )
            
            # Add status color bands
            sensor_config = MACHINE_TYPE_SENSORS.get(machine.machine_type, {}).get(sensor_name, {})
            if sensor_config:
                fig.add_hline(y=sensor_config.get('min', 0), line_dash="dash", line_color="#44CC44")
                fig.add_hline(y=sensor_config.get('max', 100), line_dash="dash", line_color="#FF4444")
            
            st.plotly_chart(fig, use_container_width=True)


def render_prediction_tab(machine: MachineInfo):
    """Render AI prediction details."""
    st.markdown("### 🔮 AI Prediction")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Health Score", f"{machine.health_score}%", 
                f"{machine.health_score - 70:+.1f}%" if machine.health_score != 70 else None)
    col2.metric("Failure Probability", f"{machine.failure_probability*100:.2f}%")
    col3.metric("Prediction Accuracy", f"{analytics.calculate_prediction_accuracy(machine.machine_id)}%")
    
    # Health gauge
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=machine.health_score,
        title={'text': "Machine Health"},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': "#44CC44" if machine.health_score > 70 else "#FFAA00" if machine.health_score > 40 else "#FF4444"},
            'steps': [
                {'range': [0, 40], 'color': "#FF4444"},
                {'range': [40, 70], 'color': "#FFAA00"},
                {'range': [70, 100], 'color': "#44CC44"}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': machine.health_score
            }
        }
    ))
    fig.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc')
    st.plotly_chart(fig, use_container_width=True)
    
    # Recommendations
    st.markdown("### 💡 Recommendations")
    
    if machine.status == MachineStatus.CRITICAL:
        st.error("🚨 **IMMEDIATE ACTION REQUIRED**")
        st.markdown(f"""
        - Health score critically low ({machine.health_score}%)
        - Failure probability high ({machine.failure_probability*100:.1f}%)
        - **Immediate inspection and maintenance required**
        - Consider emergency shutdown
        """)
    elif machine.status == MachineStatus.WARNING:
        st.warning("⚠️ **Attention Required - Schedule Maintenance**")
        st.markdown(f"""
        - Health score below optimal ({machine.health_score}%)
        - Schedule preventive maintenance within 48 hours
        - Monitor sensor readings closely
        - Check for any abnormal patterns
        """)
    else:
        st.success("✅ **Machine operating normally**")
        st.markdown(f"""
        - Health score is good ({machine.health_score}%)
        - Continue routine monitoring
        - Next maintenance scheduled: {machine.next_maintenance_date.strftime('%Y-%m-%d') if machine.next_maintenance_date else 'Not set'}
        """)


def render_work_orders_tab(machine: MachineInfo):
    """Render active work orders for a machine (Open / In Progress only)."""
    st.markdown("### 📋 Active Work Orders")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        work_orders = data_store.work_order_service.get_work_orders_by_machine(machine.machine_id)
        active_work_orders = [wo for wo in work_orders if wo.status.value in ("Open", "In Progress")]
        
        if not active_work_orders:
            if machine.status == MachineStatus.NORMAL:
                st.success("✅ No active work orders. Machine is normal.")
            else:
                st.info("No active work orders for this machine.")
        else:
            wo_data = []
            for wo in active_work_orders:
                wo_data.append({
                    "ID": wo.work_order_id,
                    "Title": wo.title,
                    "Status": wo.status.value,
                    "Priority": wo.priority,
                    "Technician": wo.assigned_technician,
                    "Scheduled": wo.scheduled_date.strftime("%Y-%m-%d") if wo.scheduled_date else "N/A",
                    "Created": wo.created_date.strftime("%Y-%m-%d")
                })
            df = pd.DataFrame(wo_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
    
    with col2:
        if st.button("➕ Create Work Order", use_container_width=True):
            wo = data_store.work_order_service.create_work_order(
                machine_id=machine.machine_id,
                title=f"Maintenance for {machine.name}",
                description=f"Auto-generated work order for {machine.name} ({machine.machine_id})",
                priority="Medium"
            )
            st.success(f"Work Order {wo.work_order_id} created!")
            st.rerun()
    
    st.markdown("---")
    st.markdown("### 📊 Active Work Order Summary")
    
    summary = data_store.work_order_service.get_work_order_summary()
    col1, col2 = st.columns(2)
    col1.metric("Open", summary.get("Open", 0))
    col2.metric("In Progress", summary.get("In Progress", 0))


def _generate_maintenance_history(machine: MachineInfo) -> List[Dict[str, str]]:
    """Generate a logically consistent maintenance history for a machine.
    
    Requirements:
    1. First row = Current machine condition (today's date, Status = Open)
    2. Newest Closed record's date MUST match Last Maintenance KPI
    3. All dates sorted newest → oldest
    4. Only today's row has Status = Open
    5. Cause/Action pairs are matching and machine-type-specific
    6. No dates before purchase_date
    7. Realistic maintenance lifecycle timeline
    
    Timeline:
      Purchase Date
      ↓
      First Maintenance (Closed)
      ↓
      Second Maintenance (Closed)  
      ↓
      Third Maintenance (Closed)
      ↓
      Latest Completed Maintenance (Closed) = Last Maintenance
      ↓
      Current Condition (Today, Open)
    
    Date order (descending):
      Today (Open)
      ↓
      Latest Closed Maintenance
      ↓
      Previous Maintenance
      ↓
      Older Maintenance
      ↓
      First Maintenance
    """
    from datetime import timedelta
    
    today = datetime.now()
    
    # Determine anchor date (purchase_date or installation_date)
    anchor_date = machine.purchase_date or machine.installation_date
    if not anchor_date:
        anchor_date = today - timedelta(days=365 * 3)  # Default: 3 years ago
    
    # Ensure anchor_date is not in the future
    if anchor_date > today:
        anchor_date = today - timedelta(days=365 * 3)
    
    # Get the authoritative last maintenance date from the machine
    last_maint = machine.last_maintenance_date
    
    # Calculate months since purchase for history depth
    months_since_purchase = max(1, int((today - anchor_date).days / 30))
    
    # Generate 2-4 completed maintenance records (not counting today's Open record)
    num_completed = min(4, max(2, months_since_purchase // 6))
    
    # Get machine-type-specific failure causes and actions
    machine_causes = list(FAILURE_CAUSE_LIBRARY.get(machine.machine_type, []))
    if not machine_causes:
        # Fallback generic causes
        machine_causes = ["Performance drift", "Component wear", "System degradation", "Sensor anomaly"]
    
    records = []
    
    # === Generate completed (Closed) maintenance records ===
    if last_maint and last_maint <= today:
        # Use actual last_maintenance_date for the newest closed record
        completed_dates = [last_maint]
        
        # Generate additional closed records between anchor_date and last_maint
        available_span = (last_maint - anchor_date).days
        if available_span > 60 and num_completed > 1:
            # Distribute additional records across the span
            for i in range(num_completed - 1):
                # Spread dates from after anchor_date to before last_maint
                ratio = (i + 1) / num_completed
                offset_days = int(available_span * ratio * 0.85)  # Leave gap after each
                if offset_days < 30:
                    offset_days = 30 * (i + 1)
                rec_date = anchor_date + timedelta(days=offset_days)
                # Add randomness
                rec_date += timedelta(days=random.randint(-5, 5))
                # Clamp
                if rec_date < anchor_date + timedelta(days=30):
                    rec_date = anchor_date + timedelta(days=30 * (i + 1))
                if rec_date >= last_maint - timedelta(days=1):
                    rec_date = last_maint - timedelta(days=random.randint(30, 90))
                completed_dates.append(rec_date)
        elif num_completed > 1:
            # Not much span, generate dates evenly
            for i in range(num_completed - 1):
                days_back = random.randint(90 * (i + 1), 180 * (i + 1))
                rec_date = last_maint - timedelta(days=days_back)
                if rec_date < anchor_date:
                    rec_date = anchor_date + timedelta(days=30 * (i + 1))
                completed_dates.append(rec_date)
    else:
        # No last maintenance date - generate all completed records from anchor
        total_days = max(365, (today - anchor_date).days)
        completed_dates = []
        for i in range(num_completed):
            # Spread evenly with randomness
            ratio = (i + 1) / (num_completed + 1)
            offset_days = int(total_days * ratio) + random.randint(-15, 15)
            offset_days = max(30, min(total_days - 1, offset_days))
            rec_date = anchor_date + timedelta(days=offset_days)
            if rec_date >= today:
                rec_date = today - timedelta(days=random.randint(30, 90))
            completed_dates.append(rec_date)
        
        # Ensure the most recent completed date would be the "last maintenance"
        if completed_dates:
            completed_dates.sort(reverse=True)
    
    # Ensure no duplicate or out-of-order dates
    # Allow dates equal to today (last maintenance can be today) - they become Closed records
    completed_dates = sorted(set(d for d in completed_dates if d <= today), reverse=True)
    
    # Limit to num_completed
    completed_dates = completed_dates[:num_completed]
    
    # Assign cause/action pairs to each completed record
    used_causes = []
    for i, rec_date in enumerate(completed_dates):
        # Pick a cause - avoid repeating recently used ones
        available = [c for c in machine_causes if c not in used_causes]
        if not available:
            available = machine_causes
        cause = random.choice(available)
        used_causes.append(cause)
        
        # Get matching action from library, or generate generic one
        action = MAINTENANCE_ACTION_LIBRARY.get(cause, "Routine maintenance completed")
        
        # Determine condition based on position in lifecycle
        if i == len(completed_dates) - 1:
            # Oldest record - likely NORMAL or early WARNING
            condition = random.choice(["NORMAL", "WARNING"])
        elif i == 0:
            # Newest closed - most recent completed maintenance
            condition = "WARNING"
        else:
            condition = random.choice(["WARNING", "CRITICAL"])
        
        records.append({
            "Date": rec_date.strftime("%Y-%m-%d"),
            "Condition": condition,
            "Cause": cause,
            "Prevention / Action": action,
            "Status": "Closed"
        })
    
    # === Add current condition record (today, Status = Open) ===
    current_status = machine.status.value  # NORMAL, WARNING, or CRITICAL
    
    # Build cause/action for current condition based on machine's actual cause
    current_cause = machine.cause or ""
    
    # If machine has no cause or it's generic, use machine type's cause library
    if not current_cause or current_cause.lower().startswith("sensor readings"):
        available_causes = [c for c in machine_causes if c not in used_causes]
        if not available_causes:
            available_causes = machine_causes
        current_cause = random.choice(available_causes)
    
    current_action = MAINTENANCE_ACTION_LIBRARY.get(current_cause, "Scheduled maintenance performed")
    
    records.append({
        "Date": today.strftime("%Y-%m-%d"),
        "Condition": current_status,
        "Cause": current_cause,
        "Prevention / Action": current_action,
        "Status": "Open"
    })
    
    # Sort: Open record (today) always first, then Closed records sorted newest → oldest
    open_records = [r for r in records if r["Status"] == "Open"]
    closed_records = [r for r in records if r["Status"] == "Closed"]
    closed_records.sort(key=lambda r: r["Date"], reverse=True)
    
    return open_records + closed_records


def render_maintenance_logs_tab(machine: MachineInfo):
    """Render maintenance logs for a machine."""
    st.markdown("### 📜 Maintenance History")
    
    alerts = data_store.alert_service.get_alerts_by_machine(machine.machine_id)
    maintenance_logs = [
        log for log in data_store.maintenance_log_service.get_logs_by_machine(machine.machine_id)
        if not log.category or log.category == machine.machine_category
    ]
    work_orders = data_store.work_order_service.get_work_orders_by_machine(
        machine.machine_id,
        include_completed=True
    )

    def _alert_reason_to_cause(reason: str) -> str:
        inferred_cause = infer_alert_cause_from_reason(reason)
        if inferred_cause != "Component degradation over time":
            return inferred_cause
        reason_text = (reason or "").lower()
        if " detected on " in reason_text:
            return reason.rsplit(" detected on ", 1)[0].strip()
        marker = f" on {machine.machine_id}".lower()
        marker_index = reason_text.rfind(marker)
        if marker_index >= 0:
            return reason[:marker_index].strip()
        return (reason or "").strip()

    def _stable_index(*parts) -> int:
        return sum(ord(ch) for ch in "|".join(str(part or "") for part in parts))

    def _matching_work_order_for_alert(alert):
        for wo in work_orders:
            if wo.alert_id == alert.alert_id:
                return wo
        return None

    def _matching_log_for_alert(alert):
        related_work_order_ids = {
            wo.work_order_id for wo in work_orders
            if wo.alert_id == alert.alert_id
        }
        for log in maintenance_logs:
            if log.work_order_id in related_work_order_ids:
                return log
            if alert.alert_id and alert.alert_id in (log.description or ""):
                return log

        date_matches = [
            log for log in maintenance_logs
            if abs((log.maintenance_date.date() - alert.timestamp.date()).days) <= 7
        ]
        if date_matches:
            return min(
                date_matches,
                key=lambda log: abs((log.maintenance_date - alert.timestamp).total_seconds())
            )

        cause = _alert_reason_to_cause(alert.reason).lower()
        cause_matches = [
            log for log in maintenance_logs
            if cause
            and (
                cause in (log.issue or "").lower()
                or cause in (log.description or "").lower()
                or cause in (log.action_taken or "").lower()
            )
        ]
        candidates = cause_matches or maintenance_logs
        if not candidates:
            return None

        return min(
            candidates,
            key=lambda log: abs((log.maintenance_date - alert.timestamp).total_seconds())
        )

    def _maintenance_type_for_event(alert, log, work_order) -> str:
        if log and log.maintenance_type:
            return log.maintenance_type.value
        if work_order and work_order.maintenance_type:
            return work_order.maintenance_type

        cause = _alert_reason_to_cause(alert.reason).lower()
        if alert.severity == AlertSeverity.CRITICAL:
            return MaintenanceType.CORRECTIVE.value
        if any(token in cause for token in ("bearing", "compressor", "motor", "pump", "fan", "belt")):
            return MaintenanceType.CORRECTIVE.value
        if any(token in cause for token in ("seal", "filter", "gasket", "spark")):
            return MaintenanceType.REPLACEMENT.value
        return MaintenanceType.PREVENTIVE.value

    def _technician_for_event(alert, log, work_order) -> str:
        if log and log.technician:
            return log.technician
        if work_order and work_order.assigned_technician and work_order.assigned_technician != "Unassigned":
            return work_order.assigned_technician
        if machine.assigned_technician:
            return machine.assigned_technician

        technicians = [
            "Rajesh Kumar", "Priya Sharma", "Amit Singh",
            "Sneha Patel", "Vikram Reddy", "Anita Desai"
        ]
        return technicians[_stable_index(machine.machine_id, alert.alert_id) % len(technicians)]

    def _cost_for_event(alert, log, work_order, maintenance_type: str) -> float:
        if log and log.cost:
            return log.cost
        if work_order and work_order.cost:
            return work_order.cost

        base_costs = {
            MaintenanceType.INSPECTION.value: 850,
            MaintenanceType.PREVENTIVE.value: 1800,
            MaintenanceType.CORRECTIVE.value: 3200,
            MaintenanceType.REPLACEMENT.value: 4200,
            MaintenanceType.EMERGENCY.value: 5600,
        }
        severity_multiplier = 1.35 if alert.severity == AlertSeverity.CRITICAL else 1.0
        variation = (_stable_index(alert.alert_id, alert.reason) % 900) + 125
        return round((base_costs.get(maintenance_type, 1800) + variation) * severity_multiplier, 2)

    def _status_for_event(alert, log) -> str:
        if log and log.status:
            return log.status
        if alert.status == "Open":
            return "Scheduled"
        if alert.status in ("Closed", "Resolved"):
            return "Completed"
        return alert.status

    history = []
    for alert in sorted(alerts, key=lambda a: a.timestamp, reverse=True):
        log = _matching_log_for_alert(alert)
        work_order = _matching_work_order_for_alert(alert)
        maintenance_type = _maintenance_type_for_event(alert, log, work_order)
        history.append({
            "Machine ID": alert.machine_id,
            "Date": alert.timestamp.strftime("%Y-%m-%d"),
            "Condition": alert.severity.value,
            "Reason": alert.reason,
            "Cause": _alert_reason_to_cause(alert.reason),
            "Technician": _technician_for_event(alert, log, work_order),
            "Cost": _cost_for_event(alert, log, work_order, maintenance_type),
            "Status": _status_for_event(alert, log),
            "Maintenance Type": maintenance_type
        })
    
    if not history:
        st.info("No maintenance logs for this machine.")
    else:
        df = pd.DataFrame(history)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Events", len(history))
        col2.metric("Total Cost", "—")
        col3.metric("Total Hours", "—")
    
    # Add maintenance log form
    st.markdown("---")
    st.markdown("### ➕ Add Maintenance Log")
    
    with st.form("add_log_form"):
        col1, col2 = st.columns(2)
        technician = col1.text_input("Technician", "Rajesh Kumar")
        maint_type = col2.selectbox("Type", [t.value for t in MaintenanceType])
        
        col1, col2 = st.columns(2)
        issue = col1.text_area("Issue", "Routine inspection")
        action = col2.text_area("Action Taken", "Standard maintenance performed")
        
        col1, col2, col3 = st.columns(3)
        cost = col1.number_input("Cost (₹)", min_value=0.0, step=100.0)
        duration = col2.number_input("Duration (hours)", min_value=0.0, step=0.5)
        parts = col3.text_input("Parts Replaced (comma separated)")
        
        submitted = st.form_submit_button("Save Log", use_container_width=True)
        if submitted:
            parts_list = [p.strip() for p in parts.split(",") if p.strip()] if parts else []
            log = data_store.maintenance_log_service.add_log(
                machine_id=machine.machine_id,
                technician=technician,
                maintenance_type=MaintenanceType(maint_type),
                issue=issue,
                action_taken=action,
                cost=cost,
                duration_hours=duration,
                parts_replaced=parts_list
            )
            st.success(f"Log {log.log_id} saved!")


def render_ai_chat_tab(machine: MachineInfo):
    """Render AI chat interface for a machine."""
    st.markdown("### 🤖 AI Maintenance Copilot")
    st.markdown(f"Ask questions about **{machine.name} ({machine.machine_id})**")
    
    # Chat history container
    chat_container = st.container()
    
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # Chat input
    prompt = st.chat_input(f"Ask about {machine.machine_id}...")
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Build analysis from machine data
                analysis = {
                    "monitoring": {
                        "severity": machine.status.value,
                        "issues": []
                    },
                    "sensor_history": []
                }
                
                response = copilot.answer(prompt, analysis)
                st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response})


def render_machine_alerts_tab(machine: MachineInfo):
    """Render alerts for a machine.
    
    Shows "Alert History" section with all alerts (historical + active).
    Active alerts are highlighted.
    """
    alerts = data_store.alert_service.get_alerts_by_machine(machine.machine_id)
    active_alerts = [a for a in alerts if a.status == "Open"]

    if not alerts:
        st.info("No alerts for this machine.")
        return

    # Show active alerts first if any
    if active_alerts:
        st.markdown("### 🚨 Active Alerts")
        for alert in sorted(active_alerts, key=lambda a: a.timestamp, reverse=True):
            severity_color = {"CRITICAL": "#FF4444", "WARNING": "#FFAA00", "INFO": "#4488FF"}.get(alert.severity.value, "#888")
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                        border-radius: 8px; padding: 10px; margin: 5px 0;
                        border-left: 4px solid {severity_color};'>
                <span style='color:{severity_color};font-weight:bold;'>{alert.severity.value}</span>
                <span style='color:#aaa;margin-left:10px;'>{alert.timestamp.strftime('%Y-%m-%d %H:%M')}</span>
                <p style='margin:5px 0;color:#ccc;'>{alert.reason}</p>
                <p style='margin:2px 0;color:#888;font-size:0.85rem;'>{alert.recommended_action}</p>
            </div>
            """, unsafe_allow_html=True)

    def _alert_reason_to_cause(reason: str) -> str:
        """Derive a meaningful root cause from the alert reason.
        Reason = WHAT happened. Cause = WHY it happened.
        """
        r = reason.lower()
        if "bearing" in r:
            return "Worn bearing race"
        if "refrigerant" in r:
            return "Refrigerant leakage"
        if "condenser" in r or "overheating" in r:
            return "Dust accumulation on coils"
        if "evaporator" in r or "icing" in r:
            return "Restricted airflow"
        if "motor" in r:
            return "Bearing wear"
        if "compressor" in r:
            return "Dirty condenser coil"
        if "fan" in r:
            return "Failed fan bearing"
        if "door" in r or "seal" in r:
            return "Damaged door gasket"
        if "cooling" in r:
            return "Low refrigerant charge"
        if "drum" in r or "vibration" in r:
            return "Unbalanced drum assembly"
        if "pump" in r or "water" in r:
            return "Pump impeller wear"
        if "alternator" in r:
            return "Failed alternator diode"
        if "fuel" in r:
            return "Clogged fuel filter"
        if "voltage" in r or "electrical" in r:
            return "Loose electrical connection"
        if "oil" in r:
            return "Oil leak from gasket"
        if "coolant" in r:
            return "Radiator blockage"
        if "timing" in r or "belt" in r:
            return "Belt material fatigue"
        if "spark" in r or "ignition" in r:
            return "Spark plug electrode wear"
        if "rpm" in r or "speed" in r:
            return "Sensor calibration drift"
        if "overload" in r or "current" in r or "load" in r:
            return "Excessive load condition"
        if "performance" in r or "drift" in r:
            return "Component degradation over time"
        return "Component degradation over time"

    # Show historical alerts section
    st.markdown("### 📜 Alert History")
    alert_rows = []
    for alert in sorted(alerts, key=lambda a: a.timestamp, reverse=True):
        cause = _alert_reason_to_cause(alert.reason)
        alert_rows.append({
            "Time": alert.timestamp.strftime("%Y-%m-%d %H:%M"),
            "Severity": alert.severity.value,
            "Reason": alert.reason,
            "Cause": cause,
            "Status": alert.status
        })

    df = pd.DataFrame(alert_rows)

    def color_severity(val):
        colors = {"CRITICAL": "#FF4444", "WARNING": "#FFAA00", "INFO": "#4488FF"}
        return f"background-color: {colors.get(val, '#888')}; color: white;"

    st.dataframe(
        df.style.applymap(color_severity, subset=["Severity"]),
        use_container_width=True,
        hide_index=True
    )


# ==================== ANALYTICS PAGE ====================

def render_analytics():
    """Render analytics page with business-focused fleet insights."""
    st.markdown("""
    <style>
        .stApp {
            background: #F8FAFC;
            font-family: 'Inter', sans-serif;
        }
        .main-header {
            font-family: 'Inter', sans-serif;
            font-size: 36px;
            font-weight: 700;
            color: #111827;
        }
        .analytics-section-title {
            font-family: 'Inter', sans-serif;
            font-size: 34px;
            font-weight: 700;
            color: #111827;
            margin: 8px 0 18px 0;
        }
        .analytics-card-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 20px;
            align-items: stretch;
        }
        .analytics-category-card {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-left: 6px solid var(--health-border);
            border-radius: 18px;
            padding: 22px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.08);
            transition: 0.25s ease;
            min-height: 245px;
            height: 100%;
            font-family: 'Inter', sans-serif;
        }
        .analytics-category-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 32px rgba(0,0,0,0.12);
        }
        .analytics-card-title {
            font-size: 24px;
            line-height: 1.2;
            font-weight: 700;
            color: #1F2937;
            margin: 0 0 10px 0;
        }
        .analytics-card-subtitle {
            font-size: 16px;
            color: #6B7280;
            margin: 0 0 18px 0;
        }
        .analytics-badge-wrap {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .analytics-stat-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 15px;
            font-weight: 600;
            color: #1F2937;
            background: #F3F4F6;
            border: 1px solid #E5E7EB;
            white-space: nowrap;
        }
        .analytics-stat-badge.healthy { background: #DCFCE7; color: #166534; border-color: #BBF7D0; }
        .analytics-stat-badge.warning { background: #FEF3C7; color: #92400E; border-color: #FDE68A; }
        .analytics-stat-badge.critical { background: #FEE2E2; color: #991B1B; border-color: #FECACA; }
        .analytics-stat-badge.health { background: #FCE7F3; color: #9D174D; border-color: #FBCFE8; }
        .analytics-stat-badge.alerts { background: #E0F2FE; color: #075985; border-color: #BAE6FD; }
        .analytics-stat-badge.maintenance { background: #EDE9FE; color: #5B21B6; border-color: #DDD6FE; }
        /* Analytics category cards - style the column containing the card header */
        div[data-testid="column"]:has(.analytics-card-header) {
            background: #FFFFFF !important;
            border: 1px solid #E5E7EB !important;
            border-radius: 18px !important;
            padding: 22px 22px 12px !important;
            box-shadow: 0 8px 24px rgba(0,0,0,0.08) !important;
            margin: 0 !important;
        }
        /* Remove extra padding from inner containers inside analytics card columns */
        div[data-testid="column"]:has(.analytics-card-header) > div {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
            box-shadow: none !important;
        }
        @media (max-width: 1024px) {
            .analytics-card-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 640px) {
            .analytics-card-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
    """, unsafe_allow_html=True)
    st.markdown("<h1 class='main-header'>Equipment Analytics</h1>", unsafe_allow_html=True)
    st.markdown("---")

    all_machines = simulator.get_all_machines()
    all_alerts = data_store.alert_service.get_all_alerts()
    open_alerts = [a for a in all_alerts if a.status == "Open"]
    today = datetime.now()

    machines_by_category = {
        finfo.get("name", fid): simulator.get_factory_machines(fid)
        for fid, finfo in simulator.get_all_factories().items()
    }

    # Pre-compute maintenance log count per category from actual maintenance logs
    all_maintenance_logs = data_store.maintenance_log_service.get_all_logs()
    machine_map = {m.machine_id: m for m in all_machines}
    cat_maintenance_counts = {}
    for log in all_maintenance_logs:
        log_machine = machine_map.get(log.machine_id)
        if log_machine:
            cat = log_machine.machine_category
            cat_maintenance_counts[cat] = cat_maintenance_counts.get(cat, 0) + 1

    category_rows = []
    for category, machines in machines_by_category.items():
        machine_ids = {m.machine_id for m in machines}
        category_open_alerts = [a for a in open_alerts if a.machine_id in machine_ids]
        maintenance_due = [
            m for m in machines
            if m.next_maintenance_date and (m.next_maintenance_date - today).days <= 7
        ]
        maint_count = cat_maintenance_counts.get(category, 0)
        category_rows.append({
            "Category": category,
            "Machines": len(machines),
            "Healthy": sum(1 for m in machines if m.status == MachineStatus.NORMAL),
            "Warning": sum(1 for m in machines if m.status == MachineStatus.WARNING),
            "Critical": sum(1 for m in machines if m.status == MachineStatus.CRITICAL),
            "Average Health": round(sum(m.health_score for m in machines) / len(machines), 1) if machines else 0,
            "Open Alerts": len(category_open_alerts),
            "Maintenance Due": len(maintenance_due),
            "Maintenance Count": maint_count,
            "Average Failure Probability": round(sum(m.failure_probability for m in machines) / len(machines) * 100, 1) if machines else 0,
        })

    category_icons = {
        "Refrigerator": "&#129482;",
        "Washing Machine": "&#129530;",
        "Air Conditioner": "&#10052;&#65039;",
        "Generator": "&#9889;",
        "Car Engine": "&#128663;",
    }
    st.markdown("<div class='analytics-section-title'>Category Summary</div>", unsafe_allow_html=True)
    card_cols = st.columns(3)
    for idx, row in enumerate(category_rows):
        with card_cols[idx % 3]:
            status_color = "#EF4444" if row["Critical"] else "#F59E0B" if row["Warning"] else "#22C55E"
            icon = category_icons.get(row["Category"], "&#9881;&#65039;")
            cname = row["Category"]
            # Build query param URLs for each badge (relative URLs navigate within same tab)
            def qp(cat, filt, page, maint_cat=None):
                base = f"?_analytics_category={quote(str(cat))}&_analytics_filter={quote(str(filt))}&_analytics_page={quote(str(page))}"
                if maint_cat:
                    base += f"&_maint_cat={quote(str(maint_cat))}"
                return base
            # Render entire card as ONE complete HTML block - all badges INSIDE the card
            st.markdown(f"""
<div style='background: #FFFFFF; border: 1px solid #E5E7EB; border-left: 6px solid {status_color}; border-radius: 18px; padding: 22px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); font-family: Inter, sans-serif;'>
<div style='font-size: 24px; line-height: 1.2; font-weight: 700; color: #1F2937; margin: 0 0 10px 0;'>{icon} {cname}</div>
<div style='font-size: 16px; color: #6B7280; margin: 0 0 18px 0;'>Machines: {row["Machines"]}</div>
<div style='display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;'>
<a href='{qp(cname, "healthy", "analytics_machines")}' target='_self' style='display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 20px; font-size: 15px; font-weight: 600; color: #166534; background: #DCFCE7; border: 1px solid #BBF7D0; text-decoration: none; white-space: nowrap;'>✅ Healthy {row["Healthy"]}</a>
<a href='{qp(cname, "warning", "analytics_machines")}' target='_self' style='display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 20px; font-size: 15px; font-weight: 600; color: #92400E; background: #FEF3C7; border: 1px solid #FDE68A; text-decoration: none; white-space: nowrap;'>🟡 Warning {row["Warning"]}</a>
<a href='{qp(cname, "critical", "analytics_machines")}' target='_self' style='display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 20px; font-size: 15px; font-weight: 600; color: #991B1B; background: #FEE2E2; border: 1px solid #FECACA; text-decoration: none; white-space: nowrap;'>🔴 Critical {row["Critical"]}</a>
</div>
<div style='display: flex; flex-wrap: wrap; gap: 8px;'>
<a href='{qp(cname, "health", "analytics_health_overview")}' target='_self' style='display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 20px; font-size: 15px; font-weight: 600; color: #9D174D; background: #FCE7F3; border: 1px solid #FBCFE8; text-decoration: none; white-space: nowrap;'>❤️ Avg Health {row["Average Health"]}%</a>
<a href='{qp(cname, "alerts", "alerts")}' target='_self' style='display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 20px; font-size: 15px; font-weight: 600; color: #075985; background: #E0F2FE; border: 1px solid #BAE6FD; text-decoration: none; white-space: nowrap;'>🚨 Alerts {row["Open Alerts"]}</a>
<a href='{qp(cname, "maintenance", "maintenance_logs", cname)}' target='_self' style='display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 20px; font-size: 15px; font-weight: 600; color: #5B21B6; background: #EDE9FE; border: 1px solid #DDD6FE; text-decoration: none; white-space: nowrap;'>🔧 Maintenance {row["Maintenance Count"]}</a>
</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    avg_health = sum(m.health_score for m in all_machines) / len(all_machines) if all_machines else 0
    avg_risk = sum(m.failure_probability for m in all_machines) / len(all_machines) if all_machines else 0
    trend_rows = []
    for days_back in range(29, -1, -1):
        drift = (days_back / 29) * (avg_risk * 18) if avg_risk else 0
        trend_rows.append({
            "Date": (today - timedelta(days=days_back)).date().isoformat(),
            "Average Health": round(max(0, min(100, avg_health - drift)), 1),
        })

    col1, col2 = st.columns(2)
    with col1:
        health_df = pd.DataFrame(category_rows)
        fig = px.bar(
            health_df,
            x="Category",
            y="Average Health",
            title="Average Health by Category",
            color="Category",
            color_discrete_map=MACHINE_TYPE_COLORS,
        )
        fig.update_layout(height=360, paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        failure_df = pd.DataFrame(category_rows)
        fig = px.bar(
            failure_df,
            x="Category",
            y="Average Failure Probability",
            title="Failure Probability by Category",
            color="Category",
            color_discrete_map=MACHINE_TYPE_COLORS,
        )
        fig.update_layout(height=360, paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        alert_df = pd.DataFrame([{"Category": row["Category"], "Open Alerts": row["Open Alerts"]} for row in category_rows])
        fig = px.bar(
            alert_df,
            x="Category",
            y="Open Alerts",
            title="Alerts by Category",
            color="Category",
            color_discrete_map=MACHINE_TYPE_COLORS,
        )
        fig.update_layout(height=360, paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        manufacturer_rows = []
        for manufacturer in sorted({m.manufacturer for m in all_machines}):
            manufacturer_machines = [m for m in all_machines if m.manufacturer == manufacturer]
            manufacturer_rows.append({
                "Manufacturer": manufacturer,
                "Machines": len(manufacturer_machines),
                "Average Health": round(sum(m.health_score for m in manufacturer_machines) / len(manufacturer_machines), 1) if manufacturer_machines else 0,
                "Average Failure Probability": round(sum(m.failure_probability for m in manufacturer_machines) / len(manufacturer_machines) * 100, 1) if manufacturer_machines else 0,
            })
        manufacturer_df = pd.DataFrame(manufacturer_rows).sort_values("Average Health", ascending=False)
        fig = px.scatter(
            manufacturer_df,
            x="Average Failure Probability",
            y="Average Health",
            size="Machines",
            color="Manufacturer",
            title="Manufacturer Performance",
            hover_data=["Machines"],
        )
        fig.update_layout(height=360, paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc', yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("AI Recommendations")
    recommendations = []
    critical_machines = [m for m in all_machines if m.status == MachineStatus.CRITICAL]
    warning_machines = [m for m in all_machines if m.status == MachineStatus.WARNING]
    due_soon = [m for m in all_machines if m.next_maintenance_date and (m.next_maintenance_date - today).days <= 7]
    if critical_machines:
        recommendations.append(f"Immediate inspection needed for {len(critical_machines)} critical machines.")
    if warning_machines:
        recommendations.append(f"Plan preventive maintenance for {len(warning_machines)} warning machines.")
    if due_soon:
        recommendations.append(f"Schedule maintenance capacity for {len(due_soon)} machines due within 7 days.")
    if open_alerts:
        recommendations.append(f"Review and close {len(open_alerts)} open alerts before the next operating cycle.")
    weakest_category = min(category_rows, key=lambda row: row["Average Health"], default=None)
    if weakest_category:
        recommendations.append(f"Prioritize {weakest_category['Category']} because it has the lowest average health at {weakest_category['Average Health']}%.")
    if not recommendations:
        recommendations.append("Fleet condition is stable. Continue routine monitoring and scheduled maintenance.")

    for recommendation in recommendations:
        st.info(recommendation)

    # === HIGH RISK MACHINES DETAIL ===
    st.markdown("---")
    st.subheader("Top 10 High-Risk Machines")
    high_risk = sorted(all_machines, key=lambda m: (m.failure_probability, 100 - m.health_score), reverse=True)[:10]
    risk_rows = []
    for m in high_risk:
        risk_rows.append({
            "Machine ID": m.machine_id,
            "Category": m.machine_category,
            "Health Score": f"{m.health_score:.1f}%",
            "Failure Probability": f"{m.failure_probability*100:.1f}%",
            "Condition": m.status.value
        })
    if risk_rows:
        df_risk = pd.DataFrame(risk_rows)
        sel = st.dataframe(
            df_risk,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Machine ID": st.column_config.Column("Machine ID", width="small"),
                "Category": st.column_config.Column("Category", width="medium"),
                "Health Score": st.column_config.Column("Health Score", width="small"),
                "Failure Probability": st.column_config.Column("Failure Probability", width="small"),
                "Condition": st.column_config.Column("Condition", width="small"),
            }
        )
        if len(sel.selection.rows) > 0:
            row_idx = sel.selection.rows[0]
            machine_id = df_risk.iloc[row_idx]["Machine ID"]
            navigate_to_machine(machine_id)
            st.rerun()


# ==================== ALERTS PAGE ====================

def render_alerts():
    """Render alert center - shows ONLY active (Open) alerts."""
    st.markdown("<h1 class='main-header'>🚨 Alert Center</h1>", unsafe_allow_html=True)
    if came_from_analytics_chip("alerts"):
        if st.button("← Back to Analytics"):
            return_to_analytics_from_chip()
    st.markdown("<p class='sub-header'>Showing only active alerts. Resolved alerts are moved to history.</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    alerts = data_store.alert_service.get_open_alerts()
    if (
        st.query_params.get("_analytics_page") == "alerts"
        and st.session_state.get("analytics_chip_filter") == "alerts"
        and st.session_state.get("analytics_category")
    ):
        analytics_category = st.session_state.get("analytics_category")
        category_machine_ids = {
            machine.machine_id
            for machine in simulator.get_all_machines()
            if machine.machine_category == analytics_category
        }
        alerts = [a for a in alerts if a.machine_id in category_machine_ids]

    # Summary: only active alerts (Open) with Warning and Critical breakdown
    col1, col2, col3 = st.columns(3)
    open_count = len(alerts)
    critical_count = sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL)
    warning_count = sum(1 for a in alerts if a.severity == AlertSeverity.WARNING)
    
    col1.metric("Active Alerts", open_count)
    col2.metric("Warning", warning_count)
    col3.metric("Critical", critical_count)
    
    st.markdown("---")
    
    # Filter by severity - only for active alerts
    severity_filter = st.selectbox("Filter by Severity", ["All", "CRITICAL", "WARNING", "INFO"])
    
    if severity_filter != "All":
        alerts = [a for a in alerts if a.severity.value == severity_filter]
    
    # Sort by timestamp descending (newest first)
    alerts.sort(key=lambda a: a.timestamp, reverse=True)
    
    if not alerts:
        st.success("✅ No active alerts. All systems normal.")
    else:
        st.caption(f"Showing {len(alerts)} active alert(s)")
        alert_rows = []
        for a in alerts:
            machine = simulator.get_machine(a.machine_id)
            machine_name = machine.name if machine else "N/A"
            alert_rows.append({
                "Machine ID": a.machine_id,
                "Alert ID": a.alert_id[:12],
                "Description": a.reason[:60],
                "Date": a.timestamp.strftime('%Y-%m-%d %H:%M'),
                "Condition": a.severity.value,
                "Status": a.status
            })
        if alert_rows:
            df_alert_page = pd.DataFrame(alert_rows)
            sel = st.dataframe(
                df_alert_page,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "Machine ID": st.column_config.Column("Machine ID", width="small"),
                    "Alert ID": st.column_config.Column("Alert ID", width=max(150, int(df_alert_page["Alert ID"].astype(str).map(len).max() * 10 + 50))),
                    "Description": st.column_config.Column("Description", width="large"),
                    "Date": st.column_config.Column("Date", width=150),
                    "Condition": st.column_config.Column("Condition", width="small"),
                    "Status": st.column_config.Column("Status", width="small"),
                }
            )
            if len(sel.selection.rows) > 0:
                row_idx = sel.selection.rows[0]
                machine_id = df_alert_page.iloc[row_idx]["Machine ID"]
                navigate_to_machine(machine_id)
                st.rerun()


# ==================== WORK ORDERS PAGE ====================

def render_work_orders():
    """Render work orders page - shows ONLY Open and In Progress work orders.
    Completed/Cancelled work orders are moved to Maintenance Logs."""
    st.markdown("<h1 class='main-header'>📋 Work Orders</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Showing only active work orders (Open / In Progress). Completed work orders are in Maintenance Logs.</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Show only Open and In Progress counts
    col1, col2 = st.columns(2)
    summary = data_store.work_order_service.get_work_order_summary()
    col1.metric("Open", summary.get("Open", 0))
    col2.metric("In Progress", summary.get("In Progress", 0))
    
    st.markdown("---")
    
    # Filter by status - only active statuses
    status_filter = st.selectbox("Filter by Status", ["All", "Open", "In Progress"])
    
    # Get only open and in-progress work orders (active only)
    all_work_orders = data_store.work_order_service.get_all_work_orders()
    work_orders = [wo for wo in all_work_orders if wo.status.value in ("Open", "In Progress")]
    if status_filter != "All":
        work_orders = [wo for wo in work_orders if wo.status.value == status_filter]
    
    work_orders.sort(key=lambda wo: wo.created_date, reverse=True)
    
    if not work_orders:
        st.success("✅ No active work orders. All machines are operating normally.")
    else:
        st.caption(f"Showing {len(work_orders)} active work order(s)")
        wo_rows = []
        for wo in work_orders:
            wo_rows.append({
                "Machine ID": wo.machine_id,
                "Work Order ID": wo.work_order_id[:12],
                "Created Date": wo.created_date.strftime('%Y-%m-%d'),
                "Priority": wo.priority,
                "Technician": wo.assigned_technician,
                "Status": wo.status.value
            })
        if wo_rows:
            df_wo = pd.DataFrame(wo_rows)
            sel = st.dataframe(
                df_wo,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "Machine ID": st.column_config.Column("Machine ID", width="small"),
                    "Work Order ID": st.column_config.Column("Work Order ID", width="small"),
                    "Created Date": st.column_config.Column("Created Date", width="medium"),
                    "Priority": st.column_config.Column("Priority", width="small"),
                    "Technician": st.column_config.Column("Technician", width="medium"),
                    "Status": st.column_config.Column("Status", width="small"),
                }
            )
            if len(sel.selection.rows) > 0:
                row_idx = sel.selection.rows[0]
                machine_id = df_wo.iloc[row_idx]["Machine ID"]
                navigate_to_machine(machine_id)
                st.rerun()


# ==================== REPORTS PAGE ====================

def _get_report_parts(report: Any) -> Dict[str, Any]:
    """Normalize Report objects and stored report dictionaries for display."""
    if isinstance(report, dict):
        return {
            "report_id": report.get("report_id", ""),
            "title": report.get("title", "Report"),
            "report_type": report.get("report_type", ""),
            "generated_at": report.get("generated_at", datetime.now().isoformat()),
            "data": report.get("data", {})
        }
    return {
        "report_id": getattr(report, "report_id", ""),
        "title": getattr(report, "title", "Report"),
        "report_type": getattr(report, "report_type", ""),
        "generated_at": getattr(report, "generated_at", datetime.now()).isoformat(),
        "data": getattr(report, "data", {})
    }


def _attention_rows() -> List[Dict[str, Any]]:
    rows = []
    for machine in simulator.get_all_machines():
        if machine.status not in (MachineStatus.WARNING, MachineStatus.CRITICAL):
            continue
        recommendation = (
            "Immediate corrective maintenance required"
            if machine.status == MachineStatus.CRITICAL
            else "Schedule preventive maintenance"
        )
        rows.append({
            "Machine ID": machine.machine_id,
            "Machine Name": machine.name,
            "Category": machine.machine_category,
            "Health Score": f"{machine.health_score:.1f}%",
            "Status": machine.status.value,
            "Failure Probability": f"{machine.failure_probability * 100:.1f}%",
            "Recommendation": recommendation
        })
    return rows


def _daily_report_tables(data: Dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Count open alerts from the data's open_alerts list
    open_alerts_list = data.get("open_alerts", [])
    open_alerts_count = len(open_alerts_list) if isinstance(open_alerts_list, list) else data.get("new_alerts", 0)
    
    fleet_summary = pd.DataFrame([{
        "Total Machines": data.get("total_machines", 0),
        "Healthy": data.get("normal_count", 0),
        "Warning": data.get("warning_count", 0),
        "Critical": data.get("critical_count", 0),
        "Average Health": f"{data.get('average_health', 0)}%",
        "Open Alerts": open_alerts_count,
        "New Work Orders": data.get("new_work_orders", 0)
    }])
    attention = pd.DataFrame(_attention_rows())
    return fleet_summary, attention


def _daily_ai_summary(data: Dict[str, Any], attention_count: int) -> str:
    critical = data.get("critical_count", 0)
    warning = data.get("warning_count", 0)
    avg_health = data.get("average_health", 0)
    if critical:
        condition = "requires immediate attention"
    elif warning:
        condition = "is stable but needs preventive follow-up"
    else:
        condition = "is operating normally"
    return (
        f"The fleet {condition}. Average health is {avg_health}%, with "
        f"{critical} critical machines and {warning} warning machines. "
        f"{attention_count} machines currently require maintenance review."
    )


def _csv_bytes(title: str, fleet_summary: pd.DataFrame, attention: pd.DataFrame, summary: str) -> bytes:
    output = io.StringIO()
    output.write(f"{title}\n\n")
    output.write("Fleet Summary\n")
    fleet_summary.to_csv(output, index=False)
    output.write("\nMachines Requiring Attention\n")
    if attention.empty:
        output.write("No warning or critical machines\n")
    else:
        attention.to_csv(output, index=False)
    output.write("\nAI Summary\n")
    output.write(summary)
    return output.getvalue().encode("utf-8")


def _excel_bytes(title: str, fleet_summary: pd.DataFrame, attention: pd.DataFrame, summary: str) -> bytes:
    def xml_escape(value: Any) -> str:
        import html
        return html.escape(str(value), quote=True)

    rows = [f"<Row><Cell><Data ss:Type='String'>{xml_escape(title)}</Data></Cell></Row>"]
    rows.append("<Row></Row>")
    rows.append("<Row><Cell><Data ss:Type='String'>Fleet Summary</Data></Cell></Row>")
    rows.append("<Row>" + "".join(
        f"<Cell><Data ss:Type='String'>{xml_escape(col)}</Data></Cell>"
        for col in fleet_summary.columns
    ) + "</Row>")
    for _, row in fleet_summary.iterrows():
        rows.append("<Row>" + "".join(
            f"<Cell><Data ss:Type='String'>{xml_escape(row[col])}</Data></Cell>"
            for col in fleet_summary.columns
        ) + "</Row>")
    rows.append("<Row></Row>")
    rows.append("<Row><Cell><Data ss:Type='String'>Machines Requiring Attention</Data></Cell></Row>")
    if attention.empty:
        rows.append("<Row><Cell><Data ss:Type='String'>No warning or critical machines</Data></Cell></Row>")
    else:
        rows.append("<Row>" + "".join(
            f"<Cell><Data ss:Type='String'>{xml_escape(col)}</Data></Cell>"
            for col in attention.columns
        ) + "</Row>")
        for _, row in attention.iterrows():
            rows.append("<Row>" + "".join(
                f"<Cell><Data ss:Type='String'>{xml_escape(row[col])}</Data></Cell>"
                for col in attention.columns
            ) + "</Row>")
    rows.append("<Row></Row>")
    rows.append(f"<Row><Cell><Data ss:Type='String'>AI Summary</Data></Cell><Cell><Data ss:Type='String'>{xml_escape(summary)}</Data></Cell></Row>")
    workbook = """<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
<Worksheet ss:Name="Report"><Table>
""" + "\n".join(rows) + """
</Table></Worksheet></Workbook>
"""
    return workbook.encode("utf-8")


def _safe_pdf_multi_cell(pdf, text: str, height: int = 6, border: int = 0):
    available_width = pdf.w - pdf.l_margin - pdf.r_margin
    if available_width <= 5:
        pdf.ln()
        pdf.set_x(pdf.l_margin)
        available_width = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_xy(pdf.l_margin, pdf.get_y())
    wrapped_lines = []
    for line in str(text).splitlines() or [""]:
        parts = []
        for word in line.split(" "):
            if not word:
                parts.append(word)
                continue
            if pdf.get_string_width(word) > available_width:
                max_chars = max(1, int(len(word) * available_width / max(pdf.get_string_width(word), 1)))
                parts.extend(textwrap.wrap(word, width=max_chars, break_long_words=True, break_on_hyphens=False))
            else:
                parts.append(word)
        wrapped_lines.append(" ".join(parts))

    pdf.multi_cell(available_width, height, "\n".join(wrapped_lines), border=border)


def _pdf_bytes(title: str, report_date: str, fleet_summary: pd.DataFrame, attention: pd.DataFrame, summary: str) -> bytes:
    def clean(value: Any) -> str:
        return str(value).encode("latin-1", "replace").decode("latin-1")

    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        usable_width = max(1, pdf.w - pdf.l_margin - pdf.r_margin)
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, clean(title), ln=True)
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 8, clean(f"Report Date: {report_date}"), ln=True)
        pdf.ln(4)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Fleet Summary", ln=True)
        pdf.set_font("Arial", "", 10)
        for col, value in fleet_summary.iloc[0].items():
            pdf.cell(65, 7, clean(col), border=1)
            pdf.cell(0, 7, clean(value), border=1, ln=True)
        pdf.ln(4)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Machines Requiring Attention", ln=True)
        pdf.set_font("Arial", "", 9)
        if attention.empty:
            pdf.cell(0, 7, "No warning or critical machines", ln=True)
        else:
            for _, row in attention.iterrows():
                _safe_pdf_multi_cell(pdf, clean(
                    f"{row['Machine ID']} | {row['Machine Name']} | {row['Category']} | "
                    f"{row['Health Score']} | {row['Status']} | {row['Failure Probability']} | "
                    f"{row['Recommendation']}"
                ), height=6, border=1)
        pdf.ln(4)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "AI Summary", ln=True)
        pdf.set_font("Arial", "", 10)
        _safe_pdf_multi_cell(pdf, clean(summary), height=6)
        output = pdf.output(dest="S")
        return bytes(output) if isinstance(output, bytearray) else output.encode("latin-1")
    except ImportError:
        lines = [title, f"Report Date: {report_date}", "", "Fleet Summary"]
        lines.extend(f"{col}: {value}" for col, value in fleet_summary.iloc[0].items())
        lines.extend(["", "Machines Requiring Attention"])
        if attention.empty:
            lines.append("No warning or critical machines")
        else:
            for _, row in attention.iterrows():
                lines.append(
                    f"{row['Machine ID']} | {row['Machine Name']} | {row['Category']} | "
                    f"{row['Health Score']} | {row['Status']} | {row['Failure Probability']} | "
                    f"{row['Recommendation']}"
                )
        lines.extend(["", "AI Summary", summary])
        text_commands = ["BT", "/F1 10 Tf", "50 780 Td"]
        for idx, line in enumerate(lines[:80]):
            escaped = clean(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            if idx:
                text_commands.append("0 -14 Td")
            text_commands.append(f"({escaped}) Tj")
        text_commands.append("ET")
        stream = "\n".join(text_commands).encode("latin-1")
        objects = [
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
            b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
            b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"\nendstream endobj",
        ]
        pdf = b"%PDF-1.4\n"
        offsets = []
        for obj in objects:
            offsets.append(len(pdf))
            pdf += obj + b"\n"
        xref = len(pdf)
        pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
        for offset in offsets:
            pdf += f"{offset:010d} 00000 n \n".encode("ascii")
        pdf += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
        return pdf


def _download_report_buttons(title: str, report_date: str, fleet_summary: pd.DataFrame,
                             attention: pd.DataFrame, summary: str, key_context: str = ""):
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_").lower() or "report"
    key_suffix = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{key_context}_{safe_name}_{report_date}").strip("_")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Download PDF",
            data=_pdf_bytes(title, report_date, fleet_summary, attention, summary),
            file_name=f"{safe_name}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=f"pdf_{key_suffix}"
        )
    with col2:
        st.download_button(
            "Download Excel",
            data=_excel_bytes(title, report_date, fleet_summary, attention, summary),
            file_name=f"{safe_name}.xls",
            mime="application/vnd.ms-excel",
            use_container_width=True,
            key=f"excel_{key_suffix}"
        )
    with col3:
        st.download_button(
            "Download CSV",
            data=_csv_bytes(title, report_date, fleet_summary, attention, summary),
            file_name=f"{safe_name}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"csv_{key_suffix}"
        )


def _report_data_rows(data: Any, prefix: str = "") -> List[Dict[str, str]]:
    rows = []
    if isinstance(data, dict):
        for key, value in data.items():
            label = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, (dict, list)):
                rows.extend(_report_data_rows(value, label))
            else:
                rows.append({"Field": label.replace("_", " ").title(), "Value": str(value)})
    elif isinstance(data, list):
        if not data:
            rows.append({"Field": prefix.replace("_", " ").title(), "Value": ""})
        for idx, item in enumerate(data, start=1):
            label = f"{prefix} {idx}" if prefix else f"Item {idx}"
            if isinstance(item, (dict, list)):
                rows.extend(_report_data_rows(item, label))
            else:
                rows.append({"Field": label.replace("_", " ").title(), "Value": str(item)})
    else:
        rows.append({"Field": prefix.replace("_", " ").title() or "Value", "Value": str(data)})
    return rows


def _generic_csv_bytes(title: str, generated_at: str, data: Dict[str, Any]) -> bytes:
    output = io.StringIO()
    output.write(f"{title}\n")
    output.write(f"Generated,{generated_at[:19].replace('T', ' ')}\n\n")
    pd.DataFrame(_report_data_rows(data)).to_csv(output, index=False)
    return output.getvalue().encode("utf-8")


def _generic_excel_bytes(title: str, generated_at: str, data: Dict[str, Any]) -> bytes:
    def xml_escape(value: Any) -> str:
        import html
        return html.escape(str(value), quote=True)

    rows = [
        f"<Row><Cell><Data ss:Type='String'>{xml_escape(title)}</Data></Cell></Row>",
        f"<Row><Cell><Data ss:Type='String'>Generated</Data></Cell><Cell><Data ss:Type='String'>{xml_escape(generated_at[:19].replace('T', ' '))}</Data></Cell></Row>",
        "<Row></Row>",
        "<Row><Cell><Data ss:Type='String'>Field</Data></Cell><Cell><Data ss:Type='String'>Value</Data></Cell></Row>"
    ]
    for row in _report_data_rows(data):
        rows.append(
            f"<Row><Cell><Data ss:Type='String'>{xml_escape(row['Field'])}</Data></Cell>"
            f"<Cell><Data ss:Type='String'>{xml_escape(row['Value'])}</Data></Cell></Row>"
        )
    workbook = """<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
<Worksheet ss:Name="Report"><Table>
""" + "\n".join(rows) + """
</Table></Worksheet></Workbook>
"""
    return workbook.encode("utf-8")


def _text_pdf_bytes(lines: List[str]) -> bytes:
    def clean(value: Any) -> str:
        return str(value).encode("latin-1", "replace").decode("latin-1")

    text_commands = ["BT", "/F1 10 Tf", "50 780 Td"]
    for idx, line in enumerate(lines[:80]):
        escaped = clean(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if idx:
            text_commands.append("0 -14 Td")
        text_commands.append(f"({escaped}) Tj")
    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("latin-1")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"\nendstream endobj",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj + b"\n"
    xref = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
    return pdf


def _first_present(data: Dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def _report_sections(title: str, generated_at: str, data: Dict[str, Any]) -> Dict[str, Any]:
    display_title = (
        title if str(title).startswith("Enterprise Predictive Maintenance Report")
        else f"Enterprise Predictive Maintenance Report - {title}"
    )

    def number_value(value: Any) -> float:
        try:
            return float(str(value).replace("%", "").replace(",", "").strip() or 0)
        except ValueError:
            return 0

    def status_value(value: Any) -> str:
        return getattr(value, "value", value)

    def fmt_count(value: Any) -> Any:
        if value in (None, ""):
            return 0
        try:
            return int(float(str(value).replace(",", "")))
        except ValueError:
            return value

    def fmt_percent(value: Any) -> str:
        return f"{number_value(value):.1f}%"

    def fmt_currency(value: Any) -> str:
        return f"₹{number_value(value):,.2f}"

    def fmt_hours(value: Any) -> str:
        return f"{number_value(value):.1f} h"

    all_machines = simulator.get_all_machines()
    all_alerts = data_store.alert_service.get_all_alerts()
    all_work_orders = data_store.work_order_service.get_all_work_orders()
    all_logs = data_store.maintenance_log_service.get_all_logs()
    scope = data.get("report_scope", {}) if isinstance(data.get("report_scope", {}), dict) else {}
    machine_info = data.get("machine_information", {}) if isinstance(data.get("machine_information", {}), dict) else {}
    scope_machine_id = scope.get("machine_id") or machine_info.get("machine_id")
    scope_category = scope.get("category_id") or data.get("category_id")

    if scope_machine_id:
        all_machines = [machine for machine in all_machines if machine.machine_id == scope_machine_id]
        all_alerts = [alert for alert in all_alerts if alert.machine_id == scope_machine_id]
        all_work_orders = [work_order for work_order in all_work_orders if work_order.machine_id == scope_machine_id]
        all_logs = [log for log in all_logs if log.machine_id == scope_machine_id]
    elif scope_category:
        factories = simulator.get_all_factories()
        category_name = factories.get(scope_category, {}).get("name", scope_category)
        category_text = str(scope_category).strip().lower().replace("_", " ")
        category_name_text = str(category_name).strip().lower().replace("_", " ")
        all_machines = [
            machine for machine in all_machines
            if str(machine.factory_id).strip().lower().replace("_", " ") in (category_text, category_name_text)
            or str(machine.machine_category).strip().lower().replace("_", " ") in (category_text, category_name_text)
        ]
        scoped_machine_ids = {machine.machine_id for machine in all_machines}
        all_alerts = [alert for alert in all_alerts if alert.machine_id in scoped_machine_ids]
        all_work_orders = [work_order for work_order in all_work_orders if work_order.machine_id in scoped_machine_ids]
        all_logs = [log for log in all_logs if log.machine_id in scoped_machine_ids]

    fleet_fallback = {
        "total_machines": len(all_machines),
        "healthy": sum(1 for machine in all_machines if machine.status == MachineStatus.NORMAL),
        "warning": sum(1 for machine in all_machines if machine.status == MachineStatus.WARNING),
        "critical": sum(1 for machine in all_machines if machine.status == MachineStatus.CRITICAL),
        "average_health": round(sum(machine.health_score for machine in all_machines) / len(all_machines), 1) if all_machines else 0,
        "average_failure_probability": round(sum(machine.failure_probability for machine in all_machines) / len(all_machines) * 100, 1) if all_machines else 0,
    }

    category_fallback = []
    category_names = sorted({machine.machine_category for machine in all_machines})
    for category_name in category_names:
        machines = [machine for machine in all_machines if machine.machine_category == category_name]
        category_fallback.append({
            "category": category_name,
            "machine_count": len(machines),
            "healthy": sum(1 for machine in machines if machine.status == MachineStatus.NORMAL),
            "warning": sum(1 for machine in machines if machine.status == MachineStatus.WARNING),
            "critical": sum(1 for machine in machines if machine.status == MachineStatus.CRITICAL),
            "average_health": round(sum(machine.health_score for machine in machines) / len(machines), 1) if machines else 0,
        })

    top_risk_fallback = [
        {
            "machine_id": machine.machine_id,
            "machine_name": machine.name,
            "category": machine.machine_category,
            "health_score": machine.health_score,
            "failure_probability": round(machine.failure_probability * 100, 1),
            "status": machine.status.value,
        }
        for machine in sorted(all_machines, key=lambda item: item.failure_probability, reverse=True)[:10]
    ]

    alert_fallback = {
        "total": len(all_alerts),
        "open": sum(1 for alert in all_alerts if alert.status == "Open"),
        "closed": sum(1 for alert in all_alerts if alert.status != "Open"),
        "critical": sum(1 for alert in all_alerts if alert.severity == AlertSeverity.CRITICAL),
        "warning": sum(1 for alert in all_alerts if alert.severity == AlertSeverity.WARNING),
        "normal": sum(1 for alert in all_alerts if alert.severity == AlertSeverity.INFO),
    }

    completed_work_orders = [
        work_order for work_order in all_work_orders
        if status_value(work_order.status) == WorkOrderStatus.COMPLETED.value
    ]
    pending_work_orders = [
        work_order for work_order in all_work_orders
        if status_value(work_order.status) in (WorkOrderStatus.OPEN.value, WorkOrderStatus.IN_PROGRESS.value)
    ]
    repair_durations = [log.duration_hours for log in all_logs if log.duration_hours > 0]
    maintenance_fallback = {
        "total_work_orders": len(all_work_orders),
        "completed": len(completed_work_orders),
        "pending": len(pending_work_orders),
        "average_repair_time": round(sum(repair_durations) / len(repair_durations), 1) if repair_durations else 0,
        "downtime": round(sum(log.duration_hours for log in all_logs), 1),
        "maintenance_cost": round(sum(log.cost for log in all_logs), 2),
    }

    fleet = (
        data.get("fleet_summary")
        or data.get("fleet_performance")
        or data.get("fleet_health")
        or {}
    )
    if not isinstance(fleet, dict):
        fleet = {}

    total_machines = _first_present(data, "total_machines", "machine_count", default=fleet.get("total_machines", fleet_fallback["total_machines"]))
    healthy = _first_present(data, "normal_count", "healthy", default=fleet.get("healthy", fleet_fallback["healthy"]))
    warning = _first_present(data, "warning_count", "warning", default=fleet.get("warning", fleet_fallback["warning"]))
    critical = _first_present(data, "critical_count", "critical", default=fleet.get("critical", fleet_fallback["critical"]))
    avg_health = _first_present(data, "average_health", "average_health_score", default=fleet.get("average_health", fleet_fallback["average_health"]))
    avg_failure = _first_present(data, "average_failure_probability", default=fleet.get("average_failure_probability", fleet_fallback["average_failure_probability"]))

    if "machine_information" in data:
        machine = data["machine_information"]
        total_machines = 1
        healthy = 1 if data.get("status") == "NORMAL" else 0
        warning = 1 if data.get("status") == "WARNING" else 0
        critical = 1 if data.get("status") == "CRITICAL" else 0
        avg_health = data.get("health", data.get("health_score", ""))
        avg_failure = data.get("failure_probability", "")
        if number_value(avg_failure) <= 1:
            avg_failure = number_value(avg_failure) * 100
        display_title = f"Enterprise Predictive Maintenance Report - {machine.get('machine_id', '')}"

    period = (
        data.get("report_period")
        or data.get("report_date")
        or (f"Last {data.get('period_days')} Days" if data.get("period_days") else "Current reporting period")
    )

    categories = (
        data.get("category_summary")
        or data.get("category_comparison")
        or data.get("category_performance")
        or category_fallback
    )
    if not categories and data.get("category"):
        categories = [{
            "category": data.get("category"),
            "machine_count": data.get("machine_count", data.get("total_machines", "")),
            "healthy": data.get("healthy", ""),
            "warning": data.get("warning", ""),
            "critical": data.get("critical", ""),
            "average_health": data.get("average_health", "")
        }]

    risk_machines = (
        data.get("top_risk_machines")
        or data.get("high_risk_machines")
        or data.get("critical_machines")
        or data.get("warning_machines")
        or data.get("predictions")
        or data.get("machine_health_summary")
        or top_risk_fallback
    )
    if isinstance(risk_machines, list):
        risk_machines = sorted(
            risk_machines,
            key=lambda row: number_value(row.get("failure_probability", 0)),
            reverse=True
        )[:10]
    else:
        risk_machines = []

    alert_stats = data.get("alert_statistics") or {}
    alerts = data.get("alerts") or data.get("alert_history") or data.get("open_alerts") or data.get("recent_alerts") or []
    total_alerts = data.get("total_alerts", alert_stats.get("total", len(alerts) if isinstance(alerts, list) and alerts else alert_fallback["total"]))
    open_alerts = alert_stats.get("open", len(data.get("open_alerts", [])) if isinstance(data.get("open_alerts"), list) and data.get("open_alerts") else alert_fallback["open"])
    closed_alerts = alert_stats.get("closed", data.get("resolved_alerts", alert_fallback["closed"]))
    severity = data.get("alerts_by_severity") or {
        "critical": alert_stats.get("critical", alert_fallback["critical"]),
        "warning": alert_stats.get("warning", alert_fallback["warning"]),
        "normal": alert_stats.get("info", alert_fallback["normal"])
    }

    work_orders = data.get("work_order_statistics") or data.get("work_orders_by_status") or {}
    maintenance = data.get("maintenance_statistics") or data.get("maintenance_summary") or {}
    total_work_orders = work_orders.get("total", maintenance_fallback["total_work_orders"])
    completed = work_orders.get("completed", _first_present(data, "completed_work_orders", "maintenance_completed", default=maintenance_fallback["completed"]))
    pending = work_orders.get("open", data.get("pending_jobs", maintenance_fallback["pending"]))
    if isinstance(pending, list):
        pending = len(pending)
    avg_repair = _first_present(data, "average_repair_time", "mttr", default=maintenance_fallback["average_repair_time"])
    downtime = _first_present(data, "downtime", "total_downtime", "total_hours", default=maintenance.get("total_downtime", maintenance_fallback["downtime"]))
    cost = _first_present(data, "maintenance_cost", "total_maintenance_cost", "total_cost", default=maintenance.get("total_cost", maintenance_fallback["maintenance_cost"]))
    if number_value(avg_repair) == 0 and maintenance_fallback["average_repair_time"]:
        avg_repair = maintenance_fallback["average_repair_time"]
    if number_value(downtime) == 0 and maintenance_fallback["downtime"]:
        downtime = maintenance_fallback["downtime"]
    if number_value(cost) == 0 and maintenance_fallback["maintenance_cost"]:
        cost = maintenance_fallback["maintenance_cost"]

    recommendations = data.get("recommendations") or []
    if isinstance(recommendations, str):
        recommendations = [recommendations]
    if not recommendations:
        recommendations = []
        if critical not in ("", 0):
            recommendations.append("Prioritize immediate corrective maintenance for critical equipment.")
        if warning not in ("", 0):
            recommendations.append("Schedule preventive service for machines currently in warning condition.")
        if avg_failure not in ("", 0) and number_value(avg_failure) > 30:
            recommendations.append("Increase inspection frequency for equipment with elevated failure probability.")
        if cost not in ("", 0):
            recommendations.append("Review maintenance spend and isolate recurring cost drivers.")
        recommendations.append("Continue routine monitoring and close open work orders on schedule.")
    recommendations = recommendations[:6]

    return {
        "title": display_title,
        "generated_at": generated_at[:19].replace("T", " "),
        "period": period,
        "summary": [
            ("Total Machines", fmt_count(total_machines)),
            ("Healthy", fmt_count(healthy)),
            ("Warning", fmt_count(warning)),
            ("Critical", fmt_count(critical)),
            ("Average Health", fmt_percent(avg_health)),
            ("Average Failure Probability", fmt_percent(avg_failure)),
        ],
        "category_rows": [
            {
                "Category": row.get("category", row.get("name", "")),
                "Machines": fmt_count(row.get("machine_count", row.get("total_machines", 0))),
                "Healthy": fmt_count(row.get("healthy", 0)),
                "Warning": fmt_count(row.get("warning", 0)),
                "Critical": fmt_count(row.get("critical", 0)),
                "Avg Health": fmt_percent(row.get("average_health", 0)),
            }
            for row in categories[:12]
        ],
        "risk_rows": [
            {
                "Machine ID": row.get("machine_id", ""),
                "Machine Name": row.get("machine_name", row.get("name", "")),
                "Category": row.get("category", row.get("type", "")),
                "Health Score": fmt_percent(row.get("health_score", 0)),
                "Failure Probability": fmt_percent(row.get("failure_probability", 0)),
                "Condition": row.get("status", row.get("condition", "")),
            }
            for row in risk_machines
        ],
        "alerts": [
            ("Total Alerts", fmt_count(total_alerts)),
            ("Open Alerts", fmt_count(open_alerts)),
            ("Closed Alerts", fmt_count(closed_alerts)),
            ("Critical", fmt_count(severity.get("critical", severity.get("CRITICAL", 0)))),
            ("Warning", fmt_count(severity.get("warning", severity.get("WARNING", 0)))),
            ("Normal", fmt_count(severity.get("normal", severity.get("info", severity.get("INFO", 0))))),
        ],
        "maintenance": [
            ("Total Work Orders", fmt_count(total_work_orders)),
            ("Completed", fmt_count(completed)),
            ("Pending", fmt_count(pending)),
            ("Average Repair Time", fmt_hours(avg_repair)),
            ("Downtime", fmt_hours(downtime)),
            ("Maintenance Cost", fmt_currency(cost)),
        ],
        "recommendations": recommendations,
    }


def _generic_pdf_bytes(title: str, generated_at: str, data: Dict[str, Any]) -> bytes:
    sections = _report_sections(title, generated_at, data)
    try:
        from fpdf import FPDF

        def clean(value: Any) -> str:
            return str(value).encode("latin-1", "replace").decode("latin-1")

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.set_font("Arial", "B", 15)
        pdf.cell(0, 9, clean(sections["title"]), ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 7, clean(f"Generated On: {sections['generated_at']}"), ln=True)
        pdf.cell(0, 7, clean(f"Report Period: {sections['period']}"), ln=True)
        pdf.ln(3)

        def heading(text: str):
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, clean(text), ln=True)
            pdf.set_font("Arial", "", 9)

        def key_value_table(rows: List[tuple]):
            for label, value in rows:
                pdf.cell(65, 7, clean(label), border=1)
                pdf.cell(0, 7, clean(value), border=1, ln=True)
            pdf.ln(3)

        def data_table(rows: List[Dict[str, Any]], columns: List[str]):
            if not rows:
                pdf.cell(0, 7, "No records available", border=1, ln=True)
                pdf.ln(3)
                return
            widths = [28, 28, 22, 22, 22, 32][:len(columns)]
            if len(columns) == 6 and columns[0] == "Machine ID":
                widths = [25, 42, 32, 25, 35, 28]
            pdf.set_font("Arial", "B", 8)
            for col, width in zip(columns, widths):
                pdf.cell(width, 7, clean(col), border=1)
            pdf.ln()
            pdf.set_font("Arial", "", 8)
            for row in rows:
                for col, width in zip(columns, widths):
                    pdf.cell(width, 7, clean(row.get(col, ""))[:24], border=1)
                pdf.ln()
            pdf.ln(3)

        heading("Executive Summary")
        key_value_table(sections["summary"])
        heading("Category Summary")
        data_table(sections["category_rows"], ["Category", "Machines", "Healthy", "Warning", "Critical", "Avg Health"])
        heading("Top Risk Machines")
        data_table(sections["risk_rows"], ["Machine ID", "Machine Name", "Category", "Health Score", "Failure Probability", "Condition"])
        heading("Alert Summary")
        key_value_table(sections["alerts"])
        heading("Maintenance Summary")
        key_value_table(sections["maintenance"])
        heading("Recommendations")
        pdf.ln(2)
        for item in sections["recommendations"]:
            text = clean(str(item))
            _safe_pdf_multi_cell(pdf, f"- {text}", height=6)

        output = pdf.output(dest="S")
        return bytes(output) if isinstance(output, bytearray) else output.encode("latin-1")
    except ImportError:
        lines = [
            sections["title"],
            f"Generated On: {sections['generated_at']}",
            f"Report Period: {sections['period']}",
            "",
            "Executive Summary",
        ]
        lines.extend(f"{label}: {value}" for label, value in sections["summary"])
        lines.extend(["", "Category Summary"])
        lines.extend(" | ".join(str(row.get(col, "")) for col in ["Category", "Machines", "Healthy", "Warning", "Critical", "Avg Health"]) for row in sections["category_rows"])
        lines.extend(["", "Top Risk Machines"])
        lines.extend(" | ".join(str(row.get(col, "")) for col in ["Machine ID", "Machine Name", "Category", "Health Score", "Failure Probability", "Condition"]) for row in sections["risk_rows"])
        lines.extend(["", "Alert Summary"])
        lines.extend(f"{label}: {value}" for label, value in sections["alerts"])
        lines.extend(["", "Maintenance Summary"])
        lines.extend(f"{label}: {value}" for label, value in sections["maintenance"])
        lines.extend(["", "Recommendations"])
        lines.extend(f"- {item}" for item in sections["recommendations"])
        return _text_pdf_bytes(lines)


def _report_xml_bytes(title: str, generated_at: str, data: Dict[str, Any]) -> bytes:
    import html

    sections = _report_sections(title, generated_at, data)

    def metrics_xml(name: str, rows: List[tuple]) -> List[str]:
        xml = [f"  <section name=\"{html.escape(name)}\">"]
        for label, value in rows:
            xml.extend([
                "    <metric>",
                f"      <name>{html.escape(str(label))}</name>",
                f"      <value>{html.escape(str(value))}</value>",
                "    </metric>"
            ])
        xml.append("  </section>")
        return xml

    def table_xml(name: str, rows: List[Dict[str, Any]]) -> List[str]:
        xml = [f"  <section name=\"{html.escape(name)}\">"]
        for row in rows:
            xml.append("    <row>")
            for key, value in row.items():
                tag = re.sub(r"[^A-Za-z0-9_]+", "_", key.strip().lower()).strip("_") or "value"
                xml.append(f"      <{tag}>{html.escape(str(value))}</{tag}>")
            xml.append("    </row>")
        xml.append("  </section>")
        return xml

    rows = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<report>",
        f"  <title>{html.escape(sections['title'])}</title>",
        f"  <generated_on>{html.escape(sections['generated_at'])}</generated_on>",
        f"  <report_period>{html.escape(str(sections['period']))}</report_period>",
    ]
    rows.extend(metrics_xml("Executive Summary", sections["summary"]))
    rows.extend(table_xml("Category Summary", sections["category_rows"]))
    rows.extend(table_xml("Top Risk Machines", sections["risk_rows"]))
    rows.extend(metrics_xml("Alert Summary", sections["alerts"]))
    rows.extend(metrics_xml("Maintenance Summary", sections["maintenance"]))
    rows.append("  <section name=\"Recommendations\">")
    for item in sections["recommendations"]:
        rows.append(f"    <recommendation>{html.escape(str(item))}</recommendation>")
    rows.extend(["  </section>", "</report>"])
    return "\n".join(rows).encode("utf-8")


def _report_docx_bytes(title: str, generated_at: str, data: Dict[str, Any]) -> bytes:
    import html

    sections = _report_sections(title, generated_at, data)

    def paragraph(text: str, bold: bool = False) -> str:
        props = "<w:rPr><w:b/></w:rPr>" if bold else ""
        return f"<w:p><w:r>{props}<w:t>{html.escape(str(text))}</w:t></w:r></w:p>"

    def table(rows: List[List[Any]]) -> str:
        cells = []
        for row in rows:
            cell_xml = "".join(
                "<w:tc><w:tcPr><w:tcBorders>"
                "<w:top w:val=\"single\" w:sz=\"4\"/><w:left w:val=\"single\" w:sz=\"4\"/>"
                "<w:bottom w:val=\"single\" w:sz=\"4\"/><w:right w:val=\"single\" w:sz=\"4\"/>"
                "</w:tcBorders></w:tcPr>"
                f"{paragraph(value)}</w:tc>"
                for value in row
            )
            cells.append(f"<w:tr>{cell_xml}</w:tr>")
        return f"<w:tbl><w:tblPr><w:tblBorders><w:top w:val=\"single\" w:sz=\"4\"/><w:left w:val=\"single\" w:sz=\"4\"/><w:bottom w:val=\"single\" w:sz=\"4\"/><w:right w:val=\"single\" w:sz=\"4\"/><w:insideH w:val=\"single\" w:sz=\"4\"/><w:insideV w:val=\"single\" w:sz=\"4\"/></w:tblBorders></w:tblPr>{''.join(cells)}</w:tbl>"

    body = [
        paragraph(sections["title"], bold=True),
        paragraph(f"Generated On: {sections['generated_at']}"),
        paragraph(f"Report Period: {sections['period']}"),
        paragraph(""),
        paragraph("Executive Summary", bold=True),
        table([["Metric", "Value"]] + [[label, value] for label, value in sections["summary"]]),
        paragraph("Category Summary", bold=True),
        table([["Category", "Machines", "Healthy", "Warning", "Critical", "Avg Health"]] + [
            [row.get("Category", ""), row.get("Machines", ""), row.get("Healthy", ""), row.get("Warning", ""), row.get("Critical", ""), row.get("Avg Health", "")]
            for row in sections["category_rows"]
        ]),
        paragraph("Top Risk Machines", bold=True),
        table([["Machine ID", "Machine Name", "Category", "Health Score", "Failure Probability", "Condition"]] + [
            [row.get("Machine ID", ""), row.get("Machine Name", ""), row.get("Category", ""), row.get("Health Score", ""), row.get("Failure Probability", ""), row.get("Condition", "")]
            for row in sections["risk_rows"]
        ]),
        paragraph("Alert Summary", bold=True),
        table([["Metric", "Value"]] + [[label, value] for label, value in sections["alerts"]]),
        paragraph("Maintenance Summary", bold=True),
        table([["Metric", "Value"]] + [[label, value] for label, value in sections["maintenance"]]),
        paragraph("Recommendations", bold=True),
    ]
    body.extend(paragraph(f"- {item}") for item in sections["recommendations"])
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {''.join(body)}
    <w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
  </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("_rels/.rels", rels)
        docx.writestr("word/document.xml", document_xml)
    return output.getvalue()


def _download_generated_report(report: Any, key_context: str = ""):
    parts = _get_report_parts(report)
    title = parts["title"]
    generated_at = parts["generated_at"]
    data = parts["data"]
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_").lower() or "report"
    key_suffix = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        f"{key_context}_{parts['report_id']}_{safe_name}_{generated_at}"
    ).strip("_")
    file_cache = st.session_state.setdefault("report_download_file_cache", {})
    file_cache_key = f"{parts['report_id']}|{safe_name}|{generated_at}"
    if file_cache_key not in file_cache:
        file_cache[file_cache_key] = {
            "pdf": _generic_pdf_bytes(title, generated_at, data),
            "docx": _report_docx_bytes(title, generated_at, data),
            "xml": _report_xml_bytes(title, generated_at, data),
        }
    files = file_cache[file_cache_key]

    st.success(f"{title} Generated Successfully")
    st.markdown("Download:")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "📄 PDF",
            data=files["pdf"],
            file_name=f"{safe_name}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=f"report_pdf_{key_suffix}"
        )
    with col2:
        st.download_button(
            "📝 DOCX",
            data=files["docx"],
            file_name=f"{safe_name}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key=f"report_docx_{key_suffix}"
        )
    with col3:
        st.download_button(
            "🗂 XML",
            data=files["xml"],
            file_name=f"{safe_name}.xml",
            mime="application/xml",
            use_container_width=True,
            key=f"report_xml_{key_suffix}"
        )


def _report_with_scope(report: Any, selected_category: str = "", selected_machine_id: str = "") -> Dict[str, Any]:
    parts = _get_report_parts(report)
    data = dict(parts["data"])
    scope_machine_id = selected_machine_id or ""
    scope_category = selected_category or ""
    data["report_scope"] = {
        "machine_id": scope_machine_id,
        "category_id": scope_category,
    }

    machines = simulator.get_all_machines()
    if scope_machine_id:
        machines = [machine for machine in machines if machine.machine_id == scope_machine_id]
    elif scope_category:
        factories = simulator.get_all_factories()
        category_name = factories.get(scope_category, {}).get("name", scope_category)
        category_text = str(scope_category).strip().lower().replace("_", " ")
        category_name_text = str(category_name).strip().lower().replace("_", " ")
        machines = [
            machine for machine in machines
            if str(machine.factory_id).strip().lower().replace("_", " ") in (category_text, category_name_text)
            or str(machine.machine_category).strip().lower().replace("_", " ") in (category_text, category_name_text)
        ]

    machine_ids = {machine.machine_id for machine in machines}
    alerts = [alert for alert in data_store.alert_service.get_all_alerts() if alert.machine_id in machine_ids]
    work_orders = [work_order for work_order in data_store.work_order_service.get_all_work_orders() if work_order.machine_id in machine_ids]
    logs = [log for log in data_store.maintenance_log_service.get_all_logs() if log.machine_id in machine_ids]

    def status_value(value: Any) -> str:
        return getattr(value, "value", value)

    data.update({
        "total_machines": len(machines),
        "normal_count": sum(1 for machine in machines if machine.status == MachineStatus.NORMAL),
        "warning_count": sum(1 for machine in machines if machine.status == MachineStatus.WARNING),
        "critical_count": sum(1 for machine in machines if machine.status == MachineStatus.CRITICAL),
        "average_health": round(sum(machine.health_score for machine in machines) / len(machines), 1) if machines else 0,
        "average_failure_probability": round(sum(machine.failure_probability for machine in machines) / len(machines) * 100, 1) if machines else 0,
    })

    category_summary = []
    for category_name in sorted({machine.machine_category for machine in machines}):
        category_machines = [machine for machine in machines if machine.machine_category == category_name]
        category_summary.append({
            "category": category_name,
            "machine_count": len(category_machines),
            "healthy": sum(1 for machine in category_machines if machine.status == MachineStatus.NORMAL),
            "warning": sum(1 for machine in category_machines if machine.status == MachineStatus.WARNING),
            "critical": sum(1 for machine in category_machines if machine.status == MachineStatus.CRITICAL),
            "average_health": round(sum(machine.health_score for machine in category_machines) / len(category_machines), 1) if category_machines else 0,
        })
    data["category_summary"] = category_summary
    data["top_risk_machines"] = [
        {
            "machine_id": machine.machine_id,
            "machine_name": machine.name,
            "category": machine.machine_category,
            "health_score": machine.health_score,
            "failure_probability": round(machine.failure_probability * 100, 1),
            "status": machine.status.value,
        }
        for machine in sorted(machines, key=lambda item: item.failure_probability, reverse=True)[:10]
    ]

    data["alert_statistics"] = {
        "total": len(alerts),
        "open": sum(1 for alert in alerts if alert.status == "Open"),
        "closed": sum(1 for alert in alerts if alert.status != "Open"),
        "critical": sum(1 for alert in alerts if alert.severity == AlertSeverity.CRITICAL),
        "warning": sum(1 for alert in alerts if alert.severity == AlertSeverity.WARNING),
        "info": sum(1 for alert in alerts if alert.severity == AlertSeverity.INFO),
    }
    data["work_order_statistics"] = {
        "total": len(work_orders),
        "open": sum(1 for work_order in work_orders if status_value(work_order.status) == WorkOrderStatus.OPEN.value),
        "in_progress": sum(1 for work_order in work_orders if status_value(work_order.status) == WorkOrderStatus.IN_PROGRESS.value),
        "completed": sum(1 for work_order in work_orders if status_value(work_order.status) == WorkOrderStatus.COMPLETED.value),
        "cancelled": sum(1 for work_order in work_orders if status_value(work_order.status) == WorkOrderStatus.CANCELLED.value),
    }

    durations = [log.duration_hours for log in logs if log.duration_hours > 0]
    maintenance_cost = round(sum(log.cost for log in logs), 2)
    downtime = round(sum(log.duration_hours for log in logs), 1)
    data["maintenance_statistics"] = {
        "total_events": len(logs),
        "total_cost": maintenance_cost,
        "total_downtime": downtime,
        "average_duration": round(sum(durations) / len(durations), 1) if durations else 0,
    }
    data["average_repair_time"] = data["maintenance_statistics"]["average_duration"]
    data["downtime"] = downtime
    data["maintenance_cost"] = maintenance_cost
    data["maintenance_logs"] = [log.to_dict() for log in logs]

    if "predictions" in data:
        data["predictions"] = [row for row in data.get("predictions", []) if row.get("machine_id") in machine_ids]
        data["total_predictions"] = len(data["predictions"])
        data["high_risk_count"] = len([row for row in data["predictions"] if float(row.get("failure_probability", 0) or 0) > 50])
        data["medium_risk_count"] = len([row for row in data["predictions"] if 20 < float(row.get("failure_probability", 0) or 0) <= 50])
        data["low_risk_count"] = len([row for row in data["predictions"] if float(row.get("failure_probability", 0) or 0) <= 20])
        data["failure_probability_distribution"] = {
            "high_risk": data["high_risk_count"],
            "medium_risk": data["medium_risk_count"],
            "low_risk": data["low_risk_count"],
        }
    if "high_risk_machines" in data:
        data["high_risk_machines"] = [row for row in data.get("high_risk_machines", []) if row.get("machine_id") in machine_ids]
    if "completed_jobs" in data:
        data["completed_jobs"] = [row for row in data.get("completed_jobs", []) if row.get("machine_id") in machine_ids]
    if "pending_jobs" in data:
        data["pending_jobs"] = [row for row in data.get("pending_jobs", []) if row.get("machine_id") in machine_ids]

    data["recommendations"] = []
    if data["critical_count"]:
        data["recommendations"].append("Prioritize immediate corrective maintenance for critical equipment in the selected scope.")
    if data["warning_count"]:
        data["recommendations"].append("Schedule preventive service for warning machines in the selected scope.")
    if data["average_failure_probability"] > 30:
        data["recommendations"].append("Increase monitoring frequency for equipment with elevated failure probability.")
    if maintenance_cost:
        data["recommendations"].append("Review maintenance spend for the selected scope and isolate recurring cost drivers.")
    data["recommendations"].append("Continue routine monitoring and close open work orders on schedule.")

    return {
        "report_id": parts["report_id"],
        "report_type": parts["report_type"],
        "title": parts["title"],
        "generated_at": parts["generated_at"],
        "data": data,
    }


def _generate_report_with_downloads(cache_key: str, generate_report):
    report_cache = st.session_state.setdefault("generated_report_cache", {})
    if cache_key in report_cache:
        _download_generated_report(report_cache[cache_key], key_context=cache_key)
        return

    st.info("Generating Report...")
    with st.spinner("Generating Report..."):
        report = generate_report()
        report_cache[cache_key] = report
    _download_generated_report(report, key_context=cache_key)


def _download_generic_report_buttons(title: str, generated_at: str, data: Dict[str, Any], key_context: str = ""):
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_").lower() or "report"
    key_suffix = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{key_context}_{safe_name}_{generated_at}").strip("_")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Download PDF",
            data=_generic_pdf_bytes(title, generated_at, data),
            file_name=f"{safe_name}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=f"pdf_{key_suffix}"
        )
    with col2:
        st.download_button(
            "Download Excel",
            data=_generic_excel_bytes(title, generated_at, data),
            file_name=f"{safe_name}.xls",
            mime="application/vnd.ms-excel",
            use_container_width=True,
            key=f"excel_{key_suffix}"
        )
    with col3:
        st.download_button(
            "Download CSV",
            data=_generic_csv_bytes(title, generated_at, data),
            file_name=f"{safe_name}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"csv_{key_suffix}"
        )


def _render_daily_report(report: Any, key_context: str = ""):
    parts = _get_report_parts(report)
    data = parts["data"]
    report_date = data.get("report_date", parts["generated_at"][:10])
    fleet_summary, attention = _daily_report_tables(data)
    summary = _daily_ai_summary(data, len(attention))

    st.subheader(parts["title"])
    st.caption(f"Report Date: {report_date}")
    st.markdown("#### Fleet Summary")
    st.dataframe(fleet_summary, use_container_width=True, hide_index=True)
    st.markdown("#### Machines Requiring Attention")
    if attention.empty:
        st.info("No warning or critical machines.")
    else:
        for _, row in attention.iterrows():
            col_a, col_b, col_c, col_d, col_e = st.columns([1.2, 2, 1.5, 1.5, 0.8])
            with col_a:
                st.markdown(f"<span style='color:#4da6ff;font-weight:500;'>{row['Machine ID']}</span>", unsafe_allow_html=True)
            with col_b:
                st.markdown(f"<span style='color:#ccc;'>{row['Machine Name']}</span>", unsafe_allow_html=True)
            with col_c:
                st.markdown(f"<span style='color:#888;'>{row['Category']} | {row['Health Score']}</span>", unsafe_allow_html=True)
            with col_d:
                status_color = STATUS_COLORS.get(row['Status'], "#888")
                st.markdown(f"<span style='color:{status_color};font-weight:bold;'>{row['Status']}</span>", unsafe_allow_html=True)
            with col_e:
                if st.button("View", key=f"report_attention_{key_context}_{row['Machine ID']}", use_container_width=True):
                    navigate_to_machine(row['Machine ID'])
                    st.rerun()
    st.markdown("#### AI Summary")
    st.write(summary)
    _download_report_buttons(parts["title"], report_date, fleet_summary, attention, summary, key_context)


def _render_business_report(report: Any, key_context: str = ""):
    parts = _get_report_parts(report)
    data = parts["data"]
    if parts["report_type"] == "daily" or "report_date" in data:
        _render_daily_report(report, key_context)
        return

    st.subheader(parts["title"])
    st.caption(f"Generated: {parts['generated_at'][:19].replace('T', ' ')}")
    scalar_rows = [
        {"Metric": key.replace("_", " ").title(), "Value": value}
        for key, value in data.items()
        if not isinstance(value, (dict, list))
    ]
    if scalar_rows:
        st.dataframe(pd.DataFrame(scalar_rows), use_container_width=True, hide_index=True)
    for key, value in data.items():
        if isinstance(value, list):
            st.markdown(f"#### {key.replace('_', ' ').title()}")
            st.dataframe(pd.DataFrame(value if value and isinstance(value[0], dict) else {key: value}), use_container_width=True, hide_index=True)
        elif isinstance(value, dict):
            st.markdown(f"#### {key.replace('_', ' ').title()}")
            st.dataframe(pd.DataFrame(_report_data_rows(value)), use_container_width=True, hide_index=True)
    _download_generic_report_buttons(parts["title"], parts["generated_at"], data, key_context)


def render_reports():
    """Render reports page."""
    st.markdown("<h1 class='main-header'>📈 Reports</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.subheader("Quick Reports")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📅 Generate Daily Report", use_container_width=True):
            _generate_report_with_downloads(
                "daily_report",
                report_generator.generate_daily_report
            )
    
    with col2:
        if st.button("📆 Generate Weekly Report", use_container_width=True):
            _generate_report_with_downloads(
                "weekly_report",
                report_generator.generate_weekly_report
            )
    
    with col3:
        if st.button("📊 Generate Monthly Report", use_container_width=True):
            _generate_report_with_downloads(
                "monthly_report",
                report_generator.generate_monthly_report
            )
    
    st.markdown("---")
    
    with st.container(border=True):
        st.subheader("Custom Reports")
        left_col, right_col = st.columns([1, 1], gap="large")
        
        with left_col:
            factories = simulator.get_all_factories()
            category_options = list(factories.keys())
            selected_category = st.selectbox(
                "Category",
                category_options,
                format_func=lambda fid: factories[fid].get("name", fid),
                key="machine_report_category"
            )
            category_machines = simulator.get_factory_machines(selected_category) if selected_category else []
            machine_lookup = {machine.machine_id: machine for machine in category_machines}
            machine_options = [""] + list(machine_lookup.keys())
            selected_machine_id = st.selectbox(
                "Machine",
                machine_options,
                format_func=lambda mid: (
                    "Select Machine" if not mid
                    else f"{mid} - {machine_lookup[mid].name}"
                ),
                key="machine_report_machine"
            )
            if st.button("⚙️ Machine Report", use_container_width=True):
                if not selected_machine_id:
                    st.warning("Select a machine to generate a machine report.")
                else:
                    _generate_report_with_downloads(
                        f"machine_report_{selected_machine_id}",
                        lambda: _report_with_scope(
                            report_generator.generate_machine_report(selected_machine_id),
                            selected_category,
                            selected_machine_id
                        )
                    )
    
        with right_col:
            if st.button("🏷️ Category Report", use_container_width=True):
                _generate_report_with_downloads(
                    f"category_report_{selected_category}",
                    lambda: report_generator.generate_factory_report(selected_category)
                )
            
            if st.button("🔮 Prediction Report", use_container_width=True):
                _generate_report_with_downloads(
                    f"prediction_report_{selected_machine_id or selected_category}",
                    lambda: _report_with_scope(
                        report_generator.generate_prediction_report(),
                        selected_category,
                        selected_machine_id
                    )
                )

            if st.button("Maintenance Report", use_container_width=True):
                _generate_report_with_downloads(
                    f"maintenance_report_{selected_machine_id or selected_category}",
                    lambda: _report_with_scope(
                        report_generator.generate_maintenance_report(),
                        selected_category,
                        selected_machine_id
                    )
                )
    
    st.markdown("---")
    
    # Recent reports
    st.subheader("📋 Recent Reports")
    recent = report_generator.get_recent_reports(5)
    if recent:
        for idx, r in enumerate(recent):
            with st.expander(f"{r['title']} ({r['generated_at'][:10]})"):
                _download_generated_report(r, key_context=f"history_{r.get('report_type', 'report')}_{r.get('report_id', idx)}_{idx}")
    else:
        st.info("No reports generated yet.")


# ==================== COPILOT PAGE ====================

def render_copilot():
    """Render AI Copilot chat interface."""
    st.markdown("<h1 class='main-header'>🤖 Enterprise Maintenance Copilot</h1>", unsafe_allow_html=True)
    st.markdown("Ask questions about your entire equipment fleet.")
    st.markdown("---")
    
    # Example questions
    with st.expander("💡 Example Questions"):
        st.markdown("""
        - "Show all critical machines"
        - "Which machine has the highest vibration?"
        - "Show all generators"
        - "Why is GEN-002 unhealthy?"
        - "Compare REF-001 and REF-004"
        - "What maintenance is due today?"
        - "Explain today's alerts"
        - "Which machine failed most frequently?"
        - "Generate today's maintenance report"
        - "Show me all refrigerators"
        - "What's the overall enterprise status?"
        """)
    
    # Chat interface
    chat_container = st.container()
    
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    prompt = st.chat_input("Ask the Enterprise Copilot...", key="copilot_input")
    
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing enterprise data..."):
                response = copilot.answer(prompt)
                st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
    
    # Clear chat button
    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.rerun()


# ==================== MAINTENANCE LOGS PAGE - ENHANCED ====================

def render_maintenance_logs():
    """Render maintenance logs page with Category Summary Cards at the top.
    
    This function adds Premium Category Summary Cards above the existing
    maintenance logs table. Clicking a card navigates to a Category Details page
    showing only machines belonging to that category, with checkboxes for selection.
    Selecting a machine shows summary stats and maintenance history.
    
    Does NOT modify any existing Enterprise Tables or UI components.
    """
    # Determine which sub-page to show
    maint_page = st.session_state.get("maintenance_page", "overview")
    maint_category = st.session_state.get("maintenance_category", None)
    maint_machine = st.session_state.get("maintenance_selected_machine", None)
    
    if maint_page == "machine_summary" and maint_machine:
        render_maintenance_machine_summary()
        return
    
    if maint_page == "category_detail" and maint_category:
        render_category_machine_list()
        return
    
    # === MAIN OVERVIEW PAGE ===
    st.markdown("<h1 class='main-header'>📝 Maintenance Logs</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    # ==================== CATEGORY OVERVIEW KPI CARDS (top row, non-clickable) ====================
    all_logs = data_store.maintenance_log_service.get_all_logs()
    all_machines = simulator.get_all_machines()
    machine_map = {m.machine_id: m for m in all_machines}
    
    from maintenance_logs_enhanced import compute_all_category_summaries
    all_category_summaries = compute_all_category_summaries(all_logs, all_machines)
    
    # ==================== OVERALL MAINTENANCE SUMMARY ====================
    total_logs = sum(s['total_logs'] for s in all_category_summaries)
    total_completed = sum(s['completed_logs'] for s in all_category_summaries)
    total_pending = sum(s['pending_logs'] for s in all_category_summaries)
    total_cost = sum(s['total_cost'] for s in all_category_summaries)
    
    st.markdown("### 📊 Overall Maintenance Summary")
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.markdown(
            "<div class='summary-section' style='text-align:center;'>"
            f"<div class='summary-stat-value'>{total_logs}</div>"
            "<div class='summary-stat-label'>Total Logs</div>"
            "</div>",
            unsafe_allow_html=True
        )
    with col_s2:
        st.markdown(
            "<div class='summary-section' style='text-align:center;'>"
            f"<div class='summary-stat-value' style='color:#44CC44'>{total_completed}</div>"
            "<div class='summary-stat-label'>Completed Logs</div>"
            "</div>",
            unsafe_allow_html=True
        )
    with col_s3:
        st.markdown(
            "<div class='summary-section' style='text-align:center;'>"
            f"<div class='summary-stat-value' style='color:#FFAA00'>{total_pending}</div>"
            "<div class='summary-stat-label'>Pending Logs</div>"
            "</div>",
            unsafe_allow_html=True
        )
    with col_s4:
        st.markdown(
            "<div class='summary-section' style='text-align:center;'>"
            f"<div class='summary-stat-value' style='color:#4da6ff'>₹{total_cost:,.0f}</div>"
            "<div class='summary-stat-label'>Total Cost</div>"
            "</div>",
            unsafe_allow_html=True
        )
    
    # ==================== 1. CATEGORY SUMMARY CARDS (clickable) ====================
    if all_category_summaries:
        st.markdown("### 📊 Category Summary")
        cols = st.columns(min(5, len(all_category_summaries)))
        for idx, summary in enumerate(all_category_summaries):
            with cols[idx % len(cols)]:
                category = summary["category"]
                # Render card as HTML (not in button label, which escapes HTML)
                st.markdown(f"""
                <div class='category-card'>
                    <div class='category-card-title'>{category}</div>
                    <div class='category-card-stat'>Total Logs: <span>{summary['total_logs']}</span></div>
                    <div class='category-card-stat'>Completed: <span style='color:#44CC44'>{summary['completed_logs']}</span></div>
                    <div class='category-card-stat'>Pending: <span style='color:#FFAA00'>{summary['pending_logs']}</span></div>
                    <div class='category-card-cost'>₹{summary['total_cost']:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"View {category}", key=f"cat_card_{idx}", use_container_width=True):
                    st.session_state.maintenance_category = category
                    st.session_state.maintenance_page = "category_detail"
                    st.session_state.maintenance_selected_machine = None
                    st.rerun()
        st.markdown("---")
    
    # ==================== EXISTING MAINTENANCE LOGS TABLE (hidden while category cards are showing) ====================
    if not all_category_summaries:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            logs = sorted(all_logs, key=lambda l: l.maintenance_date, reverse=True)
            categories = sorted({machine_map[log.machine_id].machine_category for log in logs if log.machine_id in machine_map})
            technicians = sorted({log.technician for log in logs})
            maintenance_types = sorted({log.maintenance_type.value for log in logs})
            statuses = sorted({getattr(log, "status", "Completed") for log in logs})
            f1, f2, f3 = st.columns(3)
            with f1:
                selected_category = st.selectbox("Category", ["All"] + categories, key="maintenance_log_category_filter")
                selected_technician = st.selectbox("Technician", ["All"] + technicians, key="maintenance_log_technician_filter")
            with f2:
                selected_machine = st.selectbox("Machine", ["All"] + sorted({log.machine_id for log in logs}), key="maintenance_log_machine_filter")
                selected_type = st.selectbox("Maintenance Type", ["All"] + maintenance_types, key="maintenance_log_type_filter")
            with f3:
                selected_status = st.selectbox("Status", ["All"] + statuses, key="maintenance_log_status_filter")
                search_text = st.text_input("Search", key="maintenance_log_search")
        date_range = st.date_input("Date", value=[], key="maintenance_log_date_filter")
        filtered_logs = logs
        if selected_category != "All":
            filtered_logs = [log for log in filtered_logs if log.machine_id in machine_map and machine_map[log.machine_id].machine_category == selected_category]
        if selected_machine != "All":
            filtered_logs = [log for log in filtered_logs if log.machine_id == selected_machine]
        if selected_technician != "All":
            filtered_logs = [log for log in filtered_logs if log.technician == selected_technician]
        if selected_type != "All":
            filtered_logs = [log for log in filtered_logs if log.maintenance_type.value == selected_type]
        if selected_status != "All":
            filtered_logs = [log for log in filtered_logs if getattr(log, "status", "Completed") == selected_status]
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered_logs = [log for log in filtered_logs if start_date <= log.maintenance_date.date() <= end_date]
        if search_text:
            needle = search_text.lower()
            filtered_logs = [
                log for log in filtered_logs
                if needle in log.machine_id.lower()
                or needle in log.technician.lower()
                or needle in log.log_id.lower()
                or needle in getattr(log, "machine_name", "").lower()
            ]
        
        if not filtered_logs:
            st.info("No maintenance logs found.")
        else:
            for log in filtered_logs:
                machine = simulator.get_machine(log.machine_id)
                col_a, col_b, col_c, col_d, col_e, col_f, col_g = st.columns([0.8, 1, 1.2, 1.2, 0.8, 1, 0.8])
                with col_a:
                    st.markdown(f"<span style='color:#888;font-size:0.8rem;'>{log.maintenance_date.strftime('%m-%d %H:%M')}</span>", unsafe_allow_html=True)
                with col_b:
                    st.markdown(f"<span style='color:#4da6ff;font-weight:500;'>{log.machine_id}</span>", unsafe_allow_html=True)
                with col_c:
                    name = log.machine_name or (machine.name if machine else "N/A")
                    st.markdown(f"<span style='color:#ccc;font-size:0.85rem;'>{name}</span>", unsafe_allow_html=True)
                with col_d:
                    st.markdown(f"<span style='color:#aaa;font-size:0.85rem;'>{log.maintenance_type.value}</span>", unsafe_allow_html=True)
                with col_e:
                    st.markdown(f"<span style='color:#ddd;'>₹{log.cost:,.0f}</span>", unsafe_allow_html=True)
                with col_f:
                    st.markdown(f"<span style='color:#888;font-size:0.85rem;'>{log.technician}</span>", unsafe_allow_html=True)
                with col_g:
                    if st.button("🔍", key=f"log_view_{log.log_id}", use_container_width=True):
                        navigate_to_machine(log.machine_id)
                        st.rerun()
    
        with col2:
            st.metric("Total Logs", len(all_logs))
            completed_logs = [log for log in all_logs if getattr(log, "status", "Completed") == "Completed"]
            scheduled_logs = [log for log in all_logs if getattr(log, "status", "") == "Scheduled"]
            total_cost = sum(log.cost for log in completed_logs)
            total_hours = sum(log.duration_hours for log in completed_logs)
            avg_repair_time = round(total_hours / len(completed_logs), 1) if completed_logs else 0
            total_downtime = sum(getattr(log, "downtime_hours", log.duration_hours) for log in completed_logs)
            st.metric("Completed Jobs", len(completed_logs))
            st.metric("Scheduled Jobs", len(scheduled_logs))
            st.metric("Total Cost", f"₹{total_cost:,.2f}")
            st.metric("Total Hours", f"{total_hours:.1f}h")
            st.metric("Avg Repair Time", f"{avg_repair_time:.1f}h")
            st.metric("Downtime", f"{total_downtime:.1f}h")
            
            # Export
            if st.button("📥 Export Logs", use_container_width=True):
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["Log ID", "Date", "Machine", "Machine Name", "Category", "Type", "Technician", "Issue", "Cost", "Duration", "Downtime", "Before Health", "After Health", "Status"])
                export_rows = []
                for log in filtered_logs:
                    machine = simulator.get_machine(log.machine_id)
                    row = {
                        "Log ID": log.log_id,
                        "Date": log.maintenance_date.strftime("%Y-%m-%d %H:%M"),
                        "Machine": log.machine_id,
                        "Machine Name": log.machine_name or (machine.name if machine else "N/A"),
                        "Category": log.category or (machine.machine_category if machine else "N/A"),
                        "Type": log.maintenance_type.value,
                        "Technician": log.technician,
                        "Issue": log.issue,
                        "Cost": log.cost,
                        "Duration": log.duration_hours,
                        "Downtime": getattr(log, "downtime_hours", log.duration_hours),
                        "Before Health": getattr(log, "before_health", 0),
                        "After Health": getattr(log, "after_health", 0),
                        "Status": getattr(log, "status", "Completed")
                    }
                    export_rows.append(row)
                    writer.writerow([
                        row["Log ID"], row["Date"], row["Machine"], row["Machine Name"], row["Category"],
                        row["Type"], row["Technician"], row["Issue"], row["Cost"], row["Duration"],
                        row["Downtime"], row["Before Health"], row["After Health"], row["Status"]
                    ])
                report_name = f"maintenance_logs_{datetime.now().strftime('%Y%m%d')}"
                export_data = {"maintenance_logs": export_rows}
                st.download_button(
                    "Download PDF",
                    _generic_pdf_bytes("Maintenance Logs", datetime.now().isoformat(), export_data),
                    file_name=f"{report_name}.pdf",
                    mime="application/pdf",
                    key=f"pdf_{report_name}"
                )
                st.download_button(
                    "Download Excel",
                    _generic_excel_bytes("Maintenance Logs", datetime.now().isoformat(), export_data),
                    file_name=f"{report_name}.xls",
                    mime="application/vnd.ms-excel",
                    key=f"excel_{report_name}"
                )
                st.download_button(
                    "Download CSV",
                    output.getvalue(),
                    file_name=f"{report_name}.csv",
                    mime="text/csv",
                    key=f"csv_maintenance_logs_{datetime.now().strftime('%Y%m%d')}"
                )


def render_category_machine_list():
    """Render list of machines for a selected category with checkboxes.
    
    Does NOT use the existing Enterprise Table.
    Shows:
    1. Category Summary (Total Logs, Completed, Pending, Total Cost)
    2. Machine list as a proper table with ☐ Checkbox | Machine ID | Total Logs | Total Cost
    3. Machine Summary + Maintenance History when a machine is selected
    """
    category = st.session_state.maintenance_category
    if not category:
        st.session_state.maintenance_page = "overview"
        st.rerun()
        return
    
    st.markdown("<h1 class='main-header'>📝 Maintenance Logs</h1>", unsafe_allow_html=True)
    
    if came_from_analytics_chip("maintenance_logs"):
    
        if st.button("← Back to Analytics"):
    
            return_to_analytics_from_chip()

    
    if st.button("← Back to Maintenance Logs"):
        st.session_state.maintenance_page = "overview"
        st.session_state.maintenance_category = None
        st.session_state.maintenance_selected_machine = None
        st.rerun()
    
    st.markdown(f"### 🏷️ Category: {category}")
    st.markdown("---")
    
    all_logs = data_store.maintenance_log_service.get_all_logs()
    all_machines = simulator.get_all_machines()
    
    from maintenance_logs_enhanced import (
        get_machines_for_category, compute_machine_summary,
        compute_category_summary, get_maintenance_history
    )
    
    # Get machines for this category
    cat_machines = get_machines_for_category(all_machines, category)
    
    if not cat_machines:
        st.info(f"No machines found for category '{category}'.")
        return
    
    # ==================== 1. CATEGORY SUMMARY KPIs (reusing existing metric-card styling) ====================
    cat_summary = compute_category_summary(all_logs, all_machines, category)
    st.markdown(f"### 📊 {category} Summary")
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.markdown(
            "<div class='metric-card'>"
            f"<div class='metric-value'>{cat_summary['total_logs']}</div>"
            "<div class='metric-label'>Total Logs</div>"
            "</div>",
            unsafe_allow_html=True
        )
    with col_s2:
        st.markdown(
            "<div class='metric-card'>"
            f"<div class='metric-value' style='color:#44CC44'>{cat_summary['completed_logs']}</div>"
            "<div class='metric-label'>Completed</div>"
            "</div>",
            unsafe_allow_html=True
        )
    with col_s3:
        st.markdown(
            "<div class='metric-card'>"
            f"<div class='metric-value' style='color:#FFAA00'>{cat_summary['pending_logs']}</div>"
            "<div class='metric-label'>Pending</div>"
            "</div>",
            unsafe_allow_html=True
        )
    with col_s4:
        st.markdown(
            "<div class='metric-card'>"
            f"<div class='metric-value' style='color:#4da6ff'>₹{cat_summary['total_cost']:,.0f}</div>"
            "<div class='metric-label'>Total Cost</div>"
            "</div>",
            unsafe_allow_html=True
        )
    
    # ==================== 2. MACHINE LIST WITH CHECKBOXES (using st.dataframe) ====================
    st.markdown(f"**Machines in {category}: {len(cat_machines)}**")
    st.markdown("---")
    
    # Build a DataFrame with machine data plus a checkbox column
    machine_rows = []
    for machine in sorted(cat_machines, key=lambda m: m.machine_id):
        ms = compute_machine_summary(all_logs, machine.machine_id)
        machine_rows.append({
            "Select": False,
            "Machine ID": machine.machine_id,
            "Total Logs": ms['total_logs'],
            "Total Cost": ms['total_cost']
        })
    
    df_machines = pd.DataFrame(machine_rows)
    
    prev_selected = st.session_state.get("maintenance_selected_machine")
    
    edited_df = st.data_editor(
        df_machines,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "☐",
                help="Select a machine to view details",
                default=False,
                width=38,
            ),
            "Machine ID": st.column_config.Column(
                "Machine ID",
            ),
            "Total Logs": st.column_config.Column(
                "Total Logs",
            ),
            "Total Cost": st.column_config.Column(
                "Total Cost",
            ),
        },
        disabled=["Machine ID", "Total Logs", "Total Cost"],
        key="machine_list_editor"
    )
    
    # Find which machine is selected (only one)
    selected_rows = edited_df[edited_df["Select"] == True]
    selected_count = len(selected_rows)
    
    if selected_count > 1:
        # More than one selected - keep only the first one, deselect rest
        first_selected = selected_rows.iloc[0]["Machine ID"]
        # Deselect all
        edited_df["Select"] = False
        # Select only the first one
        edited_df.loc[edited_df["Machine ID"] == first_selected, "Select"] = True
        st.session_state.maintenance_selected_machine = first_selected
        st.rerun()
    elif selected_count == 1:
        selected_machine_id = selected_rows.iloc[0]["Machine ID"]
        if prev_selected != selected_machine_id:
            st.session_state.maintenance_selected_machine = selected_machine_id
            st.rerun()
    else:
        # No selection
        if prev_selected is not None:
            st.session_state.maintenance_selected_machine = None
            st.rerun()
    
    selected_machine_id = st.session_state.get("maintenance_selected_machine")
    
    # ==================== NAVIGATE TO MAINTENANCE MACHINE SUMMARY ====================
    if selected_machine_id:
        st.session_state.maintenance_page = "machine_summary"
        st.session_state.maintenance_selected_machine = selected_machine_id
        st.rerun()
    
    if not selected_machine_id:
        # No machine selected, show nothing below the table
        pass


# ==================== MAINTENANCE MACHINE SUMMARY PAGE ====================

def render_maintenance_machine_summary():
    """Render Machine Summary page within the Maintenance Logs workflow.
    
    Uses the EXACT SAME Alert History dataset as the Machine Details page.
    This is the single source of truth for maintenance history records.
    This page belongs EXCLUSIVELY to the Maintenance Logs module.
    """
    machine_id = st.session_state.get("maintenance_selected_machine")
    if not machine_id:
        st.session_state.maintenance_page = "category_detail"
        st.rerun()
        return
    
    machine = simulator.get_machine(machine_id)
    if not machine:
        st.error(f"Machine {machine_id} not found.")
        return
    
    st.markdown("<h1 class='main-header'>📝 Maintenance Logs</h1>", unsafe_allow_html=True)
    
    if st.button("← Back to Machine List"):
        st.session_state.maintenance_page = "category_detail"
        st.rerun()
    
    st.markdown(f"### 🔧 {machine.name} ({machine.machine_id})")
    
    # ==================== MAINTENANCE SUMMARY CARDS (from Alert History dataset) ====================
    # Use the EXACT SAME dataset as Machine Details → Alert History
    alerts = data_store.alert_service.get_alerts_by_machine(machine_id)
    
    total_logs = len(alerts)
    completed_logs = len([a for a in alerts if a.status != "Open"])
    pending_logs = len([a for a in alerts if a.status == "Open"])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            "<div class='summary-section' style='text-align:center;'>"
            f"<div class='summary-stat-value'>{total_logs}</div>"
            "<div class='summary-stat-label'>Total Logs</div>"
            "</div>",
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            "<div class='summary-section' style='text-align:center;'>"
            f"<div class='summary-stat-value' style='color:#44CC44'>{completed_logs}</div>"
            "<div class='summary-stat-label'>Completed</div>"
            "</div>",
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            "<div class='summary-section' style='text-align:center;'>"
            f"<div class='summary-stat-value' style='color:#FFAA00'>{pending_logs}</div>"
            "<div class='summary-stat-label'>Pending</div>"
            "</div>",
            unsafe_allow_html=True
        )
    with col4:
        st.markdown(
            "<div class='summary-section' style='text-align:center;'>"
            f"<div class='summary-stat-value' style='color:#4da6ff'>₹0</div>"
            "<div class='summary-stat-label'>Total Cost</div>"
            "</div>",
            unsafe_allow_html=True
        )
    
    # ==================== MAINTENANCE HISTORY TABLE (from actual Maintenance Logs dataset) ====================
    st.markdown("### 📜 Maintenance History")
    
    # Use actual maintenance logs which contain technician and cost data
    maintenance_logs = data_store.maintenance_log_service.get_logs_by_machine(machine_id)
    
    if not maintenance_logs:
        st.info("No maintenance history found for this machine.")
    else:
        work_orders = data_store.work_order_service.get_work_orders_by_machine(
            machine_id,
            include_completed=True
        )
        alert_by_id = {alert.alert_id: alert for alert in alerts}
        work_order_by_id = {wo.work_order_id: wo for wo in work_orders}
        used_alert_ids = set()

        def _alert_reason_to_cause(reason: str) -> str:
            r = (reason or "").lower()
            if "bearing" in r:
                return "Worn bearing race"
            if "refrigerant" in r:
                return "Refrigerant leakage"
            if "condenser" in r or "overheating" in r:
                return "Dust accumulation on coils"
            if "evaporator" in r or "icing" in r:
                return "Restricted airflow"
            if "motor" in r:
                return "Bearing wear"
            if "compressor" in r:
                return "Dirty condenser coil"
            if "fan" in r:
                return "Failed fan bearing"
            if "door" in r or "seal" in r:
                return "Damaged door gasket"
            if "cooling" in r:
                return "Low refrigerant charge"
            if "drum" in r or "vibration" in r:
                return "Unbalanced drum assembly"
            if "pump" in r or "water" in r:
                return "Pump impeller wear"
            if "alternator" in r:
                return "Failed alternator diode"
            if "fuel" in r:
                return "Clogged fuel filter"
            if "voltage" in r or "electrical" in r:
                return "Loose electrical connection"
            if "oil" in r:
                return "Oil leak from gasket"
            if "coolant" in r:
                return "Radiator blockage"
            if "timing" in r or "belt" in r:
                return "Belt material fatigue"
            if "spark" in r or "ignition" in r:
                return "Spark plug electrode wear"
            if "rpm" in r or "speed" in r:
                return "Sensor calibration drift"
            if "overload" in r or "current" in r or "load" in r:
                return "Excessive load condition"
            if "performance" in r or "drift" in r:
                return "Component degradation over time"
            return "Component degradation over time"

        def _display_severity(alert) -> str:
            return "NORMAL" if alert.severity.value == "INFO" else alert.severity.value

        def _matching_alert_for_log(log):
            if log.work_order_id:
                work_order = work_order_by_id.get(log.work_order_id)
                if work_order and work_order.alert_id:
                    linked_alert = alert_by_id.get(work_order.alert_id)
                    if linked_alert and linked_alert.alert_id not in used_alert_ids:
                        return linked_alert

            candidates = [
                alert for alert in alerts
                if alert.machine_id == log.machine_id and alert.alert_id not in used_alert_ids
            ]
            if not candidates:
                candidates = [alert for alert in alerts if alert.machine_id == log.machine_id]
            if not candidates:
                return None

            return min(
                candidates,
                key=lambda alert: abs((log.maintenance_date - alert.timestamp).total_seconds())
            )

        history_rows = []
        for log in maintenance_logs:
            if log.machine_id != machine_id:
                continue
            alert = _matching_alert_for_log(log)
            if not alert:
                continue
            used_alert_ids.add(alert.alert_id)
            history_rows.append({
                "Machine ID": log.machine_id,
                "Date": log.maintenance_date.strftime('%Y-%m-%d'),
                "Severity": _display_severity(alert),
                "Reason": alert.reason,
                "Cause": _alert_reason_to_cause(alert.reason),
                "Technician": log.technician,
                "Cost": log.cost,
                "Status": getattr(log, "status", "Completed")
            })
        df_history = pd.DataFrame(
            history_rows,
            columns=["Machine ID", "Date", "Severity", "Reason", "Cause", "Technician", "Cost", "Status"]
        )
        st.dataframe(df_history, use_container_width=True, hide_index=True)


# ==================== ANALYTICS DESTINATION PAGES ====================

def render_analytics_machines():
    """Render filtered machine list for Analytics badge clicks.
    
    Navigated from Analytics → Healthy/Warning/Critical badges.
    Shows the EXISTING Enterprise Table with machines filtered
    by the selected category and condition filter.
    Back button returns to Analytics page.
    """
    category = st.session_state.get("analytics_category", "")
    afilter = st.session_state.get("analytics_chip_filter", "healthy")
    
    st.markdown(f"<h1 class='main-header'>Equipment Analytics - {category}</h1>", unsafe_allow_html=True)
    if st.button("← Back to Analytics"):
        st.session_state.page = "analytics"
        st.rerun()
    st.markdown("---")
    
    all_machines = simulator.get_all_machines()
    
    from maintenance_logs_enhanced import get_machines_for_category
    cat_machines = get_machines_for_category(all_machines, category)
    
    # Filter by condition
    if afilter == "healthy":
        filtered = [m for m in cat_machines if m.status == MachineStatus.NORMAL]
        title = "✅ Healthy Machines"
    elif afilter == "warning":
        filtered = [m for m in cat_machines if m.status == MachineStatus.WARNING]
        title = "⚠️ Warning Machines"
    elif afilter == "critical":
        filtered = [m for m in cat_machines if m.status == MachineStatus.CRITICAL]
        title = "🔴 Critical Machines"
    else:
        filtered = list(cat_machines)
        title = f"{category} Machines"
    
    st.markdown(f"**{title}: {len(filtered)}**")
    
    machine_rows = []
    for m in sorted(filtered, key=lambda x: x.health_score):
        machine_rows.append({
            "Machine ID": m.machine_id,
            "Category": m.machine_type.value,
            "Health Score": f"{m.health_score:.1f}%",
            "Failure Probability": f"{m.failure_probability*100:.1f}%",
            "Condition": m.status.value
        })
    
    if machine_rows:
        df_machines = pd.DataFrame(machine_rows)
        sel = st.dataframe(
            df_machines,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Machine ID": st.column_config.Column("Machine ID", width="small"),
                "Category": st.column_config.Column("Category", width="medium"),
                "Health Score": st.column_config.Column("Health Score", width="small"),
                "Failure Probability": st.column_config.Column("Failure Probability", width="small"),
                "Condition": st.column_config.Column("Condition", width="small"),
            }
        )
        if len(sel.selection.rows) > 0:
            row_idx = sel.selection.rows[0]
            machine_id = df_machines.iloc[row_idx]["Machine ID"]
            navigate_to_machine(machine_id)
            st.rerun()
    else:
        df_empty = pd.DataFrame(columns=[
            "Machine ID", "Category", "Health Score", "Failure Probability", "Condition"
        ])
        st.dataframe(
            df_empty,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Machine ID": st.column_config.Column("Machine ID", width="small"),
                "Category": st.column_config.Column("Category", width="medium"),
                "Health Score": st.column_config.Column("Health Score", width="small"),
                "Failure Probability": st.column_config.Column("Failure Probability", width="small"),
                "Condition": st.column_config.Column("Condition", width="small"),
            }
        )
        st.info("No machines found.")


def render_analytics_health_overview():
    """Render category health overview page.
    
    Navigated from Analytics → Avg Health badge.
    Shows all machines in the selected category with health scores.
    Back button returns to Analytics page.
    """
    category = st.session_state.get("analytics_category", "")
    
    st.markdown(f"<h1 class='main-header'>Equipment Analytics - {category} Health Overview</h1>", unsafe_allow_html=True)
    if st.button("← Back to Analytics"):
        st.session_state.page = "analytics"
        st.rerun()
    st.markdown("---")
    
    all_machines = simulator.get_all_machines()
    
    from maintenance_logs_enhanced import get_machines_for_category
    cat_machines = get_machines_for_category(all_machines, category)
    
    st.markdown(f"**{category}: {len(cat_machines)} machines**")
    
    machine_rows = []
    for m in sorted(cat_machines, key=lambda x: x.health_score):
        machine_rows.append({
            "Machine ID": m.machine_id,
            "Category": m.machine_type.value,
            "Health Score": f"{m.health_score:.1f}%",
            "Failure Probability": f"{m.failure_probability*100:.1f}%",
            "Condition": m.status.value
        })
    
    if machine_rows:
        df_machines = pd.DataFrame(machine_rows)
        sel = st.dataframe(
            df_machines,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Machine ID": st.column_config.Column("Machine ID", width="small"),
                "Category": st.column_config.Column("Category", width="medium"),
                "Health Score": st.column_config.Column("Health Score", width="small"),
                "Failure Probability": st.column_config.Column("Failure Probability", width="small"),
                "Condition": st.column_config.Column("Condition", width="small"),
            }
        )
        if len(sel.selection.rows) > 0:
            row_idx = sel.selection.rows[0]
            machine_id = df_machines.iloc[row_idx]["Machine ID"]
            navigate_to_machine(machine_id)
            st.rerun()
    else:
        st.info("No machines found.")


# ==================== KPI DESTINATION PAGES ====================

def render_kpi_categories():
    """Render the Machines Categories page from the Categories KPI card."""
    st.markdown("<h1 class='main-header'>Machine Categories</h1>", unsafe_allow_html=True)
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("---")
    render_machine_category_cards()


def render_kpi_machines_page():
    """Render KPI machines page using the EXISTING Enterprise Table.
    
    This is the single destination for ALL KPI machine navigation:
    - Total Machines → shows ALL machines
    - Healthy → shows machines with Condition = NORMAL
    - Warning → shows machines with Condition = WARNING
    - Critical → shows machines with Condition = CRITICAL
    
    Reuses the EXACT same Enterprise Table pattern (st.dataframe with
    on_select='rerun', selection_mode='single-row') as the
    'All Machines Health Status' table on the dashboard.
    """
    filter_value = st.session_state.get("kpi_filter", "all")
    
    # Set page title based on filter
    if filter_value == "healthy":
        title = "✅ Healthy Machines"
    elif filter_value == "warning":
        title = "⚠️ Warning Machines"
    elif filter_value == "critical":
        title = "🔴 Critical Machines"
    else:
        title = "All Machines"
    
    st.markdown(f"<h1 class='main-header'>{title}</h1>", unsafe_allow_html=True)
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("---")
    
    all_machines = simulator.get_all_machines()
    
    # Filter machines by condition
    if filter_value == "healthy":
        filtered = [m for m in all_machines if m.status == MachineStatus.NORMAL]
    elif filter_value == "warning":
        filtered = [m for m in all_machines if m.status == MachineStatus.WARNING]
    elif filter_value == "critical":
        filtered = [m for m in all_machines if m.status == MachineStatus.CRITICAL]
    else:
        filtered = list(all_machines)
    
    count_label = {
        "healthy": "Healthy",
        "warning": "Warning",
        "critical": "Critical",
        "all": "Total"
    }.get(filter_value, "Total")
    
    st.markdown(f"**{count_label} Machines: {len(filtered)}**")
    
    # Build the DataFrame with the exact same columns as the spec
    machine_rows = []
    for m in sorted(filtered, key=lambda x: x.health_score):
        machine_rows.append({
            "Machine ID": m.machine_id,
            "Category": m.machine_type.value,
            "Health Score": f"{m.health_score:.1f}%",
            "Failure Probability": f"{m.failure_probability*100:.1f}%",
            "Condition": m.status.value
        })
    
    if machine_rows:
        df_machines = pd.DataFrame(machine_rows)
        sel = st.dataframe(
            df_machines,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Machine ID": st.column_config.Column("Machine ID", width="small"),
                "Category": st.column_config.Column("Category", width="medium"),
                "Health Score": st.column_config.Column("Health Score", width="small"),
                "Failure Probability": st.column_config.Column("Failure Probability", width="small"),
                "Condition": st.column_config.Column("Condition", width="small"),
            }
        )
        if len(sel.selection.rows) > 0:
            row_idx = sel.selection.rows[0]
            machine_id = df_machines.iloc[row_idx]["Machine ID"]
            navigate_to_machine(machine_id)
            st.rerun()
    else:
        # Show empty table with the existing Enterprise Table structure
        df_empty = pd.DataFrame(columns=[
            "Machine ID", "Category", "Health Score", "Failure Probability", "Condition"
        ])
        st.dataframe(
            df_empty,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Machine ID": st.column_config.Column("Machine ID", width="small"),
                "Category": st.column_config.Column("Category", width="medium"),
                "Health Score": st.column_config.Column("Health Score", width="small"),
                "Failure Probability": st.column_config.Column("Failure Probability", width="small"),
                "Condition": st.column_config.Column("Condition", width="small"),
            }
        )
        st.info("No machines found.")


# ==================== PRE-ROUTING HOOK ====================

def pre_route():
    """Run BEFORE the main app router to intercept hyperlink navigation.
    
    Handles Dashboard KPI card clicks (?kpi_* params).
    
    This hook ensures the correct page is set BEFORE the router
    decides which page to render — preventing accidental routing to the wrong module."""
    query_params = st.query_params

    if (
        not query_params.get("_analytics_page")
        and st.session_state.get("_analytics_badge_source") == "analytics"
        and st.session_state.get("_analytics_badge_target") in ("alerts", "maintenance_logs")
        and st.session_state.get("page") == st.session_state.get("_analytics_badge_target")
    ):
        st.session_state.page = "analytics"
        st.session_state._analytics_badge_target = None
        st.session_state._analytics_badge_source = None
        st.session_state._analytics_badge_route_key = None
        return
    
    # Handle Dashboard KPI card clicks - each goes to its own dedicated page
    if query_params.get("kpi_categories"):
        st.session_state.page = "kpi_categories"
        st.session_state.selected_factory = None
        st.session_state.selected_machine = None
        st.session_state.kpi_filter = None
        query_params.clear()
        return
    
    if query_params.get("kpi_machines"):
        st.session_state.page = "kpi_machines"
        st.session_state.selected_factory = None
        st.session_state.selected_machine = None
        st.session_state.kpi_filter = "all"
        query_params.clear()
        return
    
    if query_params.get("kpi_healthy"):
        st.session_state.page = "kpi_healthy"
        st.session_state.selected_factory = None
        st.session_state.selected_machine = None
        st.session_state.kpi_filter = "healthy"
        query_params.clear()
        return
    
    if query_params.get("kpi_warning"):
        st.session_state.page = "kpi_warning"
        st.session_state.selected_factory = None
        st.session_state.selected_machine = None
        st.session_state.kpi_filter = "warning"
        query_params.clear()
        return
    
    if query_params.get("kpi_critical"):
        st.session_state.page = "kpi_critical"
        st.session_state.selected_factory = None
        st.session_state.selected_machine = None
        st.session_state.kpi_filter = "critical"
        query_params.clear()
        return
    
    if query_params.get("kpi_analytics"):
        st.session_state.page = "analytics"
        st.session_state.kpi_filter = None
        query_params.clear()
        return
    
    # Handle Machine ID click navigation from LinkColumn tables
    navigate_machine = query_params.get("navigate")
    if navigate_machine:
        st.session_state.page = "machines"
        st.session_state.selected_machine = navigate_machine
        query_params.clear()
        return
    
    # Handle Analytics Category Summary badge clicks via query params (relative URLs in same tab)
    analytics_page = query_params.get("_analytics_page")
    if analytics_page:
        analytics_category = query_params.get("_analytics_category", "")
        analytics_filter = query_params.get("_analytics_filter", "")
        maint_cat = query_params.get("_maint_cat", "")
        analytics_route_key = f"{analytics_page}|{analytics_category}|{analytics_filter}|{maint_cat}"
        preserve_history_route = analytics_page in ("alerts", "maintenance_logs")
        if preserve_history_route and st.session_state.get("_analytics_badge_route_key") == analytics_route_key:
            return
        if analytics_category:
            st.session_state.analytics_category = analytics_category
        if analytics_filter:
            st.session_state.analytics_chip_filter = analytics_filter
        st.session_state._from_analytics = True
        if preserve_history_route:
            st.session_state._analytics_badge_source = "analytics"
            st.session_state._analytics_badge_target = analytics_page
            st.session_state._analytics_badge_route_key = analytics_route_key
        else:
            st.session_state._analytics_badge_source = None
            st.session_state._analytics_badge_target = None
            st.session_state._analytics_badge_route_key = None
        if maint_cat:
            st.session_state.maintenance_category = maint_cat
            st.session_state.maintenance_page = "category_detail"
        st.session_state.page = analytics_page
        if preserve_history_route:
            return
        query_params.clear()
        return


# ==================== MAIN APP ====================

def main():
    """Main app router."""
    ensure_data_consistency_once()
    pre_route()
    render_sidebar()
    
    page = st.session_state.page
    
    if page == "dashboard":
        render_dashboard()
    elif page == "kpi_categories":
        render_kpi_categories()
    elif page in ("kpi_machines", "kpi_healthy", "kpi_warning", "kpi_critical"):
        render_kpi_machines_page()
    elif page == "machines":
        render_machines()
    elif page == "analytics":
        render_analytics()
    elif page == "analytics_machines":
        render_analytics_machines()
    elif page == "analytics_health_overview":
        render_analytics_health_overview()
    elif page == "alerts":
        render_alerts()
    elif page == "work_orders":
        render_work_orders()
    elif page == "reports":
        render_reports()
    elif page == "copilot":
        render_copilot()
    elif page == "maintenance_logs":
        render_maintenance_logs()


if __name__ == "__main__":
    main()

