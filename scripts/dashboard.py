"""
Predictive Maintenance Dashboard (Agentic AI)

Interactive Streamlit dashboard for machine status, diagnostics, and maintenance planning.
Now with LLM-powered agentic reasoning via OpenRouter.

Features:
- State-based navigation (Multi-Machine Overview ↔ Machine Detail View)
- Clickable machine cards with AI-powered insights
- Clean, professional UI with proper spacing
"""

import os
from typing import Dict, List, Optional
from datetime import datetime

import streamlit as st
from scripts.data_ingestion import generate_simulated_sensor_data, load_csv_from_upload
from scripts.llm_client import OpenRouterClient
from scripts.monitoring_agent import MonitoringAgent
from scripts.diagnostic_agent import DiagnosticAgent
from scripts.decision_agent import DecisionAgent
from scripts.maintenance_planner_agent import MaintenancePlannerAgent
from scripts.chatbot_agent import ChatbotAgent

try:
    from streamlit import st_autorefresh
    AUTO_REFRESH_AVAILABLE = True
except ImportError:
    AUTO_REFRESH_AVAILABLE = False

try:
    import plotly.graph_objects as go
    import pandas as pd
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


# ==================== CONSTANTS ====================
MACHINE_IDS = ['M1', 'M2', 'M3']
STATUS_COLOR = {
    'NORMAL': '#2ECC71',
    'WARNING': '#F1C40F',
    'CRITICAL': '#E74C3C',
    'UNKNOWN': '#95A5A6'
}

SENSOR_UNITS = {
    'vibration': 'mm/s',
    'temperature': '°C',
    'pressure': 'bar',
    'noise_level': 'dB'
}

SENSOR_LIMITS = {
    'vibration': (0, 6),
    'temperature': (40, 120),
    'pressure': (70, 140),
    'noise_level': (60, 110)
}

DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"


# ==================== PERFORMANCE CONSTANTS ====================
MAX_READINGS_FOR_AGENTS = 10  # 🔹 4. REDUCE DATA SIZE - Only send last 10 readings to agents
AUTO_REFRESH_MINUTES = 0  # 🔹 9. DISABLE AUTO REFRESH - Set to 0 to disable

# ==================== REAL-TIME IoT SIMULATION ====================
import random
import time
import time as time_module  # For timing logs

def generate_current_sensor_values(machine_id: str, fixed: bool = False) -> dict:
    """
    Generate current sensor values for real-time IoT simulation.
    Returns a dictionary with temperature, vibration, pressure.
    
    Args:
        machine_id: The machine identifier (M1, M2, M3)
        fixed: If True, return fixed base values (no random variation)
    """
    # Base values for each machine (slightly different for variety)
    machine_bases = {
        'M1': {'temp': 65, 'vib': 2.5, 'press': 100},
        'M2': {'temp': 70, 'vib': 3.0, 'press': 105},
        'M3': {'temp': 60, 'vib': 2.0, 'press': 95}
    }
    
    base = machine_bases.get(machine_id, {'temp': 65, 'vib': 2.5, 'press': 100})
    
    if fixed:
        # Return fixed base values (no random variation) for stable display
        return {
            'temperature': base['temp'],
            'vibration': base['vib'],
            'pressure': base['press'],
            'timestamp': datetime.now()
        }
    
    # Add small random variations (±10%) - only when refresh is triggered
    return {
        'temperature': round(base['temp'] + random.uniform(-5, 10), 1),
        'vibration': round(base['vib'] + random.uniform(-0.5, 1.0), 2),
        'pressure': round(base['press'] + random.uniform(-5, 8), 1),
        'timestamp': datetime.now()
    }


def init_realtime_sensor_data():
    """
    🔹 6. FIX SENSOR RE-INITIALIZATION
    Initialize real-time sensor data in session_state ONCE.
    Data persists across reruns until explicitly refreshed.
    Uses fixed values by default for stable display.
    """
    # Only initialize if not already done
    if not st.session_state.get('sensors_initialized', False):
        st.session_state['realtime_sensors'] = {
            machine_id: generate_current_sensor_values(machine_id, fixed=True)
            for machine_id in MACHINE_IDS
        }
        st.session_state['last_update'] = datetime.now()
        st.session_state['sensors_initialized'] = True
    
    return st.session_state['realtime_sensors']


def update_realtime_sensors(use_random: bool = False):
    """
    Update sensor values to simulate real-time IoT data stream.
    Called when Refresh Data is triggered.
    
    Args:
        use_random: If True, add random variations. If False, use fixed values.
    """
    # This function is deprecated. Real-time data must come from latest historical reading only.
    # Use _update_realtime_from_data after data changes.
    pass


def init_session_state():
    """
    Initialize all required session state variables ONCE.
    These persist across Streamlit reruns.
    """
    # 🔹 1. Data Persistence - Initialize ONLY ONCE
    if 'data' not in st.session_state:
        st.session_state['data'] = None
    
    # 🔹 6. Maintain Selected Machine
    if 'selected_machine' not in st.session_state:
        st.session_state['selected_machine'] = None
    
    # Other session state variables
    if 'api_key' not in st.session_state:
        st.session_state['api_key'] = None
    if 'chat_history' not in st.session_state:
        st.session_state['chat_history'] = []
    if 'data_source' not in st.session_state:
        st.session_state['data_source'] = None
    if 'machine_ids' not in st.session_state:
        st.session_state['machine_ids'] = MACHINE_IDS.copy()
    if 'realtime_sensors' not in st.session_state:
        st.session_state['realtime_sensors'] = {}
    if 'last_update' not in st.session_state:
        st.session_state['last_update'] = None
    if 'ai_insight' not in st.session_state:
        st.session_state['ai_insight'] = None
    if 'last_machine' not in st.session_state:
        st.session_state['last_machine'] = None
    
    # 🚀 PERFORMANCE: Cache for expensive computations
    if 'analysis_cache' not in st.session_state:
        st.session_state['analysis_cache'] = None
    if 'ai_insight_cache' not in st.session_state:
        st.session_state['ai_insight_cache'] = {}  # {machine_id: insight}
    
    # 🔹 6. FIX SENSOR RE-INITIALIZATION - Track if sensors initialized
    if 'sensors_initialized' not in st.session_state:
        st.session_state['sensors_initialized'] = False
    
    # 🔹 6. FIX DATA LOADING - Track if data loaded once
    if 'data_loaded_once' not in st.session_state:
        st.session_state['data_loaded_once'] = False


