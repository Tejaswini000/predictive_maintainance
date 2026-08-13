"""
Optimized Predictive Maintenance Chatbot Agent (RAG + LLM + Caching)
"""

from typing import Dict, Any, List, Optional
import streamlit as st
from scripts.llm_client import OpenRouterClient, AgenticBase


# ==================== KNOWLEDGE BASE ====================
MAINTENANCE_KNOWLEDGE_BASE = {
    "vibration": {
        "causes": ["Loose bolts", "Misalignment", "Worn bearings"],
        "actions": ["Tighten bolts", "Check alignment", "Inspect bearings"],
    },
    "temperature": {
        "causes": ["Cooling failure", "Overload", "Poor ventilation"],
        "actions": ["Check cooling", "Reduce load", "Improve airflow"],
    },
    "pressure": {
        "causes": ["Leakage", "Pump issue"],
        "actions": ["Check valves", "Inspect pump"],
    },
    "noise": {
        "causes": ["Loose parts", "Gear wear"],
        "actions": ["Tighten components", "Inspect gears"],
    },
}

KNOWLEDGE_BASE = [
    "High vibration indicates imbalance or loose components",
    "High temperature indicates overheating or friction",
    "High pressure can damage internal systems",
    "Noise increase may indicate mechanical wear",
    "Critical condition requires immediate shutdown",
    "Warning condition requires preventive maintenance",
    "Normal condition means all sensors within acceptable range",
]

DOMAIN_KEYWORDS = [
    "machine", "temperature", "vibration", "pressure", "sensor",
    "maintenance", "normal", "warning", "critical", "health",
    "noise", "bearing", "motor", "pump", "valve",
    "failure", "repair", "inspect", "status",
    "m1", "m2", "m3"
]

KEYWORD_MAPPING = {
    "vibration": ["vibrate", "shake", "vibration"],
    "temperature": ["temp", "heat", "hot", "temperature"],
    "pressure": ["pressure", "flow", "bar"],
    "noise": ["noise", "sound", "decibel"],
}


# ==================== RAG FUNCTIONS ====================
def extract_keywords(question: str) -> List[str]:
    question = question.lower()
    keywords = []

    for key, terms in KEYWORD_MAPPING.items():
        if any(term in question for term in terms):
            keywords.append(key)

    return keywords


def retrieve_knowledge(keywords: List[str]) -> str:
    data = []
    for key in keywords:
        if key in MAINTENANCE_KNOWLEDGE_BASE:
            kb = MAINTENANCE_KNOWLEDGE_BASE[key]
            data.append(f"{key.upper()}:")
            data.append(f"Causes: {', '.join(kb['causes'])}")
            data.append(f"Actions: {', '.join(kb['actions'])}")
    return "\n".join(data)


def retrieve_context(question: str) -> List[str]:
    keywords = extract_keywords(question)
    return [
        item for item in KNOWLEDGE_BASE
        if any(k in item.lower() for k in keywords)
    ]


def is_machine_related(question: str) -> bool:
    words = question.lower().split()
    return any(word in DOMAIN_KEYWORDS for word in words)


# ==================== SENSOR CONTEXT ====================
def get_sensor_context(machine_id: str, analysis: Dict[str, Any]) -> str:
    readings = analysis.get("sensor_history", [])

    if not readings:
        return "No sensor data available"

    latest = readings[-1]

    return (
        f"Machine {machine_id} Current Status:\n"
        f"Temperature: {latest.temperature}°C\n"
        f"Vibration: {latest.vibration} mm/s\n"
        f"Pressure: {latest.pressure} bar\n"
    )


# ==================== RESPONSE ENGINE ====================
def rule_based_response(severity: str) -> str:
    severity = severity.lower()

    if severity == "normal":
        return """ANSWER: Safe to operate
CAUSE: Machine severity is NORMAL
RECOMMENDATION: Continue normal operation and routine monitoring"""

    if severity == "warning":
        return """ANSWER: Operate with caution
CAUSE: Machine severity is WARNING
RECOMMENDATION: Inspect the system and take preventive action before continued operation"""

    if severity == "critical":
        return """ANSWER: Not safe to operate
CAUSE: Machine severity is CRITICAL
RECOMMENDATION: Immediate action required. Stop the machine and inspect it now"""

    return "Unable to determine state"


def generate_response(
    question: str,
    machine_id: str,
    analysis: Dict[str, Any],
    llm_client=None,
) -> str:

    # 🚫 Domain validation
    if not is_machine_related(question):
        return "⚠️ Ask only machine-related questions."

    # 🔍 RAG
    keywords = extract_keywords(question)
    kb = retrieve_knowledge(keywords)
    rag_context = retrieve_context(question)
    sensor = get_sensor_context(machine_id, analysis)

    severity = analysis.get("monitoring", {}).get("severity", "normal")
    severity = severity.upper() if severity else "NORMAL"

    context_str = "\n".join(rag_context) if rag_context else kb

    safety_instruction = """IMPORTANT:
You MUST strictly follow the machine severity.

* If NORMAL -> say 'safe to operate'
* If WARNING -> say 'operate with caution'
* If CRITICAL -> say 'not safe to operate'
* NEVER contradict the given severity"""

    prompt = f"""
You are an industrial predictive maintenance expert.

Machine: {machine_id}
Status: {severity}

{safety_instruction}

Sensor Data:
{sensor}

Knowledge:
{context_str}

Question:
{question}

Respond strictly in this format:

ANSWER: ... (MUST reflect the severity above exactly)
CAUSE: ...
RECOMMENDATION: ...
"""

    # 🤖 LLM
    if llm_client:
        try:
            res = llm_client.chat(
                "You are a predictive maintenance expert.",
                prompt,
                temperature=0.7,
                max_tokens=400
            )
            if res:
                return res
        except Exception as e:
            return f"⚠️ AI Error: {str(e)}"

    # fallback - use severity-based response
    return rule_based_response(severity.lower())


# ==================== CACHE ====================
def get_cached_response(question, machine_id, analysis, llm_client):
    if "chat_cache" not in st.session_state:
        st.session_state["chat_cache"] = {}

    key = f"{machine_id}_{question}"

    if key not in st.session_state["chat_cache"]:
        st.session_state["chat_cache"][key] = generate_response(
            question, machine_id, analysis, llm_client
        )

    return st.session_state["chat_cache"][key]


# ==================== MAIN CLASS ====================
class ChatbotAgent(AgenticBase):
    def __init__(self, llm_client: Optional[OpenRouterClient] = None):
        super().__init__(llm_client)

    def answer(self, question: str, analysis: Dict[str, Any], machine_id: str) -> str:
        # Dynamically detect machine ID from question
        detected_machine = extract_machine_id(question)
        
        if detected_machine:
            # Use detected machine ID
            machine_id = detected_machine
        elif machine_id is None:
            # No machine specified in question or as default
            return "Please specify machine (M1, M2, M3)"
        
        return get_cached_response(
            question,
            machine_id,
            analysis,
            self.llm
        )


# ==================== HELPER ====================
def extract_machine_id(question: str) -> str:
    """Extract machine ID from user question (case insensitive)."""
    question_lower = question.lower()
    
    # Check for machine identifiers in the question
    if "m1" in question_lower or "machine 1" in question_lower:
        return "M1"
    if "m2" in question_lower or "machine 2" in question_lower:
        return "M2"
    if "m3" in question_lower or "machine 3" in question_lower:
        return "M3"
    
    return None  # No machine found


def answer_question(question: str, analysis: Dict[str, Any], machine_id: str) -> str:
    return ChatbotAgent().answer(question, analysis, machine_id)
