"""
Example usage for the agentic predictive maintenance workflow.
"""

from __future__ import annotations

import os
from pprint import pprint

from data_ingestion import create_sample_csv, generate_machine_data
from model_engine import AgenticMaintenanceEngine


def run_simulated_agentic_example() -> None:
    """Run the full agentic workflow on simulated machine data."""
    print("=" * 70)
    print("AGENTIC AI EXAMPLE: SIMULATED MACHINE ANALYSIS")
    print("=" * 70)

    engine = AgenticMaintenanceEngine(
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        model="meta-llama/llama-3.3-70b-instruct:free",
    )

    results = engine.analyze(
        machine_ids=["M1", "M2", "M3"],
        data_source="simulated",
        num_readings=12,
        verbose=True,
    )

    for machine_id, report in results.items():
        print(f"\n{machine_id}")
        print(f"Severity: {report['severity']}")
        print(f"Mode: {'Agentic AI' if report['agentic_mode'] else 'Rule-based fallback'}")
        print(f"Model: {report['model_used']}")
        print("Monitoring summary:")
        pprint(report["monitoring"])
        if "diagnostic" in report:
            print("Diagnostic summary:")
            pprint(report["diagnostic"])
        if "decision" in report:
            print("Decision summary:")
            pprint(report["decision"])
        if "maintenance_plan" in report:
            print("Maintenance plan:")
            pprint(report["maintenance_plan"])


def run_csv_example() -> None:
    """Run the workflow on a sample CSV file."""
    print("\n" + "=" * 70)
    print("AGENTIC AI EXAMPLE: CSV ANALYSIS")
    print("=" * 70)

    create_sample_csv(output_path="demo_data.csv", num_records=120)
    machine_data = generate_machine_data(
        data_source="csv",
        csv_path="demo_data.csv",
    )

    engine = AgenticMaintenanceEngine(
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        model="meta-llama/llama-3.3-70b-instruct:free",
    )
    results = engine.analyze_machine_data(machine_data)

    for machine_id, report in results.items():
        print(
            f"{machine_id}: severity={report['severity']}, "
            f"issues={len(report['monitoring'].get('issues', []))}, "
            f"agentic={report['agentic_mode']}"
        )


if __name__ == "__main__":
    run_simulated_agentic_example()
    run_csv_example()