def should_refresh_data() -> bool:
    """
    🔹 8. FIX AUTO REFRESH LOGIC - Only manual refresh
    Returns False to disable automatic time-based refresh.
    """
    return False  # Disabled - only manual refresh allowed


def update_last_refresh():
    """Update the last refresh timestamp to current time."""
    st.session_state['last_refresh'] = datetime.now()


def init_machine_data(num_readings: int = 20, anomaly_chance: float = 0.15):
    """
    Initialize machine data in session_state.
    Data is generated only once on first load.
    Subsequent reruns use stored data.
    """
    if st.session_state.get('data') is None:
        st.session_state['data'] = {
            machine_id: generate_simulated_sensor_data(
                machine_id=machine_id,
                num_readings=num_readings,
                anomaly_chance=anomaly_chance
            )
            for machine_id in MACHINE_IDS
        }
        st.session_state['data_initialized'] = True

    return st.session_state['data']


def refresh_machine_data(num_readings: int = 20, anomaly_chance: float = 0.15):
    """
    Regenerate machine data when Refresh Data is clicked.
    This replaces the existing session state data.
    """
    new_data = {
        machine_id: generate_simulated_sensor_data(
            machine_id=machine_id,
            num_readings=num_readings,
            anomaly_chance=anomaly_chance
        )
        for machine_id in MACHINE_IDS
    }

    st.session_state['data'] = new_data
    _update_realtime_from_data(new_data)

    st.session_state['analysis_cache'] = None
    st.session_state['ai_insight_cache'] = {}
    st.session_state['force_rebuild'] = True

    st.session_state['ai_insight'] = None
    st.session_state['last_machine'] = None


# ==================== INTELLIGENT DATA LOADING (CSV + SIMULATED) ====================


def load_data_with_fallback(uploaded_file, num_readings: int = 20, anomaly_chance: float = 0.15):
    """
    🔹 6. FIX DATA LOADING - Load data ONLY ONCE
    Intelligently load data: CSV upload OR fallback to simulated data.
    Data is loaded only on first run, then cached.
    """
    global MACHINE_IDS
    
    # 🔹 6. FIX DATA LOADING - Check if already loaded
    if st.session_state.get('data_loaded_once') and st.session_state.get('data') is not None:
        # Data already loaded - return cached data
        return st.session_state['data'], "🔧 Using cached data"
    
    existing_data = st.session_state.get('data')
    
    if uploaded_file is not None:
        # 🟢 MODE 1: User Uploads CSV
        try:
            machine_data = load_csv_from_upload(uploaded_file)
            
            if not machine_data:
                st.error("CSV file contains no valid machine data. Falling back to simulated data.")
                raise ValueError("Empty dataset")
            
            MACHINE_IDS = list(machine_data.keys())
            
            st.session_state['data'] = machine_data
            st.session_state['data_source'] = 'csv'
            st.session_state['uploaded_file_name'] = uploaded_file.name
            st.session_state['machine_ids'] = MACHINE_IDS
            
            _update_realtime_from_data(machine_data)
            
            data_message = f"📂 Using uploaded dataset: {uploaded_file.name}"
            
        except ValueError as e:
            st.error(f"⚠️ CSV Error: {str(e)}. Falling back to simulated data.")
            machine_data = _generate_fallback_data(num_readings, anomaly_chance)
            data_message = "⚠️ Using simulated data (CSV error)"
    else:
        # 🔵 MODE 2: No CSV Uploaded - Generate simulated data
        if existing_data is None:
            # First load - generate data
            machine_data = _generate_fallback_data(num_readings, anomaly_chance)
            MACHINE_IDS = ['M1', 'M2', 'M3']
            
            st.session_state['data'] = machine_data
            st.session_state['data_source'] = 'simulated'
            st.session_state['machine_ids'] = MACHINE_IDS
            
            data_message = "🔧 Using simulated data"
        else:
            # Use existing data
            machine_data = existing_data
            data_message = "🔧 Using cached simulated data"
    
    # 🔹 6. FIX DATA LOADING - Mark as loaded
    st.session_state['data_loaded_once'] = True
    
    # Ensure ALL machines exist
    for mid in ['M1', 'M2', 'M3']:
        if mid not in machine_data:
            machine_data[mid] = generate_simulated_sensor_data(
                machine_id=mid,
                num_readings=num_readings,
                anomaly_chance=anomaly_chance
            )
    
    _update_realtime_from_data(machine_data)
    
    return machine_data, data_message


def _generate_fallback_data(num_readings: int, anomaly_chance: float):
    """Generate fallback simulated data."""
    return {
        machine_id: generate_simulated_sensor_data(
            machine_id=machine_id,
            num_readings=num_readings,
            anomaly_chance=anomaly_chance
        )
        for machine_id in MACHINE_IDS
    }


