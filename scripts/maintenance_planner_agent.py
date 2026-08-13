"""
Maintenance Planner Agent for Predictive Maintenance (Agentic AI)

Generates maintenance plans based on root causes and severity using LLM-powered reasoning.
"""

from typing import Dict, List, Any, Optional
from scripts.llm_client import OpenRouterClient, AgenticBase


class MaintenancePlannerAgent(AgenticBase):
    """Agentic maintenance planner that uses LLM to generate plans."""
    
    SYSTEM_PROMPT = """You are a predictive maintenance planning expert. Generate detailed maintenance 
plans based on identified root causes and severity levels.

For WARNING severity:
- Focus on preventive maintenance
- Schedule activities within 48-72 hours
- Include inspection and monitoring steps

For CRITICAL severity:
- Focus on emergency corrective maintenance
- Immediate action required
- Include safety precautions and emergency protocols

Respond with a JSON object:
{
    "maintenance_plans": ["step 1", "step 2", ...],
    "total_estimated_time": "X hours",
    "safety_notes": ["safety note 1", ...],
    "reasoning": "Explanation of the maintenance plan"
}"""

    def __init__(self, llm_client: Optional[OpenRouterClient] = None):
        """Initialize the maintenance planner agent."""
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
        """Convert root causes (dict or str) into readable text."""
        if not root_causes:
            return 'No specific root causes identified'
        
        formatted = []
        for rc in root_causes:
            if isinstance(rc, dict):
                formatted.append(
                    rc.get('cause') or 
                    rc.get('issue') or 
                    rc.get('description') or 
                    str(rc)
                )
            else:
                formatted.append(str(rc))
        
        return '; '.join(formatted)
    
    def _rule_based_analyze(self, root_causes: List[Any], severity: Any) -> Dict[str, Any]:
        """Fallback rule-based maintenance planning."""
        severity_label = self._normalize_severity(severity)
        root_causes_text = self._format_root_causes(root_causes)
        
        if severity_label == 'NORMAL':
            return {
                'maintenance_plans': [],
                'total_estimated_time': '0 hours',
                'safety_notes': [],
                'reasoning': 'No maintenance needed for normal operation'
            }
        
        plans = []
        safety_notes = []
        total_time = 0
        
        if severity_label == 'WARNING':
            plans = [
                'Inspect affected systems identified in diagnostics',
                'Check lubrication and coolant levels',
                'Tighten loose mechanical components',
                'Schedule preventive maintenance within the next 48 hours',
                'Monitor sensor readings hourly for any changes'
            ]
            safety_notes = [
                'Follow standard safety procedures',
                'Wear protective gloves and eye protection',
                'Ensure the machine is powered down before inspection'
            ]
            total_time = 2
        
        elif severity_label == 'CRITICAL':
            plans = [
                'Immediately stop the machine and isolate power sources',
                'Inspect bearings, shafts, seals, and alignment',
                'Replace worn or damaged components as identified',
                'Perform a full system diagnostic check after repairs',
                'Run the machine at low load and monitor sensor values for stability',
                'Document all repairs and confirm equipment readiness before restart'
            ]
            safety_notes = [
                'Lockout/tagout all energy sources before service',
                'Use hearing protection and safety glasses',
                'Verify emergency stop systems are functional',
                'Keep a fire extinguisher and first aid kit nearby'
            ]
            total_time = 6
        
        return {
            'maintenance_plans': plans,
            'total_estimated_time': f'{total_time} hours',
            'safety_notes': safety_notes,
            'reasoning': f'Rule-based plan for {severity_label}. Causes: {root_causes_text}'
        }
    
    def analyze(self, root_causes: List[Any], severity: Any) -> Dict[str, Any]:
        """
        Generate a maintenance plan based on root causes and severity.
        """
        # If no LLM client, use rule-based fallback
        if self.llm is None:
            return self._rule_based_analyze(root_causes, severity)
        
        severity_label = self._normalize_severity(severity)
        
        if severity_label == 'NORMAL':
            return {
                'maintenance_plans': [],
                'total_estimated_time': '0 hours',
                'safety_notes': [],
                'reasoning': 'Machine operating normally, no maintenance required'
            }
        
        # ✅ FIXED HERE
        root_causes_text = self._format_root_causes(root_causes)
        
        user_prompt = f"""Severity: {severity_label}

Root causes to address:
{root_causes_text}

Generate a detailed maintenance plan in JSON format."""

        try:
            result = self.llm.chat_json(self.SYSTEM_PROMPT, user_prompt, temperature=0.3)
            return {
                'maintenance_plans': result.get('maintenance_plans', []),
                'total_estimated_time': result.get('total_estimated_time', '0 hours'),
                'safety_notes': result.get('safety_notes', []),
                'reasoning': result.get('reasoning', 'LLM planning complete')
            }
        except Exception:
            return self._rule_based_analyze(root_causes, severity)


def plan_maintenance(root_causes: List[Any], severity: Any) -> Dict[str, Any]:
    """Convenience wrapper for maintenance planning."""
    return MaintenancePlannerAgent().analyze(root_causes, severity)