"""
Decision Agent for Predictive Maintenance (Agentic AI)

Suggests actions based on diagnostic results and severity level using LLM-powered reasoning.
"""

from typing import Dict, List, Any, Optional
from scripts.llm_client import OpenRouterClient, AgenticBase


class DecisionAgent(AgenticBase):
    """Agentic decision agent that uses LLM to recommend actions."""
    
    SYSTEM_PROMPT = """You are a predictive maintenance decision expert. Based on the severity level and 
diagnostic findings, recommend appropriate maintenance actions.

Priority guidelines:
- LOW: Continue normal monitoring, no immediate action needed
- MEDIUM: Schedule preventive maintenance within 48-72 hours
- HIGH: Immediate action required, potential emergency shutdown

Actions should be specific, actionable, and prioritized by urgency.

Respond with a JSON object:
{
    "priority": "low|medium|high",
    "recommended_actions": ["action 1", "action 2", ...],
    "estimated_urgency": "Scheduled|Soon|Immediate",
    "reasoning": "Explanation of the decision"
}"""

    def __init__(self, llm_client: Optional[OpenRouterClient] = None):
        """Initialize the decision agent."""
        super().__init__(llm_client)
    
    @staticmethod
    def _normalize_severity(severity: Any) -> str:
        """Extract and normalize severity."""
        if isinstance(severity, dict):
            severity = severity.get('severity') or severity.get('state') or severity.get('status')
        if not isinstance(severity, str):
            return 'NORMAL'
        return severity.strip().upper()

    def _format_root_causes(self, root_causes: List[Any]) -> str:
        """Convert root causes into clean readable bullet format."""
        if not root_causes:
            return "No root causes identified"

        formatted = []
        for rc in root_causes:
            if isinstance(rc, dict):
                # Extract 'cause' safely
                formatted.append(rc.get('cause', str(rc)))
            else:
                formatted.append(str(rc))

        # Better format for LLM understanding
        return "\n".join(f"- {item}" for item in formatted)
    
    def _rule_based_analyze(self, diagnostic_results: Dict[str, Any], severity: Any) -> Dict[str, Any]:
        """Fallback rule-based decision making."""
        severity_label = self._normalize_severity(severity)
        
        if severity_label == 'NORMAL':
            return {
                'priority': 'low',
                'recommended_actions': [],
                'estimated_urgency': 'Scheduled',
                'reasoning': 'No action needed for normal operation'
            }
        
        recommendations = []
        priority = 'medium'
        estimated_urgency = 'Soon'
        
        if severity_label == 'WARNING':
            recommendations = [
                'Reduce machine load where possible',
                'Increase monitoring frequency',
                'Review diagnostic findings and inspect affected systems',
                'Schedule preventive maintenance check'
            ]
        
        elif severity_label == 'CRITICAL':
            recommendations = [
                'Stop the machine safely',
                'Notify the operator and maintenance team immediately',
                'Isolate the equipment if necessary',
                'Perform emergency inspection and repairs'
            ]
            priority = 'high'
            estimated_urgency = 'Immediate'
        
        # Add diagnostic-based recommendations
        root_causes = diagnostic_results.get('root_causes', [])
        if root_causes:
            if severity_label == 'WARNING':
                recommendations.append('Document root causes and review corrective actions')
            elif severity_label == 'CRITICAL':
                recommendations.append('Verify emergency repair scope against diagnostic root causes')
        
        return {
            'priority': priority,
            'recommended_actions': recommendations,
            'estimated_urgency': estimated_urgency,
            'reasoning': f'Rule-based decision: {priority} priority for {severity_label} severity'
        }
    
    def analyze(self, diagnostic_results: Dict[str, Any], severity: Any) -> Dict[str, Any]:
        """
        Recommend actions based on diagnostic results and severity.
        """
        # Fallback if no LLM
        if self.llm is None:
            return self._rule_based_analyze(diagnostic_results, severity)
        
        severity_label = self._normalize_severity(severity)
        
        if severity_label == 'NORMAL':
            return {
                'priority': 'low',
                'recommended_actions': [],
                'estimated_urgency': 'Scheduled',
                'reasoning': 'Machine operating normally'
            }
        
        # ✅ FIXED: Safe formatting
        root_causes = diagnostic_results.get('root_causes', [])
        root_causes_text = self._format_root_causes(root_causes)
        
        user_prompt = f"""Severity: {severity_label}

Root causes identified:
{root_causes_text}

Provide decision and recommendations in JSON format."""
        
        try:
            result = self.llm.chat_json(self.SYSTEM_PROMPT, user_prompt, temperature=0.3)
            return {
                'priority': result.get('priority', 'medium'),
                'recommended_actions': result.get('recommended_actions', []),
                'estimated_urgency': result.get('estimated_urgency', 'Soon'),
                'reasoning': result.get('reasoning', 'LLM decision complete')
            }
        except Exception:
            return self._rule_based_analyze(diagnostic_results, severity)


def decide(diagnostic_results: Dict[str, Any], severity: Any) -> Dict[str, Any]:
    """Convenience wrapper for decision analysis."""
    return DecisionAgent().analyze(diagnostic_results, severity)