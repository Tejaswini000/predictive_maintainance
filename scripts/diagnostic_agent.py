"""
Diagnostic Agent for Predictive Maintenance (Agentic AI)

Analyzes sensor data and monitoring severity using LLM-powered reasoning 
to identify likely root causes.
"""

from typing import Dict, List, NamedTuple, Any, Optional
from scripts.llm_client import OpenRouterClient, AgenticBase


class SensorData(NamedTuple):
    """Represents a single machine sensor reading."""
    machine_id: str
    timestamp: str
    vibration: float
    temperature: float
    pressure: float
    noise_level: float


class DiagnosticAgent(AgenticBase):
    """Agentic diagnostic agent that uses LLM to identify root causes."""
    
    SYSTEM_PROMPT = """You are a predictive maintenance diagnostic expert. Analyze sensor data and monitoring 
results to identify the root causes of anomalies.

Common root causes to consider:
- Imbalance or misalignment (from vibration patterns)
- Overheating (from temperature trends)
- Bearing wear or failure (from vibration + temperature)
- Seal failure or pressure issues (from pressure anomalies)
- Mechanical degradation (from noise patterns)
- Lubrication issues (from temperature + vibration combined)
- Electrical issues (from irregular sensor patterns)

Analyze the sensor data and monitoring results, then respond with a JSON object:
{
    "root_causes": ["list of identified root causes with explanations"],
    "confidence_scores": {"cause_name": 0.0-1.0 confidence score},
    "reasoning": "Detailed explanation of the diagnosis"
}"""

    def __init__(self, llm_client: Optional[OpenRouterClient] = None):
        """Initialize the diagnostic agent."""
        super().__init__(llm_client)
    
    @staticmethod
    def _resolve_severity(monitoring_results: Any) -> str:
        """Extract severity from monitoring results."""
        if isinstance(monitoring_results, dict):
            severity = monitoring_results.get('severity') or monitoring_results.get('state') or monitoring_results.get('status')
        else:
            severity = monitoring_results
        if not isinstance(severity, str):
            return 'NORMAL'
        return severity.strip().upper()
    
    def _rule_based_analyze(self, readings: List[SensorData], monitoring_results: Any) -> Dict[str, Any]:
        """Fallback rule-based diagnosis."""
        severity = self._resolve_severity(monitoring_results)
        
        if severity == 'NORMAL':
            return {'root_causes': [], 'confidence_scores': {}, 'reasoning': 'No diagnosis needed for normal state'}
        
        if not readings:
            return {'root_causes': [], 'confidence_scores': {}}
        
        latest = readings[-1]
        root_causes = []
        confidence_scores = {}
        
        # Rule-based root cause detection
        if latest.vibration > 3.5:
            root_causes.append('Imbalance or misalignment due to high vibration')
            confidence_scores['imbalance'] = 0.9
        elif latest.vibration > 2.5:
            root_causes.append('Possible imbalance from elevated vibration')
            confidence_scores['imbalance'] = 0.6
        
        if latest.temperature > 100:
            root_causes.append('Overheating from excessive temperature')
            confidence_scores['overheating'] = 0.95
        elif latest.temperature > 85:
            root_causes.append('Potential overheating from elevated temperature')
            confidence_scores['overheating'] = 0.65
        
        if latest.noise_level > 95:
            root_causes.append('Mechanical degradation indicated by high noise level')
            confidence_scores['mechanical_degradation'] = 0.9
        elif latest.noise_level > 85:
            root_causes.append('Possible mechanical degradation from elevated noise')
            confidence_scores['mechanical_degradation'] = 0.55
        
        if latest.pressure < 85 or latest.pressure > 125:
            root_causes.append('Seal failure or pressure system issue')
            confidence_scores['seal_failure'] = 0.85
        elif latest.pressure < 90 or latest.pressure > 115:
            root_causes.append('Pressure drift indicating possible seal wear')
            confidence_scores['seal_failure'] = 0.5
        
        if not root_causes:
            root_causes.append('No clear root cause found; data requires further review')
        
        return {
            'root_causes': root_causes,
            'confidence_scores': confidence_scores,
            'reasoning': f'Rule-based analysis: {len(root_causes)} root cause(s) identified'
        }
    
    def analyze(self, readings: List[SensorData], monitoring_results: Any) -> Dict[str, Any]:
        """
        Analyze sensor patterns and return root causes.
        
        Args:
            readings: List of SensorData for a machine
            monitoring_results: Monitoring output containing severity
            
        Returns:
            Dictionary with root_causes and confidence_scores
        """
        # If no LLM client, use rule-based fallback
        if self.llm is None:
            return self._rule_based_analyze(readings, monitoring_results)
        
        severity = self._resolve_severity(monitoring_results)
        
        if severity == 'NORMAL':
            return {
                'root_causes': [],
                'confidence_scores': {},
                'reasoning': 'Machine is operating normally'
            }
        
        if not readings:
            return {
                'root_causes': [],
                'confidence_scores': {}
            }
        
        # Format data for LLM
        sensor_info = self._format_sensor_data(readings)
        issues_info = self._format_anomalies(monitoring_results.get('issues', []))
        
        user_prompt = f"""Machine severity: {severity}

Sensor data:
{sensor_info}

Detected issues:
{issues_info}

Provide root cause analysis in JSON format."""

        try:
            result = self.llm.chat_json(self.SYSTEM_PROMPT, user_prompt, temperature=0.3)
            return {
                'root_causes': result.get('root_causes', []),
                'confidence_scores': result.get('confidence_scores', {}),
                'reasoning': result.get('reasoning', 'LLM diagnosis complete')
            }
        except Exception as e:
            return self._rule_based_analyze(readings, monitoring_results)


def diagnose(readings: List[SensorData], monitoring_results: Any) -> Dict[str, Any]:
    """Convenience wrapper for diagnostic analysis."""
    return DiagnosticAgent().analyze(readings, monitoring_results)
