"""
AI Orchestrator for Predictive Maintenance (Agentic AI)

Coordinates all agents using LLM-powered reasoning.
Activates agents based on machine severity from monitoring results.

Rules:
- NORMAL: run only Monitoring Agent
- WARNING: run Diagnostic and Decision Agents, skip Maintenance Planner
- CRITICAL: run all agents

Output is a machine-wise structured response.
"""

import os
from typing import Dict, List, NamedTuple, Any, Optional
from datetime import datetime
from llm_client import OpenRouterClient
from monitoring_agent import MonitoringAgent
from diagnostic_agent import DiagnosticAgent
from decision_agent import DecisionAgent
from maintenance_planner_agent import MaintenancePlannerAgent


class SensorData(NamedTuple):
    """Represents sensor readings from a machine."""
    machine_id: str
    timestamp: str
    vibration: float
    temperature: float
    pressure: float
    noise_level: float


class AIOrchestrator:
    """Coordinates the agentic agents with LLM-powered reasoning."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the orchestrator with LLM client.
        
        Args:
            api_key: OpenRouter API key. Falls back to OPENROUTER_API_KEY env var.
            model: Model to use for LLM reasoning
        """
        # Initialize LLM client (will be None if no API key provided)
        resolved_model = model or os.environ.get(
            "OPENROUTER_MODEL",
            "meta-llama/llama-3.3-70b-instruct:free",
        )
        self.llm_client = None
        if api_key or os.environ.get("OPENROUTER_API_KEY"):
            try:
                self.llm_client = OpenRouterClient(api_key=api_key, model=resolved_model)
            except ValueError:
                pass
        
        # Initialize agents with LLM client
        self.monitoring_agent = MonitoringAgent(self.llm_client)
        self.diagnostic_agent = DiagnosticAgent(self.llm_client)
        self.decision_agent = DecisionAgent(self.llm_client)
        self.maintenance_planner = MaintenancePlannerAgent(self.llm_client)
        
        self._agentic_mode = self.llm_client is not None
    
    @staticmethod
    def _resolve_severity(value: Any) -> str:
        """Extract and normalize severity from various input types."""
        if isinstance(value, dict):
            severity = value.get('severity') or value.get('state') or value.get('status')
        else:
            severity = value
        if not isinstance(severity, str):
            return 'UNKNOWN'
        severity = severity.strip().upper()
        return severity if severity in {'NORMAL', 'WARNING', 'CRITICAL'} else 'UNKNOWN'

    def orchestrate(
        self,
        monitoring_results: Dict[str, Any],
        sensor_data: Dict[str, List[SensorData]],
        verbose: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """
        Orchestrate agent execution based on severity.
        
        Args:
            monitoring_results: Dict mapping machine_id to monitoring results
            sensor_data: Dict mapping machine_id to list of SensorData
            verbose: Whether to include verbose output
            
        Returns:
            Dict mapping machine_id to complete analysis results
        """
        analysis: Dict[str, Dict[str, Any]] = {}

        for machine_id, readings in sensor_data.items():
            severity = self._resolve_severity(monitoring_results.get(machine_id, 'UNKNOWN'))
            
            machine_report: Dict[str, Any] = {
                'machine_id': machine_id,
                'severity': severity,
                'agentic_mode': self._agentic_mode,
                'model_used': self.llm_client.model if self.llm_client else 'rule-based'
            }
            
            # Always run monitoring
            monitoring = self.monitoring_agent.evaluate(readings)
            machine_report['monitoring'] = monitoring
            
            # Run additional agents based on severity
            if severity == 'WARNING':
                # Run diagnostic and decision
                diagnostic = self.diagnostic_agent.analyze(readings, monitoring)
                machine_report['diagnostic'] = diagnostic
                
                decision = self.decision_agent.analyze(diagnostic, severity)
                machine_report['decision'] = decision
            
            elif severity == 'CRITICAL':
                # Run all agents
                diagnostic = self.diagnostic_agent.analyze(readings, monitoring)
                machine_report['diagnostic'] = diagnostic
                
                decision = self.decision_agent.analyze(diagnostic, severity)
                machine_report['decision'] = decision
                
                root_causes = diagnostic.get('root_causes', [])
                maintenance_plan = self.maintenance_planner.analyze(root_causes, severity)
                machine_report['maintenance_plan'] = maintenance_plan
            
            # Add verbose info if requested
            if verbose:
                machine_report['verbose'] = {
                    'reading_count': len(readings),
                    'latest_reading': readings[-1]._asdict() if readings else None,
                    'agent_execution_order': self._get_execution_order(severity)
                }
            
            analysis[machine_id] = machine_report

        return analysis
    
    def _get_execution_order(self, severity: str) -> List[str]:
        """Get the order of agent execution for a given severity."""
        base_order = ['monitoring']
        if severity == 'WARNING':
            return base_order + ['diagnostic', 'decision']
        elif severity == 'CRITICAL':
            return base_order + ['diagnostic', 'decision', 'maintenance_plan']
        return base_order
    
    def is_agentic(self) -> bool:
        """Check if the orchestrator is running in agentic mode."""
        return self._agentic_mode
    
    def get_status(self) -> Dict[str, Any]:
        """Get the status of the orchestrator."""
        return {
            'agentic_mode': self._agentic_mode,
            'model': self.llm_client.model if self.llm_client else None,
            'agents_initialized': True
        }


def orchestrate(
    monitoring_results: Dict[str, Any],
    sensor_data: Dict[str, List[SensorData]],
    verbose: bool = False
) -> Dict[str, Dict[str, Any]]:
    """Convenience function for orchestrating all machines."""
    orchestrator = AIOrchestrator()
    return orchestrator.orchestrate(monitoring_results, sensor_data, verbose=verbose)
