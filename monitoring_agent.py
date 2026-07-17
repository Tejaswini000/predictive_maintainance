"""
Monitoring Agent for Predictive Maintenance (Agentic AI)

Analyzes a machine's sensor data using LLM-powered reasoning to detect 
abnormal conditions and assign severity labels.
"""

from typing import Dict, List, NamedTuple, Any, Optional
from llm_client import OpenRouterClient, AgenticBase


class SensorData(NamedTuple):
    """Represents a single machine sensor reading."""
    machine_id: str
    timestamp: str
    vibration: float
    temperature: float
    pressure: float
    noise_level: float


class MonitoringAgent(AgenticBase):
    """Agentic monitoring agent that uses LLM for health analysis."""
    
    THRESHOLDS = {
        'vibration': {'normal': (0.0, 2.5), 'warning': (2.5, 3.5), 'critical': (3.5, float('inf'))},
        'temperature': {'normal': (60.0, 85.0), 'warning': (50.0, 60.0), 'warning_upper': (85.0, 100.0), 
                       'critical': ((float('-inf'), 50.0), (100.0, float('inf')))},
        'pressure': {'normal': (90.0, 115.0), 'warning': ((85.0, 90.0), (115.0, 125.0)),
                    'critical': ((float('-inf'), 85.0), (125.0, float('inf')))},
        'noise_level': {'normal': (0.0, 85.0), 'warning': (85.0, 95.0), 'critical': (95.0, float('inf'))}
    }
    
    SYSTEM_PROMPT = """You are a predictive maintenance monitoring expert. Analyze sensor data from industrial machines 
to detect abnormal conditions and assign severity levels.

Classification guidelines:
- NORMAL: All sensors within acceptable ranges
- WARNING: One or more sensors showing elevated values but not critical
- CRITICAL: Sensors indicating immediate risk of failure

Sensor thresholds for classification:
- Vibration: normal 0-2.5 mm/s, warning 2.5-3.5 mm/s, critical >3.5 mm/s
- Temperature: normal 60-85°C, warning 50-60°C or 85-100°C, critical <50°C or >100°C
- Pressure: normal 90-115 bar, warning 85-90 or 115-125 bar, critical <85 or >125 bar
- Noise Level: normal 0-85 dB, warning 85-95 dB, critical >95 dB

Analyze the sensor data and respond with a JSON object containing:
{
    "status": "Brief status description",
    "severity": "NORMAL|WARNING|CRITICAL",
    "issues": [{"sensor": "sensor name", "value": 0.0, "unit": "sensor unit", "severity": "level", "description": "issue description"}],
    "reasoning": "Brief explanation of the assessment"
}"""

    def __init__(self, llm_client: Optional[OpenRouterClient] = None):
        """Initialize the monitoring agent."""
        super().__init__(llm_client)
    
    @classmethod
    def _check_range(cls, value: float, range_def: Any) -> bool:
        """Check if value is within range."""
        if isinstance(range_def[0], tuple):
            return any(low <= value <= high for low, high in range_def)
        return range_def[0] <= value <= range_def[1]
    
    def _rule_based_evaluate(self, readings: List[SensorData]) -> Dict[str, Any]:
        """Fallback rule-based evaluation."""
        if not readings:
            return {'status': 'System is stable', 'severity': 'normal', 'issues': [], 'reasoning': 'No data available'}
        
        latest = readings[-1]
        issues = []
        severity_ranks = {'normal': 0, 'warning': 1, 'critical': 2}
        overall_severity = 'normal'
        
        def update_severity(sensor: str, level: str, value: float, unit: str, description: str):
            nonlocal overall_severity
            if severity_ranks[level] > severity_ranks[overall_severity]:
                overall_severity = level
            # Store structured alert data with separate value and unit
            issues.append({
                'sensor': sensor,
                'value': value,
                'unit': unit,
                'severity': level,
                'description': description
            })
        
        # Vibration check
        vib = latest.vibration
        if vib > 3.5:
            update_severity('vibration', 'critical', vib, 'mm/s', 'High vibration detected')
        elif vib > 2.5:
            update_severity('vibration', 'warning', vib, 'mm/s', 'Elevated vibration detected')
        
        # Temperature check
        temp = latest.temperature
        if temp > 100 or temp < 50:
            update_severity('temperature', 'critical', temp, '°C', 'Temperature out of safe range')
        elif temp > 85 or temp < 60:
            update_severity('temperature', 'warning', temp, '°C', 'Temperature elevated')
        
        # Pressure check
        pres = latest.pressure
        if pres > 125 or pres < 85:
            update_severity('pressure', 'critical', pres, 'bar', 'Pressure outside safe range')
        elif pres > 115 or pres < 90:
            update_severity('pressure', 'warning', pres, 'bar', 'Pressure slightly off')
        
        # Noise check
        noise = latest.noise_level
        if noise > 95:
            update_severity('noise_level', 'critical', noise, 'dB', 'High noise level detected')
        elif noise > 85:
            update_severity('noise_level', 'warning', noise, 'dB', 'Elevated noise level detected')
        
        status_map = {
            'normal': 'System is stable',
            'warning': 'System requires attention',
            'critical': 'System requires immediate action'
        }
        
        return {
            'status': status_map.get(overall_severity, 'Unknown'),
            'severity': overall_severity.upper(),
            'issues': issues,
            'reasoning': f'Rule-based analysis: {len(issues)} issue(s) detected'
        }
    
    def evaluate(self, readings: List[SensorData]) -> Dict[str, Any]:
        """
        Evaluate machine sensor data and assign a severity level.
        
        Args:
            readings: List of SensorData for one machine
            
        Returns:
            Dictionary with status, severity, issues list, and reasoning
        """
        # If no LLM client, use rule-based fallback
        if self.llm is None:
            return self._rule_based_evaluate(readings)
        
        if not readings:
            return {'status': 'System is stable', 'severity': 'NORMAL', 'issues': [], 'reasoning': 'No data available'}
        
        # Format sensor data for LLM
        sensor_info = self._format_sensor_data(readings)
        
        user_prompt = f"""Analyze this machine's sensor data:

{sensor_info}

Provide your assessment in JSON format."""

        try:
            result = self.llm.chat_json(self.SYSTEM_PROMPT, user_prompt, temperature=0.3)
            # Ensure required fields exist
            normalized_issues = []
            latest = readings[-1]
            sensor_units = {
                'vibration': 'mm/s',
                'temperature': '°C',
                'pressure': 'bar',
                'noise_level': 'dB'
            }

            for issue in result.get('issues', []):
                sensor_name = issue.get('sensor')
                normalized_issues.append({
                    'sensor': sensor_name,
                    'value': issue.get('value', getattr(latest, sensor_name, None) if sensor_name else None),
                    'unit': issue.get('unit', sensor_units.get(sensor_name, '')),
                    'severity': issue.get('severity', 'warning'),
                    'description': issue.get('description', 'Issue detected')
                })

            return {
                'status': result.get('status', 'Analyzing'),
                'severity': result.get('severity', 'NORMAL'),
                'issues': normalized_issues,
                'reasoning': result.get('reasoning', 'LLM analysis complete')
            }
        except Exception as e:
            # Fallback to rule-based on LLM failure
            return self._rule_based_evaluate(readings)


def evaluate_machine(readings: List[SensorData]) -> Dict[str, Any]:
    """Convenience wrapper - creates agent and evaluates."""
    # Will be connected to global LLM client in orchestrator
    return MonitoringAgent().evaluate(readings)