def _update_realtime_from_data(machine_data: Dict):
    """
    Update real-time sensors from loaded data (CSV or simulated).
    Uses latest reading for each machine.
    """
    realtime = {}
    for machine_id, readings in machine_data.items():
        if readings:
            latest = readings[-1]
            realtime[machine_id] = {
                'temperature': latest.temperature,
                'vibration': latest.vibration,
                'pressure': latest.pressure,
                'noise_level': latest.noise_level,
                'timestamp': latest.timestamp
            }
        else:
            realtime[machine_id] = generate_current_sensor_values(machine_id, fixed=True)
    st.session_state['realtime_sensors'] = realtime
    st.session_state['last_update'] = datetime.now()


def get_machine_status(machine_id: str) -> str:
    """
    🔹 SINGLE SOURCE OF TRUTH: Get consistent status for a machine.
    
    ONLY uses analysis_cache from MonitoringAgent - never computes from raw thresholds.
    This ensures overview and detail show SAME status.
    
    Args:
        machine_id: The machine identifier
        
    Returns:
        Status string: 'NORMAL', 'WARNING', 'CRITICAL', or 'UNKNOWN'
    """
    # ONLY use pre-computed analysis from MonitoringAgent
    analysis = st.session_state.get('analysis_cache', {})
    
    if machine_id in analysis:
        severity = analysis[machine_id].get('monitoring', {}).get('severity', 'UNKNOWN')
        return severity.upper() if severity else 'UNKNOWN'
    
    # No fallback - if analysis not available, something is wrong
    return 'UNKNOWN'


def get_latest_reading(machine_id: str) -> Optional[dict]:
    """
    Get the latest sensor reading for a machine.
    🔹 4. Real-Time Data
    
    Args:
        machine_id: The machine identifier
        
    Returns:
        Dictionary with latest sensor values or None
    """
    machine_data = st.session_state.get('data', {})
    readings = machine_data.get(machine_id, [])
    
    if readings:
        latest = readings[-1]
        return {
            'temperature': latest.temperature,
            'vibration': latest.vibration,
            'pressure': latest.pressure,
            'noise_level': latest.noise_level,
            'timestamp': latest.timestamp,
            'status': get_machine_status(machine_id)  # Include status from single source
        }
    return None


def get_machine_history(machine_id: str) -> List:
    """
    Get historical data for a machine.
    🔹 5. Historical Data
    
    Args:
        machine_id: The machine identifier
        
    Returns:
        List of SensorData objects for the machine
    """
    machine_data = st.session_state.get('data', {})
    return machine_data.get(machine_id, [])


# ==================== INITIALIZATION ====================
def init_agents(api_key: str = None, model: str = None):
    """Initialize all agents with optional LLM client."""
    resolved_model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    llm_client = None
    if api_key or os.environ.get("OPENROUTER_API_KEY"):
        try:
            llm_client = OpenRouterClient(
                api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
                model=resolved_model
            )
        except Exception as e:
            st.warning(f"Failed to initialize LLM client: {e}")
    
    return {
        'monitoring': MonitoringAgent(llm_client),
        'diagnostic': DiagnosticAgent(llm_client),
        'decision': DecisionAgent(llm_client),
        'maintenance': MaintenancePlannerAgent(llm_client),
        'chatbot': ChatbotAgent(llm_client),
        'llm_client': llm_client
    }


def build_analysis(machine_data: Dict[str, List], agents: Dict):
    """
    🔹 1. LOCK ANALYSIS - Compute ONLY ONCE
    🔹 3. OPTIMIZE AGENT EXECUTION - Skip heavy agents based on severity
    🔹 4. REDUCE DATA SIZE - Only send last 10 readings to agents
    
    AGENT FLOW OPTIMIZATION:
    - NORMAL: Only Monitoring Agent runs (skip diagnostic, decision, maintenance)
    - WARNING: Monitoring + Diagnostic + Decision agents run (skip maintenance)
    - CRITICAL: Run all agents
    """
    # 🔹 10. PERFORMANCE DEBUGGING - Start timing
    start_time = time_module.time()
    
    analysis = {}
    for machine_id, readings in machine_data.items():
        # 🔹 4. REDUCE DATA SIZE - Only use last 10 readings
        recent_readings = readings[-MAX_READINGS_FOR_AGENTS:] if readings else []
        
        # Always run Monitoring Agent to get severity
        monitoring = agents['monitoring'].evaluate(recent_readings)
        severity = monitoring.get('severity', 'normal').lower()
        
        # 🔹 3. OPTIMIZE AGENT EXECUTION - Skip heavy agents based on severity
        if severity == 'normal':
            # NORMAL: Only Monitoring Agent - no issues detected
            diagnostic = {'root_causes': [], 'confidence_scores': {}}
            decision = {'recommended_actions': [], 'priority': 'low'}
            maintenance_plan = {'maintenance_plans': [], 'safety_notes': []}
            
        elif severity == 'warning':
            # WARNING: Run Diagnostic + Decision agents only (skip maintenance)
            diagnostic = agents['diagnostic'].analyze(recent_readings, monitoring)
            decision = agents['decision'].analyze(diagnostic, severity)
            maintenance_plan = {'maintenance_plans': [], 'safety_notes': []}
            
        else:  # critical or unknown
            # CRITICAL: Run all agents
            diagnostic = agents['diagnostic'].analyze(recent_readings, monitoring)
            decision = agents['decision'].analyze(diagnostic, severity)
            maintenance_plan = agents['maintenance'].analyze(diagnostic.get('root_causes', []), severity)
        
        analysis[machine_id] = {
            'monitoring': monitoring,
            'diagnostic': diagnostic,
            'decision': decision,
            'maintenance_plan': maintenance_plan,
            'sensor_history': readings  # Keep full history for display
        }
    
    # 🔹 10. PERFORMANCE DEBUGGING - Log execution time
    elapsed = time_module.time() - start_time
    print(f"⚡ build_analysis completed in {elapsed:.3f}s")
    
    return analysis


