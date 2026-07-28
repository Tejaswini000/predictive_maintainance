"""
Maintenance Logs Enhancement Module

Adds Category Summary Cards, Category Details, Machine Selection,
and Maintenance History to the Maintenance Logs page.

This module is completely separate from the existing Enterprise Table
and does not modify any existing components.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from models import MaintenanceLog, MachineInfo


def compute_category_summary(logs: List[MaintenanceLog], machines: List[MachineInfo], category: str) -> Dict[str, Any]:
    """Compute summary stats for a single machine category."""
    machine_ids = {m.machine_id for m in machines if m.machine_category == category}
    cat_logs = [log for log in logs if log.machine_id in machine_ids]
    
    total_logs = len(cat_logs)
    completed_logs = len([log for log in cat_logs if getattr(log, "status", "Completed") == "Completed"])
    pending_logs = len([log for log in cat_logs if getattr(log, "status", "") != "Completed"])
    total_cost = sum(log.cost for log in cat_logs)
    
    return {
        "category": category,
        "total_logs": total_logs,
        "completed_logs": completed_logs,
        "pending_logs": pending_logs,
        "total_cost": total_cost
    }


def compute_all_category_summaries(logs: List[MaintenanceLog], machines: List[MachineInfo]) -> List[Dict[str, Any]]:
    """Compute summary stats for all machine categories."""
    categories = sorted({m.machine_category for m in machines})
    summaries = []
    for category in categories:
        summary = compute_category_summary(logs, machines, category)
        if summary["total_logs"] > 0:
            summaries.append(summary)
    return summaries


def compute_machine_summary(logs: List[MaintenanceLog], machine_id: str) -> Dict[str, Any]:
    """Compute summary stats for a single machine."""
    machine_logs = [log for log in logs if log.machine_id == machine_id]
    
    total_logs = len(machine_logs)
    completed_logs = len([log for log in machine_logs if getattr(log, "status", "Completed") == "Completed"])
    pending_logs = len([log for log in machine_logs if getattr(log, "status", "") != "Completed"])
    total_cost = sum(log.cost for log in machine_logs)
    
    return {
        "machine_id": machine_id,
        "total_logs": total_logs,
        "completed_logs": completed_logs,
        "pending_logs": pending_logs,
        "total_cost": total_cost
    }


def get_machines_for_category(machines: List[MachineInfo], category: str) -> List[MachineInfo]:
    """Get all machines belonging to a category."""
    return [m for m in machines if m.machine_category == category]


def get_maintenance_history(logs: List[MaintenanceLog], machine_id: str) -> List[MaintenanceLog]:
    """Get maintenance history for a specific machine, sorted by date descending."""
    machine_logs = [log for log in logs if log.machine_id == machine_id]
    machine_logs.sort(key=lambda l: l.maintenance_date, reverse=True)
    return machine_logs