"""
Agentic maintenance engine powered by OpenRouter.

This module replaces the old ML classifier with an agent-first workflow that:
- loads machine sensor data
- runs monitoring, diagnostics, decisioning, and planning agents
- returns a structured machine-by-machine report
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from data_ingestion import SensorData, generate_machine_data
from orchestrator import AIOrchestrator


class AgenticMaintenanceEngine:
    """High-level entry point for the agentic maintenance workflow."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.model = model
        self.orchestrator = AIOrchestrator(api_key=self.api_key, model=self.model)

    def analyze_machine_data(
        self,
        machine_data: Dict[str, List[SensorData]],
        verbose: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """Run the full agent pipeline over already-loaded machine data."""
        monitoring_results = {
            machine_id: self.orchestrator.monitoring_agent.evaluate(readings)
            for machine_id, readings in machine_data.items()
        }
        return self.orchestrator.orchestrate(
            monitoring_results=monitoring_results,
            sensor_data=machine_data,
            verbose=verbose,
        )

    def analyze(
        self,
        machine_ids: Optional[List[str]] = None,
        data_source: str = "simulated",
        csv_path: Optional[str] = None,
        num_readings: int = 10,
        verbose: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """Load data and run the full agentic workflow."""
        machine_data = generate_machine_data(
            machine_ids=machine_ids,
            data_source=data_source,
            csv_path=csv_path,
            num_readings=num_readings,
        )
        return self.analyze_machine_data(machine_data, verbose=verbose)

    def get_status(self) -> Dict[str, Any]:
        """Return the current engine configuration."""
        status = self.orchestrator.get_status()
        status["engine"] = "agentic"
        return status


def analyze_machine_data(
    machine_data: Dict[str, List[SensorData]],
    api_key: Optional[str] = None,
    model: str = "meta-llama/llama-3.3-70b-instruct:free",
    verbose: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Convenience wrapper for analyzing an in-memory machine dataset."""
    engine = AgenticMaintenanceEngine(api_key=api_key, model=model)
    return engine.analyze_machine_data(machine_data, verbose=verbose)


def analyze(
    machine_ids: Optional[List[str]] = None,
    data_source: str = "simulated",
    csv_path: Optional[str] = None,
    num_readings: int = 10,
    api_key: Optional[str] = None,
    model: str = "meta-llama/llama-3.3-70b-instruct:free",
    verbose: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Convenience wrapper for loading data and running the agentic workflow."""
    engine = AgenticMaintenanceEngine(api_key=api_key, model=model)
    return engine.analyze(
        machine_ids=machine_ids,
        data_source=data_source,
        csv_path=csv_path,
        num_readings=num_readings,
        verbose=verbose,
    )