# ==================== AI INSIGHT FUNCTION ====================
def get_ai_insight(machine_id: str, details: Dict, llm_client) -> Optional[str]:
    """
    Get AI-powered insight for a machine using OpenRouter API.
    
    🔹 1. LAZY LLM EXECUTION - Only called when explicitly requested
    
    Returns:
        str: AI insight with problem description, risk level, and recommended action
    """
    if not llm_client:
        return "AI insight unavailable: No LLM client configured"
    
    try:
        monitoring = details['monitoring']
        diagnostic = details['diagnostic']
        decision = details['decision']
        readings = details['sensor_history']
        
        # Get severity from SINGLE SOURCE
        severity = get_machine_status(machine_id)
        
        # Get current sensor values
        current = readings[-1] if readings else None
        sensor_data = ""
        if current:
            sensor_data = f"""
- Vibration: {current.vibration:.2f} mm/s
- Temperature: {current.temperature:.2f} °C
- Pressure: {current.pressure:.2f} bar
- Noise Level: {current.noise_level:.2f} dB"""
        
        safety_instruction = ""
        if severity == "WARNING":
            safety_instruction = "\nSAFETY RULE: Never say 'safe to operate'. Use 'operate with caution'."
        elif severity == "CRITICAL":
            safety_instruction = "\nSAFETY RULE: Never allow continued operation. State that the machine must be stopped and attended immediately."
        
        prompt = f"""You are a predictive maintenance expert. Analyze the following machine data for {machine_id} and provide insights.

Machine: {machine_id}
Severity: {severity}
Current Sensor Data:{sensor_data}

Issues Detected: {monitoring.get('issues', [])}
Root Causes: {diagnostic.get('root_causes', [])}
Recommended Actions: {decision.get('recommended_actions', [])}
{safety_instruction}

Please provide a concise analysis in this format:
PROBLEM: [Brief description of the issue]
RISK LEVEL: [Low/Medium/High/Critical]
ACTION: [Recommended action to take]

Keep your response short and actionable."""

        # 🔹 7. ADD DEBUG LOGGING
        print("LLM CALLED for:", machine_id)
        
        # Call AI using correct API: chat(system_prompt, user_prompt)
        response = llm_client.chat(
            "You are a predictive maintenance expert AI assistant.",
            prompt,
            temperature=0.7,
            max_tokens=500
        )
        
        if response:
            return response
        return "AI insight unavailable: Empty response"
        
    except Exception as e:
        return f"AI insight unavailable: {str(e)}"


# ==================== MAINTENANCE REPORT FUNCTIONS ====================
def analyze_machine_trend(readings: List, condition: str = "NORMAL") -> str:
    """
    Analyze sensor data trend over time.
    
    FIX: Trend MUST be calculated from historical sensor data, then enforced based on condition.
    
    Args:
        readings: List of sensor readings
        condition: Machine condition (NORMAL, WARNING, CRITICAL)
    
    Returns:
        Trend string: 'Stable', 'Slightly Unstable', or 'Unstable'
    """
    if not readings or len(readings) < 2:
        return "Stable"

    first = readings[0]
    last = readings[-1]

    temp_change = abs(last.temperature - first.temperature)
    vib_change = abs(last.vibration - first.vibration)
    press_change = abs(last.pressure - first.pressure)

    avg_change = (temp_change + vib_change + press_change) / 3

    if avg_change < 2:
        trend = "Stable"
    elif avg_change < 5:
        trend = "Slightly Unstable"
    else:
        trend = "Unstable"

    if condition == "NORMAL":
        return "Stable" if avg_change < 3 else "Slightly Unstable"
    elif condition == "WARNING":
        return "Slightly Unstable"
    elif condition == "CRITICAL":
        return "Unstable"

    return trend


def generate_machine_summary(machine_id: str, details: Dict, readings: List) -> str:
    """
    Generate a concise maintenance report for a single machine.
    
    Output Format:
    Machine M1 Summary:
    Condition: [Normal/Warning/Critical]
    Issues: [list or None]
    Trend: [Stable/Unstable]
    Cause: [possible reason]
    Action: [recommended action]
    """
    monitoring = details['monitoring']
    diagnostic = details['diagnostic']
    decision = details['decision']
    
    severity = monitoring.get('severity', 'normal').upper()
    issues = monitoring.get('issues', [])
    root_causes = diagnostic.get('root_causes', [])
    actions = decision.get('recommended_actions', [])
    
    # Key Issues
    if issues:
        issue_types = list(set([i.get('sensor', 'Unknown') for i in issues]))
        issues_str = ", ".join(issue_types)
    else:
        issues_str = "None"
    
    # Trend
    severity = get_machine_status(machine_id)
    trend = analyze_machine_trend(readings, severity)
    
    # Possible Cause
    if root_causes:
        cause_str = root_causes[0]
    else:
        cause_str = "No significant issues identified"
    
    # Recommended Action
    if actions:
        action_str = actions[0]
    else:
        action_str = "Continue monitoring"
    
    # Build report in strict format
    report = f"""Machine {machine_id} Summary:
Condition: {severity}
Issues: {issues_str}
Trend: {trend}
Cause: {cause_str}
Action: {action_str}"""
    
    return report


