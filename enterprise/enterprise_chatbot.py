"""
Enterprise Maintenance Copilot

Extends the existing ChatbotAgent with enterprise-level capabilities.
Handles queries across equipment categories and multiple machine types.
Reuses existing AI agents and knowledge base.
"""

import re
import os
import sys
from pathlib import Path

# Add the project root and package directory to Python's import path
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
for path in (str(PACKAGE_DIR), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from chatbot_agent import (
    ChatbotAgent, extract_machine_id, is_machine_related,
    MAINTENANCE_KNOWLEDGE_BASE, KNOWLEDGE_BASE
)
from models import (
    MachineInfo, MachineType, MachineStatus, AlertSeverity, Alert,
    WorkOrder, WorkOrderStatus, MaintenanceLog
)
from simulation import EnterpriseSimulator
from analytics import AnalyticsEngine, get_analytics_engine
from services import get_data_store
from reports import ReportGenerator, get_report_generator
from ml_model import get_predictor, predict_machine_status


ACTIVE_MACHINE_TYPES = {
    "refrigerator": MachineType.REFRIGERATOR,
    "fridge": MachineType.REFRIGERATOR,
    "washing machine": MachineType.WASHING_MACHINE,
    "washer": MachineType.WASHING_MACHINE,
    "air conditioner": MachineType.AIR_CONDITIONER,
    "ac": MachineType.AIR_CONDITIONER,
    "generator": MachineType.GENERATOR,
    "car engine": MachineType.CAR_ENGINE,
    "engine": MachineType.CAR_ENGINE,
}

ACTIVE_MACHINE_ID_PATTERN = r"(REF-\d+|WM-\d+|AC-\d+|GEN-\d+|ENG-\d+)"

CONDITION_SYNONYMS = {
    MachineStatus.NORMAL: [
        "normal", "healthy", "good", "running normally", "operating normally"
    ],
    MachineStatus.WARNING: [
        "warning", "needs attention", "need attention", "attention"
    ],
    MachineStatus.CRITICAL: [
        "critical", "urgent", "high risk", "high-risk"
    ],
}


class EnterpriseCopilot:
    """
    Enterprise Maintenance Copilot - understands the entire equipment fleet.
    Answers questions about specific machines, categories, and the fleet.
    Reuses the existing chatbot_agent for single-machine questions.
    """

    def __init__(self, llm_client=None):
        self.simulator = EnterpriseSimulator()
        self.analytics = get_analytics_engine()
        self.data_store = get_data_store()
        self.report_generator = get_report_generator()
        self.chatbot = ChatbotAgent(llm_client)
        self.llm_client = llm_client

    def answer(self, question: str, analysis: Optional[Dict] = None) -> str:
        """
        Answer an enterprise-level question.
        Routes to the appropriate handler based on question type.
        """
        q = question.lower().strip()

        # Check for machine-specific questions (route to existing chatbot)
        machine_id = extract_machine_id(question)
        if machine_id and not self._is_enterprise_query(q):
            return self._answer_machine_question(machine_id, question)

        # Enterprise-level routing
        if self._is_why_unhealthy(q):
            return self._answer_why_unhealthy(q)
        elif self._is_highest_vibration(q):
            return self._answer_highest_vibration()
        elif self._is_machine_condition_list_query(q):
            return self._answer_machine_condition_list(q)
        elif self._is_show_critical(q):
            return self._answer_show_critical()
        elif self._is_compare_machines(q):
            return self._answer_compare_machines(q)
        elif self._is_maintenance_due(q) and not self._is_machine_type_query(q):
            return self._answer_maintenance_due()
        elif self._is_explain_alerts(q):
            return self._answer_explain_alerts()
        elif self._is_most_frequent_failure(q):
            return self._answer_most_frequent_failure()
        elif self._is_summarize_factory(q):
            return self._answer_summarize_factory(q)
        elif self._is_summarize_line(q):
            return self._answer_summarize_line(q)
        elif self._is_generate_report(q):
            return self._answer_generate_report(q)
        elif self._is_machine_type_query(q):
            return self._answer_machine_type_query(q)
        elif self._is_overall_status(q):
            return self._answer_overall_status()
        elif self._is_health_stats(q):
            return self._answer_health_stats()
        else:
            # Check if any machine-specific patterns
            extracted = self._extract_enterprise_machine_id(q)
            if extracted:
                machine = self.simulator.get_machine(extracted)
                if machine:
                    return self._answer_machine_info(machine)
            
            # Default: try existing chatbot with enterprise context
            if analysis:
                return self._answer_with_enterprise_context(question)
            
            return self._answer_overall_status()

    # ==================== QUERY DETECTION ====================

    def _is_enterprise_query(self, q: str) -> bool:
        """Check if query needs enterprise-level processing."""
        enterprise_patterns = [
            "factory", "line", "plant", "enterprise", "overall",
            "compare", "critical", "all machine", "summary",
            "report", "summarize", "highest", "most frequent",
            "maintenance due", "today's alert", "health",
            "unhealthy", "why is", "category", "equipment",
            "generator", "refrigerator", "washing machine",
            "air conditioner", "car engine"
        ]
        return any(p in q for p in enterprise_patterns)

    def _is_why_unhealthy(self, q: str) -> bool:
        patterns = [r"why is (.*) unhealthy", r"why is (.*) (critical|warning)", 
                    r"what.*wrong with (.*)", r"problem with (.*)"]
        return any(re.search(p, q) for p in patterns)

    def _is_highest_vibration(self, q: str) -> bool:
        patterns = [r"highest vibration", r"highest.*vibrat", r"most vibration", 
                    r"which machine.*vibrat", r"max vibration"]
        return any(re.search(p, q) for p in patterns)

    def _is_show_critical(self, q: str) -> bool:
        patterns = [r"all critical", r"show critical", r"critical machine",
                    r"list.*critical", r"which.*critical"]
        return any(re.search(p, q) for p in patterns)

    def _extract_condition_status(self, q: str) -> Optional[MachineStatus]:
        """Map condition-related wording to machine status."""
        for status, synonyms in CONDITION_SYNONYMS.items():
            if any(term in q for term in synonyms):
                return status
        return None

    def _extract_category_filter(self, q: str) -> Optional[str]:
        """Find a category mentioned in the question using live category names."""
        normalized_q = re.sub(r"\s+", " ", q.lower()).strip()
        factories = self.simulator.get_all_factories()
        category_candidates = []

        for factory_id, factory_info in factories.items():
            category_name = factory_info.get("name", factory_id)
            category_candidates.extend([factory_id, category_name])

        category_candidates.extend(ACTIVE_MACHINE_TYPES.keys())

        for candidate in sorted(set(category_candidates), key=len, reverse=True):
            normalized = str(candidate).lower().replace("_", " ").strip()
            if normalized and re.search(rf"\b{re.escape(normalized)}\b", normalized_q):
                for factory_id, factory_info in factories.items():
                    category_name = factory_info.get("name", factory_id)
                    if normalized in {
                        str(factory_id).lower().replace("_", " ").strip(),
                        str(category_name).lower().replace("_", " ").strip(),
                    }:
                        return category_name
                if candidate in ACTIVE_MACHINE_TYPES:
                    return ACTIVE_MACHINE_TYPES[candidate].value

        return None

    def _is_machine_condition_list_query(self, q: str) -> bool:
        """Detect requests to list machines by status, optionally by category."""
        if not self._extract_condition_status(q):
            return False
        list_terms = [
            "machine", "machines", "show", "list", "which", "what are",
            "what's", "give me", "display"
        ]
        return any(term in q for term in list_terms)

    def _is_compare_machines(self, q: str) -> bool:
        return bool(re.search(r"compare (.*) and (.*)", q))

    def _is_maintenance_due(self, q: str) -> bool:
        patterns = [r"maintenance due", r"maintenance.*today", r"due.*maintenance",
                    r"scheduled maintenance", r"upcoming maintenance"]
        return any(re.search(p, q) for p in patterns)

    def _is_explain_alerts(self, q: str) -> bool:
        patterns = [r"today.*alert", r"explain.*alert", r"alert.*today",
                    r"show.*alert", r"recent alert"]
        return any(re.search(p, q) for p in patterns)

    def _is_most_frequent_failure(self, q: str) -> bool:
        patterns = [r"most frequent", r"failed most", r"highest failure",
                    r"most failure", r"break.*most"]
        return any(re.search(p, q) for p in patterns)

    def _is_summarize_factory(self, q: str) -> bool:
        return bool(re.search(r"summarize (factory|plant) (\w+)", q))

    def _is_summarize_line(self, q: str) -> bool:
        return bool(re.search(r"summarize.*(?:production )?line (\w+)", q))

    def _is_generate_report(self, q: str) -> bool:
        patterns = [r"report", r"generate.*report", r"today.*report",
                    r"weekly report", r"monthly report"]
        return any(re.search(p, q) for p in patterns)

    def _is_machine_type_query(self, q: str) -> bool:
        type_keywords = [
            "refrigerator", "washing machine", "air conditioner", "generator",
            "car engine", "engine"
        ]
        return any(k in q for k in type_keywords)

    def _is_overall_status(self, q: str) -> bool:
        patterns = [r"overall.*status", r"system.*health", r"enterprise.*status",
                    r"how.*everything", r"factory.*status", r"general.*status"]
        return any(re.search(p, q) for p in patterns)

    def _is_health_stats(self, q: str) -> bool:
        patterns = [r"health score", r"average health", r"health.*stat",
                    r"all.*health", r"machine.*health"]
        return any(re.search(p, q) for p in patterns)

    # ==================== ENTERPRISE MACHINE ID EXTRACTION ====================

    def _extract_enterprise_machine_id(self, q: str) -> Optional[str]:
        """Extract enterprise machine IDs from equipment-based questions."""
        patterns = [
            r"(REF-\d+)", r"(WM-\d+)", r"(AC-\d+)", r"(GEN-\d+)",
            r"(ENG-\d+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, q.upper())
            if match:
                return match.group(1)
        return None

    # ==================== ANSWER GENERATORS ====================

    def _answer_machine_condition_list(self, q: str) -> str:
        """List live machines filtered by condition and optional category."""
        status = self._extract_condition_status(q)
        if not status:
            return self._answer_overall_status()

        category_filter = self._extract_category_filter(q)
        machines = self.simulator.get_all_machines()
        if category_filter:
            machines = [
                machine for machine in machines
                if machine.machine_category.lower() == category_filter.lower()
            ]

        filtered = [
            machine for machine in machines
            if machine.status == status
        ]
        filtered.sort(key=lambda machine: machine.machine_id)

        status_title = {
            MachineStatus.NORMAL: "Normal Machines",
            MachineStatus.WARNING: "Warning Machines",
            MachineStatus.CRITICAL: "Critical Machines",
        }.get(status, f"{status.value.title()} Machines")
        if category_filter:
            status_title = f"{category_filter} {status_title}"

        if not filtered:
            return (
                f"## {status_title}\n\n"
                f"No machines are currently in {status.value} condition."
            )

        result = f"## {status_title} ({len(filtered)})\n\n"
        for machine in filtered:
            result += (
                f"- **{machine.machine_id} - {machine.name}** | "
                f"Category: {machine.machine_category} | "
                f"Health Score: {machine.health_score:.1f}% | "
                f"Failure Probability: {machine.failure_probability * 100:.1f}% | "
                f"Current Status: {machine.status.value}\n"
            )

        result += f"\n**Total {status_title}: {len(filtered)}**"
        return result

    def _answer_machine_question(self, machine_id: str, question: str) -> str:
        """Route single-machine questions to existing chatbot."""
        machine = self.simulator.get_machine(machine_id)
        if not machine:
            return f"❌ Machine {machine_id} not found in the enterprise."
        
        # Build analysis context for the chatbot
        analysis = self._build_machine_analysis(machine)
        return self.chatbot.answer(question, analysis, machine_id)

    def _build_machine_analysis(self, machine: MachineInfo) -> Dict:
        """Build analysis dict compatible with existing chatbot."""
        issues = self._get_machine_issues(machine)
        
        # Add ML prediction insights
        ml_pred = getattr(machine, 'ml_prediction', None)
        if ml_pred:
            ml_insight = {
                "sensor": "ML Prediction",
                "severity": ml_pred.get("predicted_status", "NORMAL"),
                "description": (
                    f"ML model predicts {ml_pred.get('predicted_status', 'NORMAL')} "
                    f"with {ml_pred.get('confidence', 0)*100:.1f}% confidence. "
                    f"Probabilities: NORMAL={ml_pred.get('probabilities', {}).get('NORMAL', 0)*100:.1f}%, "
                    f"WARNING={ml_pred.get('probabilities', {}).get('WARNING', 0)*100:.1f}%, "
                    f"CRITICAL={ml_pred.get('probabilities', {}).get('CRITICAL', 0)*100:.1f}%"
                )
            }
            issues.insert(0, ml_insight)
        
        return {
            "monitoring": {
                "severity": machine.status.value,
                "issues": issues
            },
            "sensor_history": [],
            "ml_prediction": ml_pred  # Pass ML prediction to downstream
        }

    def _get_machine_issues(self, machine: MachineInfo) -> List[Dict]:
        """Get issues for a machine."""
        issues = []
        alerts = self.data_store.alert_service.get_alerts_by_machine(machine.machine_id)
        open_alerts = [a for a in alerts if a.status == "Open"]
        
        for alert in open_alerts[:3]:
            issues.append({
                "sensor": alert.reason,
                "severity": alert.severity.value,
                "description": alert.recommended_action
            })
        
        if machine.health_score < 60:
            issues.append({
                "sensor": "health",
                "severity": "CRITICAL",
                "description": f"Health score critically low: {machine.health_score}"
            })
        elif machine.health_score < 85:
            issues.append({
                "sensor": "health",
                "severity": "WARNING",
                "description": f"Health score below threshold: {machine.health_score}"
            })
        
        return issues

    def _answer_why_unhealthy(self, q: str) -> str:
        """Answer why a specific machine is unhealthy."""
        # Extract machine ID
        match = re.search(ACTIVE_MACHINE_ID_PATTERN, q.upper())
        machine_id = match.group(1) if match else None
        
        if not machine_id:
            # Try to find machine by type
            for keyword, mtype in ACTIVE_MACHINE_TYPES.items():
                if keyword in q:
                    # Find the unhealthiest of this type
                    machines = self.simulator.get_machines_by_type(mtype)
                    if machines:
                        unhealthiest = min(machines, key=lambda m: m.health_score)
                        machine_id = unhealthiest.machine_id
                        break
        
        if not machine_id:
            return "❌ Please specify a machine ID (e.g., REF-001, ENG-003)."
        
        machine = self.simulator.get_machine(machine_id)
        if not machine:
            return f"❌ Machine {machine_id} not found."
        
        # Build detailed explanation
        alerts = self.data_store.alert_service.get_alerts_by_machine(machine_id)
        open_alerts = [a for a in alerts if a.status == "Open"]
        
        reasons = []
        if machine.health_score < 60:
            reasons.append(f"🔴 **Critical Health**: Health score is only {machine.health_score}/100")
        elif machine.health_score < 85:
            reasons.append(f"🟡 **Warning Health**: Health score is {machine.health_score}/100")
        
        reasons.append(f"📊 **Failure Probability**: {machine.failure_probability*100:.1f}%")
        
        if open_alerts:
            reasons.append(f"⚠️ **Active Alerts**: {len(open_alerts)} open alerts")
            for alert in open_alerts[:3]:
                reasons.append(f"   - {alert.reason} ({alert.severity.value})")
        
        reasons.append(f"⏱️ **Operating Hours**: {machine.operating_hours:.0f} hours")
        reasons.append(f"📅 **Last Maintenance**: {machine.last_maintenance_date.strftime('%Y-%m-%d') if machine.last_maintenance_date else 'Never'}")
        
        return (
            f"## 🔍 Analysis: {machine.name} ({machine_id})\n\n"
            + "\n".join(reasons) + "\n\n"
            f"**Recommended**: {'Immediate inspection required' if machine.status == MachineStatus.CRITICAL else 'Schedule maintenance soon'}"
        )

    def _answer_highest_vibration(self) -> str:
        """Find machine with highest vibration across enterprise."""
        # Get latest sensor data for all machines
        all_readings = self.simulator.generate_all_sensor_readings(count=5)
        
        max_vibration = -1
        max_machine = None
        max_value = None
        
        for mid, sensors in all_readings.items():
            if "vibration" in sensors and sensors["vibration"]:
                readings = sensors["vibration"]
                avg_vib = sum(r["sensor_value"] for r in readings) / len(readings)
                if avg_vib > max_vibration:
                    max_vibration = avg_vib
                    max_machine = mid
                    max_value = avg_vib
        
        if not max_machine:
            return "❌ No vibration data available."
        
        machine = self.simulator.get_machine(max_machine)
        name = machine.name if machine else max_machine
        
        # Get top 3 highest vibration machines
        vib_list = []
        for mid, sensors in all_readings.items():
            if "vibration" in sensors and sensors["vibration"]:
                readings = sensors["vibration"]
                avg_vib = sum(r["sensor_value"] for r in readings) / len(readings)
                m = self.simulator.get_machine(mid)
                vib_list.append((mid, m.name if m else mid, avg_vib))
        
        vib_list.sort(key=lambda x: x[2], reverse=True)
        
        result = f"## 📳 Highest Vibration Machines\n\n"
        result += f"**#1 {vib_list[0][1]} ({vib_list[0][0]})**: {vib_list[0][2]:.2f} mm/s ← **Highest**\n\n"
        
        if len(vib_list) > 1:
            result += "**Top 5:**\n"
            for i, (mid, mname, vib) in enumerate(vib_list[:5], 1):
                machine = self.simulator.get_machine(mid)
                status = machine.status.value if machine else "UNKNOWN"
                result += f"{i}. {mname} ({mid}): {vib:.2f} mm/s [{status}]\n"
        
        return result

    def _answer_show_critical(self) -> str:
        """List all critical machines across enterprise."""
        all_machines = self.simulator.get_all_machines()
        critical = [m for m in all_machines if m.status == MachineStatus.CRITICAL]
        warning = [m for m in all_machines if m.status == MachineStatus.WARNING]
        
        if not critical and not warning:
            return "✅ **All machines are operating normally.** No critical or warning machines found."
        
        result = "## 🚨 Critical & Warning Machines\n\n"
        
        if critical:
            result += f"### 🔴 Critical ({len(critical)})\n\n"
            result += "| Machine | Name | Health | Type | Category | Manufacturer | Model |\n"
            result += "|---------|------|--------|------|----------|--------------|-------|\n"
            for m in sorted(critical, key=lambda x: x.health_score):
                result += f"| {m.machine_id} | {m.name} | {m.health_score}% | {m.machine_type.value} | {m.machine_category} | {m.manufacturer} | {m.model_number} |\n"
        
        if warning:
            result += f"\n### 🟡 Warning ({len(warning)})\n\n"
            result += "| Machine | Name | Health | Type | Category | Manufacturer | Model |\n"
            result += "|---------|------|--------|------|----------|--------------|-------|\n"
            for m in sorted(warning, key=lambda x: x.health_score):
                result += f"| {m.machine_id} | {m.name} | {m.health_score}% | {m.machine_type.value} | {m.machine_category} | {m.manufacturer} | {m.model_number} |\n"
        
        return result

    def _answer_compare_machines(self, q: str) -> str:
        """Compare two machines."""
        matches = re.findall(ACTIVE_MACHINE_ID_PATTERN, q.upper())
        if len(matches) < 2:
            return "❌ Please specify two machines to compare (e.g., REF-001 and REF-008)."
        
        m1_id, m2_id = matches[0], matches[1]
        m1 = self.simulator.get_machine(m1_id)
        m2 = self.simulator.get_machine(m2_id)
        
        if not m1 or not m2:
            return f"❌ Machines not found: {m1_id if not m1 else ''} {m2_id if not m2 else ''}"
        
        analytics1 = self.analytics.get_machine_analytics(m1_id)
        analytics2 = self.analytics.get_machine_analytics(m2_id)
        
        result = f"## 📊 Comparison: {m1.name} vs {m2.name}\n\n"
        result += "| Metric | " + m1.name + f" ({m1_id}) | " + m2.name + f" ({m2_id}) | Difference |\n"
        result += "|--------|" + "-" * (len(m1.name) + 8) + "|" + "-" * (len(m2.name) + 8) + "|----------|\n"
        
        diff = m1.health_score - m2.health_score
        result += f"| **Health Score** | {m1.health_score}% | {m2.health_score}% | {diff:+.1f}% |\n"
        
        diff = m1.failure_probability - m2.failure_probability
        result += f"| **Failure Prob.** | {m1.failure_probability*100:.1f}% | {m2.failure_probability*100:.1f}% | {diff:+.2f} |\n"
        
        result += f"| **Status** | {m1.status.value} | {m2.status.value} |  |\n"
        result += f"| **Type** | {m1.machine_type.value} | {m2.machine_type.value} |  |\n"
        result += f"| **Category** | {m1.machine_category} | {m2.machine_category} |  |\n"
        result += f"| **Manufacturer** | {m1.manufacturer} | {m2.manufacturer} |  |\n"
        result += f"| **Model** | {m1.model_number} | {m2.model_number} |  |\n"
        result += f"| **Operating Hrs** | {m1.operating_hours:.0f} | {m2.operating_hours:.0f} | {m1.operating_hours - m2.operating_hours:+.0f} |\n"
        result += f"| **MTBF** | {analytics1.mtbf_hours}h | {analytics2.mtbf_hours}h | {analytics1.mtbf_hours - analytics2.mtbf_hours:+.1f}h |\n"
        result += f"| **Availability** | {analytics1.availability_percent}% | {analytics2.availability_percent}% | {analytics1.availability_percent - analytics2.availability_percent:+.1f}% |\n"
        
        return result

    def _answer_maintenance_due(self) -> str:
        """Show machines due for maintenance."""
        all_machines = self.simulator.get_all_machines()
        today = datetime.now()
        due_soon = []
        overdue = []
        
        for m in all_machines:
            if m.next_maintenance_date:
                days_to = (m.next_maintenance_date - today).days
                if days_to < 0:
                    overdue.append((m, abs(days_to)))
                elif days_to <= 7:
                    due_soon.append((m, days_to))
        
        if not overdue and not due_soon:
            return "✅ **No maintenance due today.** All machines are up to date."
        
        result = "## 🔧 Maintenance Due\n\n"
        
        if overdue:
            result += f"### ⏰ Overdue ({len(overdue)})\n\n"
            result += "| Machine | Name | Days Overdue | Health | Type |\n"
            result += "|---------|------|-------------|--------|------|\n"
            for m, days in sorted(overdue, key=lambda x: x[1], reverse=True)[:10]:
                result += f"| {m.machine_id} | {m.name} | {days}d | {m.health_score}% | {m.machine_type.value} |\n"
        
        if due_soon:
            result += f"\n### 📅 Due Within 7 Days ({len(due_soon)})\n\n"
            result += "| Machine | Name | Days Left | Health | Type |\n"
            result += "|---------|------|----------|--------|------|\n"
            for m, days in sorted(due_soon, key=lambda x: x[1]):
                result += f"| {m.machine_id} | {m.name} | {days}d | {m.health_score}% | {m.machine_type.value} |\n"
        
        return result

    def _answer_explain_alerts(self) -> str:
        """Explain today's alerts."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        all_alerts = self.data_store.alert_service.get_all_alerts()
        today_alerts = [a for a in all_alerts if a.timestamp >= today]
        
        if not today_alerts:
            return "✅ **No alerts today.** Everything is operating normally."
        
        result = f"## 🚨 Today's Alerts ({len(today_alerts)})\n\n"
        
        critical = [a for a in today_alerts if a.severity == AlertSeverity.CRITICAL]
        warning = [a for a in today_alerts if a.severity == AlertSeverity.WARNING]
        info = [a for a in today_alerts if a.severity == AlertSeverity.INFO]
        
        if critical:
            result += f"### 🔴 Critical ({len(critical)})\n\n"
            for a in critical:
                machine = self.simulator.get_machine(a.machine_id)
                name = machine.name if machine else a.machine_id
                result += f"- **{name} ({a.machine_id})**: {a.reason}\n"
                result += f"  → Action: {a.recommended_action}\n\n"
        
        if warning:
            result += f"### 🟡 Warning ({len(warning)})\n\n"
            for a in warning[:5]:
                machine = self.simulator.get_machine(a.machine_id)
                name = machine.name if machine else a.machine_id
                result += f"- **{name} ({a.machine_id})**: {a.reason}\n"
        
        if info:
            result += f"\n### ℹ️ Info ({len(info)})\n\n"
            for a in info[:3]:
                machine = self.simulator.get_machine(a.machine_id)
                name = machine.name if machine else a.machine_id
                result += f"- {name}: {a.reason}\n"
        
        return result

    def _answer_most_frequent_failure(self) -> str:
        """Find machine that failed most frequently."""
        all_logs = self.data_store.maintenance_log_service.get_all_logs()
        failure_counts = {}
        
        for log in all_logs:
            if log.maintenance_type in ("Corrective", "Emergency"):
                failure_counts[log.machine_id] = failure_counts.get(log.machine_id, 0) + 1
        
        if not failure_counts:
            return "✅ **No failures recorded.** All machines are well-maintained."
        
        sorted_failures = sorted(failure_counts.items(), key=lambda x: x[1], reverse=True)
        
        result = "## 📊 Most Frequent Failures\n\n"
        result += "| Rank | Machine | Name | Type | Failures | Health |\n"
        result += "|------|---------|------|------|----------|--------|\n"
        
        for i, (mid, count) in enumerate(sorted_failures[:10], 1):
            machine = self.simulator.get_machine(mid)
            name = machine.name if machine else mid
            mtype = machine.machine_type.value if machine else "Unknown"
            health = machine.health_score if machine else "N/A"
            result += f"| {i} | {mid} | {name} | {mtype} | {count} | {health}% |\n"
        
        return result

    def _answer_summarize_factory(self, q: str) -> str:
        """Summarize a specific equipment category."""
        match = re.search(r"(?:factory|plant|category|equipment)\s+([A-Za-z0-9\s-]+)", q, re.IGNORECASE)
        if not match:
            for keyword, mtype in ACTIVE_MACHINE_TYPES.items():
                if keyword in q.lower():
                    factory_id = mtype.value
                    break
            else:
                return "❌ Please specify which category (e.g., Refrigerator or Generator)."
        else:
            factory_name = match.group(1).strip().lower()
            factory_id = None
            for fid, finfo in self.simulator.get_all_factories().items():
                if factory_name in fid.lower() or factory_name in finfo["name"].lower():
                    factory_id = fid
                    break
            if not factory_id:
                return f"❌ Category '{factory_name}' not found."
        
        machines = self.simulator.get_factory_machines(factory_id)
        finfo = self.simulator.get_all_factories()[factory_id]
        analytics = self.analytics.get_factory_analytics(factory_id)
        
        result = f"## �️ Category Summary: {finfo['name']}\n\n"
        result += f"**Total Machines**: {len(machines)}\n"
        result += f"**Manufacturers**: {len(set(m.manufacturer for m in machines))}\n\n"
        
        # Status breakdown
        critical = sum(1 for m in machines if m.status == MachineStatus.CRITICAL)
        warning = sum(1 for m in machines if m.status == MachineStatus.WARNING)
        normal = sum(1 for m in machines if m.status == MachineStatus.NORMAL)
        result += f"- 🔴 Critical: {critical}\n"
        result += f"- 🟡 Warning: {warning}\n"
        result += f"- ✅ Normal: {normal}\n\n"
        
        if analytics:
            result += "**KPIs**:\n"
            result += f"- Average Health: {analytics.get('average_health', 'N/A')}%\n"
            result += f"- Average MTBF: {analytics.get('average_mtbf', 'N/A')}h\n"
            result += f"- Average MTTR: {analytics.get('average_mttr', 'N/A')}h\n"
            result += f"- Average Availability: {analytics.get('average_availability', 'N/A')}%\n"
            result += f"- Total Maintenance Cost: ₹{analytics.get('total_maintenance_cost', 0):,.2f}\n"
        
        return result

    def _answer_summarize_line(self, q: str) -> str:
        """Summarize a machine category group."""
        match = re.search(r"(?:line)\s+(\w+)", q, re.IGNORECASE)
        if not match:
            return "❌ Please specify which machine category group (e.g., L1, L2, L3)."
        
        line_id = match.group(1).upper()
        
        # Find machines in this line
        line_machines = []
        line_name = ""
        factory_id = ""
        for fid, finfo in self.simulator.factories.items():
            for lid, linfo in finfo["lines"].items():
                if lid == line_id:
                    line_machines = linfo["machines"]
                    line_name = linfo["name"]
                    factory_id = fid
                    break
        
        if not line_machines:
            return f"❌ machine category group '{line_id}' not found."
        
        result = f"## 📋 Category Group: {line_name} ({line_id})\n\n"
        
        # Status breakdown
        critical = sum(1 for m in line_machines if m.status == MachineStatus.CRITICAL)
        warning = sum(1 for m in line_machines if m.status == MachineStatus.WARNING)
        normal = sum(1 for m in line_machines if m.status == MachineStatus.NORMAL)
        avg_health = sum(m.health_score for m in line_machines) / len(line_machines) if line_machines else 0
        
        result += f"**Category**: {factory_id}\n"
        result += f"**Total Machines**: {len(line_machines)}\n"
        result += f"**Average Health**: {avg_health:.1f}%\n"
        result += f"- 🔴 Critical: {critical}\n"
        result += f"- 🟡 Warning: {warning}\n"
        result += f"- ✅ Normal: {normal}\n\n"
        
        result += "**Machine List**:\n\n"
        result += "| ID | Name | Type | Health | Status |\n"
        result += "|----|------|------|--------|--------|\n"
        for m in line_machines:
            result += f"| {m.machine_id} | {m.name} | {m.machine_type.value} | {m.health_score}% | {m.status.value} |\n"
        
        return result

    def _answer_generate_report(self, q: str) -> str:
        """Generate a report based on query."""
        if "daily" in q:
            report = self.report_generator.generate_daily_report()
        elif "weekly" in q:
            report = self.report_generator.generate_weekly_report()
        elif "monthly" in q:
            report = self.report_generator.generate_monthly_report()
        else:
            report = self.report_generator.generate_daily_report()
        
        data = report.data
        result = f"## 📊 {report.title}\n\n"
        result += f"**Generated**: {report.generated_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        
        if "total_machines" in data:
            result += "### Overview\n\n"
            result += f"- **Total Machines**: {data['total_machines']}\n"
            result += f"- **Average Health**: {data.get('average_health', 'N/A')}%\n"
            result += f"- **Critical**: {data.get('critical_count', 0)}\n"
            result += f"- **Warning**: {data.get('warning_count', 0)}\n"
            result += f"- **New Alerts**: {data.get('new_alerts', 0)}\n"
            result += f"- **Work Orders**: {data.get('new_work_orders', 0)}\n"
            result += f"- **Maintenance Events**: {data.get('maintenance_events', 0)}\n"
            result += f"- **Total Cost**: ₹{data.get('total_maintenance_cost', 0):,.2f}\n"
        
        return result

    def _answer_machine_type_query(self, q: str) -> str:
        """Answer questions about a specific machine type."""
        for kw, mtype in ACTIVE_MACHINE_TYPES.items():
            if kw in q:
                machines = self.simulator.get_machines_by_type(mtype)
                if not machines:
                    return f"❌ No {mtype.value}s found."
                
                avg_health = sum(m.health_score for m in machines) / len(machines)
                critical = sum(1 for m in machines if m.status == MachineStatus.CRITICAL)
                warning = sum(1 for m in machines if m.status == MachineStatus.WARNING)
                
                result = f"## 🔧 {mtype.value}s Summary\n\n"
                result += f"**Total**: {len(machines)}\n"
                result += f"**Average Health**: {avg_health:.1f}%\n"
                result += f"- 🔴 Critical: {critical}\n"
                result += f"- 🟡 Warning: {warning}\n"
                result += f"- ✅ Normal: {len(machines) - critical - warning}\n\n"
                
                result += "| ID | Name | Health | Status | Category | Manufacturer | Model |\n"
                result += "|----|------|--------|--------|----------|--------------|-------|\n"
                for m in machines:
                    result += f"| {m.machine_id} | {m.name} | {m.health_score}% | {m.status.value} | {m.machine_category} | {m.manufacturer} | {m.model_number} |\n"
                
                return result
        
        return "Please specify an equipment type such as Refrigerator, Washing Machine, Air Conditioner, Generator, or Car Engine."

    def _answer_overall_status(self) -> str:
        """Give overall enterprise status."""
        stats = self.simulator.get_stats()
        
        result = "## �️ Enterprise Overall Status\n\n"
        result += f"**Equipment Categories**: {stats.get('total_categories', stats['total_factories'])}\n"
        result += f"**Total Machines**: {stats['total_machines']}\n"
        result += f"**Average Health**: {stats['average_health']}%\n"
        result += f"**Open Alerts**: {stats['open_alerts']}\n\n"
        
        result += "### Status Distribution\n\n"
        result += f"- ✅ **Healthy**: {stats['healthy_count']}\n"
        result += f"- 🟡 **Warning**: {stats['warning_count']}\n"
        result += f"- 🔴 **Critical**: {stats['critical_count']}\n\n"
        
        result += "### By Category\n\n"
        for fid, count in stats.get('factory_counts', {}).items():
            factory_info = self.simulator.get_all_factories().get(fid, {})
            name = factory_info.get("name", fid)
            result += f"- **{name}**: {count} machines\n"
        
        return result

    def _answer_health_stats(self) -> str:
        """Show health statistics for all machines."""
        all_machines = self.simulator.get_all_machines()
        
        result = "## 💚 Machine Health Overview\n\n"
        result += "| Machine | Name | Type | Health | Failure Prob. | Status |\n"
        result += "|---------|------|------|--------|--------------|--------|\n"
        
        sorted_machines = sorted(all_machines, key=lambda m: m.health_score)
        for m in sorted_machines:
            result += f"| {m.machine_id} | {m.name} | {m.machine_type.value} | {m.health_score}% | {m.failure_probability*100:.1f}% | {m.status.value} |\n"
        
        return result

    def _answer_with_enterprise_context(self, question: str) -> str:
        """Answer using existing chatbot with additional enterprise context."""
        stats = self.simulator.get_stats()
        context = (
            f"\nEnterprise Context:\n"
            f"- {stats.get('total_categories', stats['total_factories'])} equipment categories, {stats['total_machines']} machines total\n"
            f"- Average health: {stats['average_health']}%\n"
            f"- Critical: {stats['critical_count']}, Warning: {stats['warning_count']}\n"
        )
        return f"ℹ️ Enterprise Context:\n{context}\n" + self.chatbot.answer(
            question, 
            {"monitoring": {"severity": "normal", "issues": []}, "sensor_history": []},
            None
        )

    def _answer_machine_info(self, machine: MachineInfo) -> str:
        """Provide detailed info about a machine."""
        analytics = self.analytics.get_machine_analytics(machine.machine_id)
        
        result = f"## ℹ️ {machine.name} ({machine.machine_id})\n\n"
        result += f"- **Type**: {machine.machine_type.value}\n"
        result += f"- **Category**: {machine.machine_category}\n"
        result += f"- **Model**: {machine.model_number}\n"
        result += f"- **Manufacturer**: {machine.manufacturer}\n"
        result += f"- **Status**: {machine.status.value}\n"
        result += f"- **Health Score**: {machine.health_score}%\n"
        result += f"- **Failure Probability**: {machine.failure_probability*100:.1f}%\n"
        result += f"- **Operating Hours**: {machine.operating_hours:.0f}h\n"
        result += f"- **Last Maintenance**: {machine.last_maintenance_date.strftime('%Y-%m-%d') if machine.last_maintenance_date else 'Never'}\n"
        result += f"- **Next Maintenance**: {machine.next_maintenance_date.strftime('%Y-%m-%d') if machine.next_maintenance_date else 'Not scheduled'}\n\n"
        
        if analytics:
            result += "**Analytics**:\n"
            result += f"- MTBF: {analytics.mtbf_hours}h\n"
            result += f"- MTTR: {analytics.mttr_hours}h\n"
            result += f"- Availability: {analytics.availability_percent}%\n"
            result += f"- Utilization: {analytics.utilization_percent}%\n"
        
        return result


# Helper function for backward compatibility
def answer_enterprise_question(question: str, analysis: Optional[Dict] = None) -> str:
    """Convenience function to answer enterprise questions."""
    return EnterpriseCopilot().answer(question, analysis)