def generate_overall_summary(analysis: Dict[str, Dict]) -> str:
    """
    Generate an overall system summary with STRICT logic rules.
    
    Rules:
    - Only NORMAL machines are Stable
    - Warning/Critical machines are NOT Stable
    - No contradictions in output
    """
    # Collect machine data
    machine_data = []
    for machine_id, details in analysis.items():
        severity = details['monitoring'].get('severity', 'normal').upper()
        issues = details['monitoring'].get('issues', [])
        issue_count = len(issues)
        machine_data.append({
            'id': machine_id,
            'severity': severity,
            'issues': issues,
            'issue_count': issue_count
        })
    
    # Sort by severity priority: CRITICAL > WARNING > NORMAL
    severity_priority = {'CRITICAL': 0, 'WARNING': 1, 'NORMAL': 2, 'UNKNOWN': 3}
    machine_data.sort(key=lambda x: (severity_priority.get(x['severity'], 3), -x['issue_count']))
    
    # === PRIORITY RANKING ===
    priority_ranking = " → ".join([f"{m['id']} ({m['severity']})" for m in machine_data])
    
    # === MOST CRITICAL ===
    critical_machines = [m for m in machine_data if m['severity'] == 'CRITICAL']
    if critical_machines:
        most_critical = critical_machines[0]
        most_critical_str = f"{most_critical['id']} ({most_critical['severity']})"
    else:
        most_critical_str = "None"
    
    # === MOST STABLE ===
    normal_machines = [m for m in machine_data if m['severity'] == 'NORMAL']
    if len(normal_machines) == len(machine_data):
        # All machines are Normal
        most_stable_str = "All Machines"
    elif len(normal_machines) > 1:
        most_stable_str = ", ".join([m['id'] for m in normal_machines])
    elif len(normal_machines) == 1:
        most_stable_str = normal_machines[0]['id']
    else:
        most_stable_str = "None"
    
    # === COMMON ISSUES ===
    all_issues = []
    for m in machine_data:
        for issue in m['issues']:
            all_issues.append(issue.get('sensor', 'Unknown'))
    common_issues = list(set(all_issues))
    common_issues_str = ", ".join(common_issues) if common_issues else "None"
    
    # === SYSTEM HEALTH ===
    critical_count = sum(1 for m in machine_data if m['severity'] == 'CRITICAL')
    warning_count = sum(1 for m in machine_data if m['severity'] == 'WARNING')
    normal_count = sum(1 for m in machine_data if m['severity'] == 'NORMAL')
    
    if critical_count > 0:
        system_health = "⚠️ Requires immediate attention"
    elif warning_count > 0:
        system_health = "⚡ Partial attention needed"
    else:
        system_health = "✅ All machines are operating normally"
    
    # Build report in clean markdown format (no ** markers)
    report = f"""| Metric | Value |
|--------|-------|
| **Priority Ranking** | {priority_ranking} |
| **Most Critical** | {most_critical_str} |
| **Most Stable** | {most_stable_str} |
| **Common Issues** | {common_issues_str} |
| **System Health** | {system_health} |"""
    
    return report


# ==================== UI COMPONENTS ====================
def render_gauge(sensor: str, value: float):
    """Render a gauge chart for a sensor."""
    title = sensor.replace('_', ' ').title()
    unit = SENSOR_UNITS.get(sensor, '')
    min_val, max_val = SENSOR_LIMITS.get(sensor, (0, 100))

    if HAS_PLOTLY:
        fig = go.Figure(
            go.Indicator(
                mode='gauge+number',
                value=value,
                title={'text': f"{title} ({unit})", 'font': {'size': 16}},
                gauge={
                    'axis': {'range': [min_val, max_val]},
                    'bar': {'color': '#2E86AB'},
                    'steps': [
                        {'range': [min_val, max_val * 0.6], 'color': '#2ECC71'},
                        {'range': [max_val * 0.6, max_val * 0.85], 'color': '#F1C40F'},
                        {'range': [max_val * 0.85, max_val], 'color': '#E74C3C'}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': max_val * 0.9
                    }
                }
            )
        )
        fig.update_layout(height=250, margin={'t': 20, 'b': 10, 'l': 20, 'r': 20})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.metric(label=f"{title} ({unit})", value=f"{value:.1f}")


def render_trend_chart(readings: List, title: str):
    """Render a trend chart for sensor data."""
    if not readings:
        st.warning("No sensor data available.")
        return

    if HAS_PLOTLY:
        data = {
            'timestamp': [r.timestamp for r in readings],
            'vibration': [r.vibration for r in readings],
            'temperature': [r.temperature for r in readings],
            'pressure': [r.pressure for r in readings],
            'noise_level': [r.noise_level for r in readings]
        }
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        fig = go.Figure()
        for sensor, label in [('vibration', 'Vibration'), ('temperature', 'Temperature'), ('pressure', 'Pressure'), ('noise_level', 'Noise')]:
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df[sensor], mode='lines+markers', name=label))
        
        fig.update_layout(
            title=title,
            xaxis_title='Time',
            yaxis_title='Value',
            legend_title='Sensor',
            height=400,
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart({
            'Vibration': [r.vibration for r in readings],
            'Temperature': [r.temperature for r in readings],
            'Pressure': [r.pressure for r in readings],
            'Noise': [r.noise_level for r in readings]
        })


# ==================== PAGE VIEWS ====================
def render_overview(analysis: Dict[str, Dict]):
    """Render the Multi-Machine Overview page with real-time sensor data."""
    st.subheader("📊 Multi-Machine Overview")
    st.write("Click on a machine card to view detailed diagnostics.")
    st.markdown("")
    
    # Get real-time sensor data
    realtime_sensors = st.session_state.get('realtime_sensors', {})
    
    # Get machine IDs from session state (dynamic based on CSV or default)
    machine_ids = st.session_state.get('machine_ids', MACHINE_IDS)
    
    # Overall System Summary
    st.markdown("---")
    overall_report = generate_overall_summary(analysis)
    st.subheader("📋 Overall System Summary")
    
    # Render overall summary as a SINGLE formatted block
    st.markdown(overall_report)
    st.markdown("---")
    
    # Create columns for machine cards
    cols = st.columns(len(machine_ids))
    
    for idx, (machine_id, details) in enumerate(analysis.items()):
        # 🔹 USE SINGLE SOURCE: Get consistent status from cached analysis
        severity = get_machine_status(machine_id)
        status_text = severity.title()
        color = STATUS_COLOR.get(severity, STATUS_COLOR['UNKNOWN'])
        issues = details['monitoring'].get('issues', [])
        issue_count = len(issues)
        
        # Get real-time sensor values for this machine
        current_sensors = realtime_sensors.get(machine_id, {})

        with cols[idx]:
            # Card container
            st.markdown(
                f"""
                <div style='background-color: {color}; border-radius: 12px; padding: 20px; text-align: center; color: white;'>
                    <h2 style='margin: 0; font-size: 28px;'>{machine_id}</h2>
                    <p style='font-size: 18px; margin: 8px 0;'><strong>{status_text}</strong></p>
                    <p style='font-size: 14px; margin: 4px 0;'>{"⚠️ " + str(issue_count) + " Issues" if issue_count > 0 else "✅ No Issues"}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Real-time sensor metrics
            st.markdown("**Real-Time Sensors:**")
            c1, c2, c3 = st.columns(3)
            with c1:
                temp = current_sensors.get('temperature', 0)
                st.metric("🌡️ Temp", f"{temp:.1f}°C")
            with c2:
                vib = current_sensors.get('vibration', 0)
                st.metric("📳 Vib", f"{vib:.2f}")
            with c3:
                press = current_sensors.get('pressure', 0)
                st.metric("⚙️ Press", f"{press:.1f}")
            
            st.markdown("")
            
            # Clickable button to select machine
            if st.button(f"View Details →", key=f"select_{machine_id}", use_container_width=True):
                st.session_state['selected_machine'] = machine_id
                st.rerun()


def render_machine_detail(machine_id: str, details: Dict, llm_client):
    """Render the Machine Detail page."""
    monitoring = details['monitoring']
    diagnostic = details['diagnostic']
    decision = details['decision']
    maintenance_plan = details['maintenance_plan']
    readings = details['sensor_history']
    
    # 🔹 SINGLE SOURCE OF TRUTH: Use consistent status function
    # DO NOT use monitoring.get('severity', 'normal') - that causes inconsistency!
    severity = get_machine_status(machine_id)
    color = STATUS_COLOR.get(severity, STATUS_COLOR['UNKNOWN'])
    
    # Header with back button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Back to Overview", key="back_button"):
            st.session_state.pop('selected_machine', None)
            st.rerun()
    with col2:
        st.markdown(f"<h2 style='margin: 0;'>Machine {machine_id}</h2>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Severity indicator
    if severity == 'NORMAL':
        st.success(f"🟢 System Status: {severity} - Operating within normal parameters")
    elif severity == 'WARNING':
        st.warning(f"🟡 System Status: {severity} - Attention required")
    elif severity == 'CRITICAL':
        st.error(f"🔴 System Status: {severity} - Immediate action required")
    else:
        st.info(f"⚪ System Status: {severity} - Status unknown")
    
    st.markdown("")
    
    # 🚀 PERFORMANCE: AI Insight with caching
    # 🔹 5. CONTROL LLM - DO NOT call LLM automatically, add button
    with st.expander("🤖 AI-Powered Insight", expanded=True):
        ai_cache = st.session_state.get('ai_insight_cache', {})
        
        # Check if we already have cached insight for this machine
        if machine_id in ai_cache:
            st.info(ai_cache[machine_id])
            # Add button to regenerate
            if st.button("🔄 Regenerate AI Insight", key=f"regen_ai_{machine_id}"):
                # Clear cache for this machine
                st.session_state['ai_insight_cache'].pop(machine_id, None)
                st.rerun()
        elif llm_client:
            # 🔹 5. CONTROL LLM - Only call when button clicked
            if st.button("🚀 Generate AI Insight", key=f"generate_ai_{machine_id}"):
                with st.spinner("Generating AI insight..."):
                    ai_insight = get_ai_insight(machine_id, details, llm_client)
                    # Cache it for future use
                    st.session_state['ai_insight_cache'][machine_id] = ai_insight
                    st.rerun()
        else:
            st.warning("🤖 AI Insight: Add API key in sidebar to enable AI-powered analysis")
    
    st.markdown("---")
    
    # Machine Maintenance Report
    st.subheader("📋 Maintenance Report")
    
    # Get values for the summary
    severity = get_machine_status(machine_id)
    monitoring = details['monitoring']
    diagnostic = details['diagnostic']
    decision = details['decision']
    
    issues = monitoring.get('issues', [])
    if issues:
        issue_types = list(set([i.get('sensor', 'Unknown') for i in issues]))
        issues_str = ", ".join(issue_types)
    else:
        issues_str = "None"
    
    # Trend must use severity-aware calculation
    severity = get_machine_status(machine_id)
    trend = analyze_machine_trend(readings, severity)
    
    root_causes = diagnostic.get('root_causes', [])
    if root_causes:
        cause_str = root_causes[0]
    else:
        cause_str = "No significant issues identified"
    
    actions = decision.get('recommended_actions', [])
    if actions:
        action_str = actions[0]
    else:
        action_str = "Continue monitoring"
    
    # Render machine summary as a SINGLE formatted block
    st.markdown(f"""
    **Machine {machine_id} Summary**
    
    - **Condition:** {severity}
    - **Issues:** {issues_str}
    - **Trend:** {trend}
    - **Cause:** {cause_str}
    - **Action:** {action_str}
    """)
    
    st.markdown("---")
    
    # Real-time Sensor Data Display
    st.subheader("📡 Real-Time Sensor Data")
    
    # Get real-time sensor data from session state
    realtime_sensors = st.session_state.get('realtime_sensors', {})
    current_sensors = realtime_sensors.get(machine_id, {})
    
    # Display sensor metrics in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        temp = current_sensors.get('temperature', readings[-1].temperature if readings else 0)
        st.metric(
            label="🌡️ Temperature",
            value=f"{temp:.1f} °C",
            delta=None
        )
    
    with col2:
        vib = current_sensors.get('vibration', readings[-1].vibration if readings else 0)
        st.metric(
            label="📳 Vibration",
            value=f"{vib:.2f} mm/s",
            delta=None
        )
    
    with col3:
        press = current_sensors.get('pressure', readings[-1].pressure if readings else 0)
        st.metric(
            label="⚙️ Pressure",
            value=f"{press:.1f} bar",
            delta=None
        )
    
    # Show last update time
    last_update = st.session_state.get('last_update')
    if last_update:
        st.caption(f"🕐 Last updated: {last_update.strftime('%H:%M:%S')}")
    
    st.markdown("---")
    
    # Historical Sensor Gauges
    st.subheader("📈 Historical Sensor Data")
    cols = st.columns(4)
    
    sensor_values = {
        'vibration': readings[-1].vibration if readings else 0,
        'temperature': readings[-1].temperature if readings else 0,
        'pressure': readings[-1].pressure if readings else 0,
        'noise_level': readings[-1].noise_level if readings else 0
    }
    
    for idx, (sensor, value) in enumerate(sensor_values.items()):
        with cols[idx]:
            render_gauge(sensor, value)
    
    st.markdown("---")
    
    # Alerts Section
    st.subheader("🚨 Alerts & Issues")
    issues = monitoring.get('issues', [])
    if not issues:
        st.success("No active alerts. All systems operating normally.")
    else:
        for issue in issues:
            sensor = issue.get('sensor', 'Unknown').upper()
            value = issue.get('value')
            unit = issue.get('unit', '')
            severity = issue.get('severity', 'unknown').upper()
            description = issue.get('description', 'No description available')
            
            # Color-code severity badge
            severity_colors = {
                'CRITICAL': '🔴',
                'WARNING': '🟡',
                'NORMAL': '🟢'
            }
            severity_icon = severity_colors.get(severity, '⚪')
            
            if value is not None:
                value_display = f"{value:.2f} {unit}"
            else:
                value_display = "Not Available"
            
            # Create clean alert display
            with st.expander(f"{severity_icon} {sensor}", expanded=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Description:** {description}")
                with col2:
                    st.markdown(f"**Severity:** {severity}")
                st.markdown(f"**Value:** {value_display}")
    
    st.markdown("---")
    
    # Diagnostic Summary
    st.subheader("🔍 Diagnostic Analysis")
    root_causes = diagnostic.get('root_causes', [])
    confidences = diagnostic.get('confidence_scores', {})
    
    if not root_causes:
        st.info("No root causes identified. Machine operating normally.")
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.write("**Identified Root Causes:**")
            for cause in root_causes:
                st.write(f"• {cause}")
        with col2:
            if confidences:
                st.write("**Confidence Scores:**")
                for cause, score in confidences.items():
                    if score <= 1:
                        score = score * 100
                    st.markdown(f"**{cause.replace('_', ' ').title()}:** {score:.0f}%")
                    st.progress(score / 100)
                    st.caption(f"{cause}: {score:.1f}%")
    
    st.markdown("---")
    
    # Recommendations
    st.subheader("💡 Recommendations")
    st.write(f"**Priority Level:** `{decision.get('priority', 'low').upper()}`")
    actions = decision.get('recommended_actions', [])
    if actions:
        for action in actions:
            st.write(f"• {action}")
    else:
        st.info("No specific recommendations at this time.")
    
    st.markdown("---")
    
    # Maintenance Plan - ONLY show for CRITICAL status
    if severity == 'CRITICAL' and maintenance_plan.get('maintenance_plans'):
        st.subheader("🛠️ Maintenance Plan")
        for step in maintenance_plan.get('maintenance_plans', []):
            st.write(f"• {step}")
        st.write(f"**Estimated Total Time:** {maintenance_plan.get('total_estimated_time', 'N/A')}")
        
        safety_notes = maintenance_plan.get('safety_notes', [])
        if safety_notes:
            st.write("**Safety Notes:**")
            for note in safety_notes:
                st.warning(f"⚠️ {note}")
    # For WARNING status, show preventive recommendations only (already shown above)
    # No maintenance plan for WARNING - just recommendations
    
    st.markdown("---")
    
    # Trend Visualization
    st.subheader("📉 Trend Visualization")
    render_trend_chart(readings, f"Sensor History for {machine_id}")


# ==================== MAIN FUNCTION ====================
def main():
    # Page configuration
    st.set_page_config(
        page_title='Predictive Maintenance Dashboard',
        page_icon='🤖',
        layout='wide'
    )
    
    # 🔹 1. Initialize session state ONCE
    init_session_state()
    
    # Initialize data_initialized flag
    if 'data_initialized' not in st.session_state:
        st.session_state['data_initialized'] = False
    
    # Title
    st.title("🤖 Agentic Predictive Maintenance Dashboard")
    st.write("Real-time machine health monitoring with LLM-powered AI agents.")
    st.markdown("")
    
    # Sidebar configuration
    sidebar = st.sidebar
    sidebar.header("⚙️ System Status")
    
    # Clean status info (removed cluttered config elements)
    sidebar.success("✅ System Running")
    sidebar.info("📡 Real-time monitoring active")
    
    sidebar.markdown("---")
    sidebar.header("📊 Data Configuration")
    
    # 🔹 1. File Upload
    uploaded_file = sidebar.file_uploader(
        "Upload Sensor CSV",
        type=["csv"],
        help="Upload a CSV with columns: machine, time, temperature, vibration, pressure"
    )
    
    # Real-time status
    last_update = st.session_state.get('last_update')
    if last_update:
        sidebar.info(f"🕐 Last update: {last_update.strftime('%H:%M:%S')}")
    
    # Data parameters (used for initial load and refresh)
    num_readings = sidebar.slider('Readings per machine', min_value=10, max_value=50, value=20, step=5)
    anomaly_chance = sidebar.slider('Anomaly chance', min_value=0.0, max_value=0.5, value=0.15, step=0.05)
    
    # 🔹 2. Conditional Data Loading
    # 🔹 3. Session State Usage
    # 🔁 Switching Logic: If CSV is uploaded → override; If removed → fallback
    machine_data, data_message = load_data_with_fallback(
        uploaded_file,
        num_readings=num_readings,
        anomaly_chance=anomaly_chance
    )
    
    # 🔹 7. UI Behavior - Show data source message
    if st.session_state.get('data_source') == 'csv':
        sidebar.success(f"📂 Using uploaded dataset")
    else:
        sidebar.info("🔧 Using simulated data")
    
    # 🔹 8. REFRESH LOGIC - When refresh button clicked
    if sidebar.button('🔄 Refresh Sensor Data', use_container_width=True):
        # Only refresh simulated data, not uploaded CSV
        if st.session_state.get('data_source') != 'csv':
            refresh_machine_data(num_readings=num_readings, anomaly_chance=anomaly_chance)
        else:
            # For CSV mode, just update realtime from existing data
            _update_realtime_from_data(machine_data)
        
        # FIX ISSUE 2 & 4: Explicitly clear caches and force rebuild
        st.session_state['analysis_cache'] = None
        st.session_state['ai_insight_cache'] = {}
        st.session_state['force_rebuild'] = True
        st.rerun()
    
    # Show auto-refresh status
    if st.session_state.get('last_refresh'):
        time_since = datetime.now() - st.session_state['last_refresh']
        minutes_passed = time_since.total_seconds() / 60
        minutes_left = AUTO_REFRESH_MINUTES - minutes_passed
        if minutes_left > 0:
            sidebar.info(f"⏱️ Auto-refresh in: {int(minutes_left)} min")
        else:
            sidebar.warning("⏱️ Auto-refresh due now")
    
    # Show data status
    if st.session_state.get('data_initialized'):
        sidebar.success("✅ Sensor data stable")
    else:
        sidebar.info("⏳ Initializing sensors...")
    
    # 🔹 3. Time-Based Auto Refresh (10 minutes) - handled automatically
    # The 10-minute auto-refresh is now built into load_data_with_fallback()
    # This manual interval is kept for faster refreshes if user wants (optional)
    refresh_interval = sidebar.number_input('Manual refresh (seconds)', min_value=0, max_value=120, value=0, help="Optional faster refresh (overrides 10-min auto-refresh)")

    # 🔹 9. ⛔ DISABLE AUTO REFRESH - Only manual refresh allowed
    # (disabled st_autorefresh - uncomment to enable)
    # if AUTO_REFRESH_AVAILABLE and refresh_interval > 0:
    #     st_autorefresh(interval=refresh_interval * 1000, key='dashboard_autorefresh')
    
    # Show current view indicator
    current_view = st.session_state.get('selected_machine')
    if current_view:
        sidebar.info(f"📍 Viewing: {current_view}")
    else:
        sidebar.info("📍 Viewing: Overview")
    
    # Initialize agents (using environment variables for API key)
    agents = init_agents()
    
    # Show agentic mode indicator
    if agents['llm_client']:
        st.success("🧠 AI Agent active")
    else:
        st.info("📊 Running in rule-based mode")
    
    # 🔹 4. Real-Time Data - Get from session state
    realtime_sensors = st.session_state.get('realtime_sensors', {})
    
    # � PERFORMANCE: Use cached analysis if available and data hasn't changed
    # Only rebuild if data source changed or first load
    cached_analysis = st.session_state.get('analysis_cache')
    data_source = st.session_state.get('data_source')
    force_rebuild = st.session_state.get('force_rebuild', False)
    
    needs_rebuild = (
        st.session_state.get('analysis_cache') is None
        or st.session_state.get('force_rebuild', False)
    )
    
    # 🔹 3. PREVENT RECOMPUTATION - If no data, show error and stop
    if not machine_data:
        st.error("No data available")
        st.stop()
    
    if needs_rebuild:
        # Build analysis only on first load
        analysis = build_analysis(machine_data, agents)
        
        # � 1. �🔒 LOCK ANALYSIS - Cache the result
        st.session_state['analysis_cache'] = analysis
        st.session_state['force_rebuild'] = False
    else:
        # Use cached analysis - huge performance improvement
        analysis = cached_analysis
    
    # Render based on navigation state
    if current_view:
        # Show machine detail view
        render_machine_detail(current_view, analysis[current_view], agents['llm_client'])
    else:
        # Show overview
        render_overview(analysis)
    
    # Chatbot section
    st.markdown("---")
    st.subheader("💬 Ask about your machines")
    
    user_question = st.text_input(
        'Ask a question about machine health:',
        placeholder="e.g., Is M1 safe to operate?"
    )
    if st.button('Ask AI', disabled=not agents['llm_client']):
        if user_question and agents['llm_client']:
            # 🔹 FIX: Use selected_machine instead of hardcoded M1
            target_machine = current_view or MACHINE_IDS[0]
            response = agents['chatbot'].answer(user_question, analysis[target_machine], target_machine)
            st.session_state['chat_history'].append((user_question, response))
    
    # Display chat history with RAG-enhanced responses
    for q, a in st.session_state['chat_history'][-5:]:
        st.markdown(f"**You:** {q}")
        # Display RAG response in structured format
        st.info(a)
        st.markdown("---")


if __name__ == '__main__':
    main()
