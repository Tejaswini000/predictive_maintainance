"""
Enterprise Services for Predictive Maintenance Platform

Manages work orders, maintenance logs, alert lifecycle, and technician assignment.
Reuses existing AI agents for diagnostics and decision-making.
"""

import uuid
import random
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta

from models import (
    MachineInfo, MachineStatus, Alert, AlertSeverity,
    WorkOrder, WorkOrderStatus, MaintenanceLog, MaintenanceType,
    MachineType
)


# ==================== WORK ORDER SERVICE ====================

class WorkOrderService:
    """Manages the complete work order lifecycle."""

    def __init__(self):
        self.work_orders: Dict[str, WorkOrder] = {}
        self.technicians = [
            "Rajesh Kumar", "Priya Sharma", "Amit Singh", 
            "Sneha Patel", "Vikram Reddy", "Anita Desai"
        ]
        self._next_id = 0

    def _generate_id(self) -> str:
        """Generate a unique work order ID."""
        self._next_id += 1
        return f"WO-{self._next_id:04d}"

    def _get_store(self):
        """Get the EnterpriseDataStore singleton."""
        store_cls = globals().get("EnterpriseDataStore")
        return getattr(store_cls, "_instance", None) if store_cls else None

    def create_work_order(
        self,
        machine_id: str,
        title: str,
        description: str,
        priority: str = "Medium",
        assigned_technician: Optional[str] = None,
        estimated_hours: float = 0.0,
        scheduled_date: Optional[date] = None,
        created_by: str = "AI System",
        alert_id: Optional[str] = None
    ) -> WorkOrder:
        """Create a new work order from AI-detected issues."""
        for existing in self.work_orders.values():
            if (
                existing.machine_id == machine_id and
                existing.status in (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)
            ):
                if alert_id and not existing.alert_id:
                    existing.alert_id = alert_id
                return existing

        assigned_tech = assigned_technician or self._assign_technician()

        wo = WorkOrder(
            work_order_id=self._generate_id(),
            machine_id=machine_id,
            title=title,
            description=description,
            status=WorkOrderStatus.OPEN,
            priority=priority,
            assigned_technician=assigned_tech,
            created_date=datetime.now(),
            scheduled_date=scheduled_date or (date.today() + timedelta(days=1)),
            due_date=scheduled_date or (date.today() + timedelta(days=1)),
            estimated_hours=estimated_hours or self._estimate_hours(priority),
            created_by=created_by,
            alert_id=alert_id
        )
        self.work_orders[wo.work_order_id] = wo

        # Auto-create a Scheduled Preventive Maintenance Log linked to this work order
        self._create_scheduled_maintenance_log(wo)

        return wo

    def _create_scheduled_maintenance_log(self, wo: WorkOrder):
        """Create a Scheduled Maintenance Log when a work order is created."""
        store = self._get_store()
        if not store or not getattr(store, "_initialized", False):
            return

        machine = None
        try:
            from simulation import EnterpriseSimulator
            machine = EnterpriseSimulator().get_machine(wo.machine_id)
        except Exception:
            pass

        machine_name = wo.machine_name or (machine.name if machine else "")
        category = wo.category or (machine.machine_category if machine else "")
        before_health = wo.current_health_score or (machine.health_score if machine else 0.0)

        # Estimated duration defaults to 2 Hours for scheduled logs
        estimated_duration = 2.0

        store.maintenance_log_service.add_log(
            machine_id=wo.machine_id,
            technician=wo.assigned_technician,
            maintenance_type=MaintenanceType.PREVENTIVE,
            issue=wo.issue_description or wo.title,
            action_taken="",
            cost=0.0,
            duration_hours=estimated_duration,
            remarks="",
            work_order_id=wo.work_order_id,
            machine_name=machine_name,
            category=category,
            description="Preventive maintenance scheduled automatically after AI prediction.",
            start_time=datetime.now(),
            end_time=None,
            downtime_hours=0.0,
            before_health=before_health,
            after_health=0.0,
            status="Scheduled"
        )

    def _assign_technician(self) -> str:
        """Auto-assign a technician (round-robin simulation)."""
        return random.choice(self.technicians)

    def _estimate_hours(self, priority: str) -> float:
        """Estimate hours based on priority."""
        estimates = {
            "Low": 2.0,
            "Medium": 4.0,
            "High": 8.0,
            "Critical": 12.0
        }
        return estimates.get(priority, 4.0)

    def update_status(self, work_order_id: str, new_status: WorkOrderStatus) -> bool:
        """Update work order status."""
        wo = self.work_orders.get(work_order_id)
        if not wo:
            return False
        wo.status = new_status
        if new_status == WorkOrderStatus.COMPLETED:
            wo.completed_date = datetime.now()
            # Update the existing maintenance log (created when work order was created)
            self._complete_maintenance_log_from_work_order(wo)
        return True

    def assign_technician(self, work_order_id: str, technician: str) -> bool:
        """Assign/reassign technician."""
        wo = self.work_orders.get(work_order_id)
        if not wo:
            return False
        wo.assigned_technician = technician
        return True

    def update_progress(self, work_order_id: str, actual_hours: float,
                        parts_replaced: List[str], cost: float, remarks: str) -> bool:
        """Update work order progress."""
        wo = self.work_orders.get(work_order_id)
        if not wo:
            return False
        wo.actual_hours = actual_hours
        wo.parts_replaced = parts_replaced
        wo.cost = cost
        wo.remarks = remarks
        return True

    def get_work_orders_by_machine(self, machine_id: str) -> List[WorkOrder]:
        """Get all work orders for a machine."""
        return [wo for wo in self.work_orders.values() if wo.machine_id == machine_id]

    def get_work_orders_by_status(self, status: WorkOrderStatus) -> List[WorkOrder]:
        """Get work orders by status."""
        return [wo for wo in self.work_orders.values() if wo.status == status]

    def get_all_work_orders(self) -> List[WorkOrder]:
        """Get all work orders."""
        return list(self.work_orders.values())

    def get_open_work_orders(self) -> List[WorkOrder]:
        """Get open and in-progress work orders."""
        return [
            wo for wo in self.work_orders.values()
            if wo.status in (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)
        ]

    def has_active_work_order(self, machine_id: str) -> bool:
        """Return True if a machine already has an open or in-progress work order."""
        return any(
            wo.machine_id == machine_id and
            wo.status in (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)
            for wo in self.work_orders.values()
        )

    def get_work_order_summary(self) -> Dict[str, int]:
        """Get summary of work orders by status."""
        summary = {"Open": 0, "In Progress": 0, "Completed": 0, "Cancelled": 0}
        for wo in self.work_orders.values():
            summary[wo.status.value] = summary.get(wo.status.value, 0) + 1
        return summary

    def auto_create_from_alert(self, alert: Alert, machine_name: str) -> WorkOrder:
        """Auto-create a work order from a critical/warning alert."""
        priority_map = {
            AlertSeverity.CRITICAL: "Critical",
            AlertSeverity.WARNING: "High",
            AlertSeverity.INFO: "Low"
        }
        return self.create_work_order(
            machine_id=alert.machine_id,
            title=f"Maintenance Required: {machine_name}",
            description=f"Alert: {alert.reason}\nRecommended: {alert.recommended_action}",
            priority=priority_map.get(alert.severity, "Medium"),
            scheduled_date=date.today() + timedelta(days=1 if alert.severity == AlertSeverity.WARNING else 0),
            alert_id=alert.alert_id
        )

    def auto_create_from_machine_status(self, machine: MachineInfo, alert: Optional[Alert] = None) -> Optional[WorkOrder]:
        """Create one active work order for warning or critical machine states."""
        if machine.status == MachineStatus.NORMAL:
            return None
        if machine.status not in (MachineStatus.WARNING, MachineStatus.CRITICAL):
            return None

        is_critical = machine.status == MachineStatus.CRITICAL
        maintenance_type = MaintenanceType.CORRECTIVE if is_critical else MaintenanceType.PREVENTIVE
        priority = "High" if is_critical else "Medium"
        due_date = date.today() if is_critical else date.today() + timedelta(days=1)
        issue_description = (
            f"{machine.name} is in {machine.status.value} status with "
            f"{machine.health_score:.1f}% health."
        )
        ai_recommendation = (
            "Perform corrective maintenance immediately and inspect critical subsystems."
            if is_critical
            else "Schedule preventive maintenance and inspect sensors before condition worsens."
        )

        wo = self.create_work_order(
            machine_id=machine.machine_id,
            title=f"{maintenance_type.value} Maintenance: {machine.name}",
            description=(
                f"Machine ID: {machine.machine_id}\n"
                f"Machine Name: {machine.name}\n"
                f"Category: {machine.machine_category}\n"
                f"Current Health Score: {machine.health_score:.1f}%\n"
                f"Current Status: {machine.status.value}\n"
                f"Priority: {priority}\n"
                f"Maintenance Type: {maintenance_type.value}\n"
                f"Issue Description: {issue_description}\n"
                f"AI Recommendation: {ai_recommendation}"
            ),
            priority=priority,
            scheduled_date=due_date,
            estimated_hours=self._estimate_hours(priority),
            alert_id=alert.alert_id if alert else None
        )
        wo.due_date = due_date
        wo.machine_name = machine.name
        wo.category = machine.machine_category
        wo.current_health_score = machine.health_score
        wo.current_status = machine.status.value
        wo.maintenance_type = maintenance_type.value
        wo.issue_description = issue_description
        wo.ai_recommendation = ai_recommendation
        return wo

    def _complete_maintenance_log_from_work_order(self, wo: WorkOrder):
        """Update the existing scheduled maintenance log when a work order is completed."""
        store_cls = globals().get("EnterpriseDataStore")
        store = getattr(store_cls, "_instance", None) if store_cls else None
        if not store or not getattr(store, "_initialized", False):
            return

        # Find the existing maintenance log linked to this work order
        existing_log = store.maintenance_log_service.get_log_by_work_order(wo.work_order_id)
        if not existing_log:
            # If no log exists (e.g., legacy data), create one
            self._create_scheduled_maintenance_log(wo)
            existing_log = store.maintenance_log_service.get_log_by_work_order(wo.work_order_id)
            if not existing_log:
                return

        machine = None
        try:
            from simulation import EnterpriseSimulator
            machine = EnterpriseSimulator().get_machine(wo.machine_id)
        except Exception:
            pass

        before_health = existing_log.before_health or wo.current_health_score or (machine.health_score if machine else 0)
        after_health = before_health
        if machine:
            after_health = min(100.0, max(before_health, before_health + (18 if wo.priority == "High" else 10)))
            machine.health_score = round(after_health, 1)
            machine.failure_probability = round(max(0.01, (100 - machine.health_score) / 100 * 0.45), 3)
            if machine.health_score >= 70:
                machine.status = MachineStatus.NORMAL

        maintenance_type = MaintenanceType.CORRECTIVE if wo.priority == "High" else MaintenanceType.PREVENTIVE
        if wo.maintenance_type:
            try:
                maintenance_type = MaintenanceType(wo.maintenance_type)
            except ValueError:
                maintenance_type = MaintenanceType.CORRECTIVE if wo.priority == "High" else MaintenanceType.PREVENTIVE

        duration = wo.actual_hours or wo.estimated_hours or self._estimate_hours(wo.priority)
        end_time = wo.completed_date or datetime.now()
        start_time = existing_log.start_time or (end_time - timedelta(hours=duration))

        # Update the existing log with completion data
        store.maintenance_log_service.update_log(
            existing_log.log_id,
            status="Completed",
            maintenance_type=maintenance_type,
            action_taken=wo.ai_recommendation or wo.description,
            parts_replaced=wo.parts_replaced,
            cost=wo.cost or self._estimate_hours(wo.priority) * 1200,
            duration_hours=duration,
            remarks=wo.remarks,
            description=wo.description,
            start_time=start_time,
            end_time=end_time,
            downtime_hours=duration,
            after_health=after_health,
            maintenance_date=datetime.now()
        )

        # Per requirement: Alert remains Open. Do NOT resolve it here.
        # The alert is resolved independently by the alert service when appropriate.
        pass

    def delete_work_order(self, work_order_id: str) -> bool:
        """Delete a work order and its linked maintenance log."""
        wo = self.work_orders.pop(work_order_id, None)
        if not wo:
            return False
        # Cascade delete the linked maintenance log
        store = self._get_store()
        if store and getattr(store, "_initialized", False):
            store.maintenance_log_service.delete_log_by_work_order(work_order_id)
        return True


# ==================== MAINTENANCE LOG SERVICE ====================

class MaintenanceLogService:
    """Manages maintenance history records."""

    def __init__(self):
        self.logs: Dict[str, MaintenanceLog] = {}
        self._next_id = 500

    def _generate_id(self) -> str:
        self._next_id += 1
        return f"LOG-{self._next_id:04d}"

    def add_log(
        self,
        machine_id: str,
        technician: str,
        maintenance_type: MaintenanceType,
        issue: str,
        action_taken: str,
        parts_replaced: Optional[List[str]] = None,
        cost: float = 0.0,
        duration_hours: float = 0.0,
        remarks: str = "",
        work_order_id: Optional[str] = None,
        machine_name: str = "",
        category: str = "",
        description: str = "",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        downtime_hours: float = 0.0,
        before_health: float = 0.0,
        after_health: float = 0.0,
        status: str = "Completed"
    ) -> MaintenanceLog:
        """Add a maintenance log entry."""
        if work_order_id:
            for existing in self.logs.values():
                if existing.work_order_id == work_order_id:
                    return existing
        log = MaintenanceLog(
            log_id=self._generate_id(),
            machine_id=machine_id,
            maintenance_date=datetime.now(),
            technician=technician,
            maintenance_type=maintenance_type,
            issue=issue,
            action_taken=action_taken,
            parts_replaced=parts_replaced or [],
            cost=cost,
            duration_hours=duration_hours,
            remarks=remarks,
            work_order_id=work_order_id,
            machine_name=machine_name,
            category=category,
            description=description or action_taken,
            start_time=start_time,
            end_time=end_time,
            downtime_hours=downtime_hours if downtime_hours is not None else duration_hours,
            before_health=before_health,
            after_health=after_health,
            status=status
        )
        self.logs[log.log_id] = log
        return log

    def get_logs_by_machine(self, machine_id: str) -> List[MaintenanceLog]:
        """Get all logs for a machine."""
        return sorted(
            [log for log in self.logs.values() if log.machine_id == machine_id],
            key=lambda x: x.maintenance_date,
            reverse=True
        )

    def get_recent_logs(self, days: int = 30) -> List[MaintenanceLog]:
        """Get logs from recent days."""
        cutoff = datetime.now() - timedelta(days=days)
        return [
            log for log in self.logs.values()
            if log.maintenance_date >= cutoff
        ]

    def get_all_logs(self) -> List[MaintenanceLog]:
        """Get all maintenance logs."""
        return list(self.logs.values())

    def get_total_maintenance_cost(self, machine_id: Optional[str] = None) -> float:
        """Get total maintenance cost."""
        logs = self.get_logs_by_machine(machine_id) if machine_id else self.get_all_logs()
        return sum(log.cost for log in logs)

    def get_log_by_work_order(self, work_order_id: str) -> Optional[MaintenanceLog]:
        """Find a maintenance log by its linked work order ID."""
        for log in self.logs.values():
            if log.work_order_id == work_order_id:
                return log
        return None

    def update_log(self, log_id: str, **kwargs) -> Optional[MaintenanceLog]:
        """Update fields on an existing maintenance log."""
        log = self.logs.get(log_id)
        if not log:
            return None
        for key, value in kwargs.items():
            if hasattr(log, key):
                setattr(log, key, value)
        return log

    def delete_log(self, log_id: str) -> bool:
        """Delete a maintenance log by ID."""
        if log_id in self.logs:
            del self.logs[log_id]
            return True
        return False

    def delete_log_by_work_order(self, work_order_id: str) -> bool:
        """Delete the maintenance log linked to a work order."""
        log = self.get_log_by_work_order(work_order_id)
        if log:
            return self.delete_log(log.log_id)
        return False


# ==================== ALERT SERVICE ====================

class AlertService:
    """Manages alert lifecycle, deduplication, and routing."""

    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self._resolved_alerts: Dict[str, Alert] = {}

    def get_active_alert_by_machine(self, machine_id: str) -> Optional[Alert]:
        """Return the active alert for a machine, if one exists."""
        for alert in self.alerts.values():
            if alert.machine_id == machine_id and alert.status in ("Open", "Acknowledged"):
                return alert
        return None

    def has_active_alert(self, machine_id: str) -> bool:
        """Return True if a machine already has an open or acknowledged alert."""
        return self.get_active_alert_by_machine(machine_id) is not None

    def create_alert(self, machine_id: str, severity: AlertSeverity,
                     reason: str, recommended_action: str) -> Alert:
        """Create a new alert."""
        alert_id = f"ALT-{machine_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        existing = self.get_active_alert_by_machine(machine_id)
        if existing:
            return existing

        alert = Alert(
            alert_id=alert_id,
            machine_id=machine_id,
            severity=severity,
            reason=reason,
            timestamp=datetime.now(),
            recommended_action=recommended_action
        )
        self.alerts[alert.alert_id] = alert
        return alert

    def auto_create_from_machine_status(self, machine: MachineInfo) -> Optional[Alert]:
        """Create one active alert for warning or critical machine states."""
        if machine.status == MachineStatus.NORMAL:
            return None
        if machine.status not in (MachineStatus.WARNING, MachineStatus.CRITICAL):
            return None

        severity = (
            AlertSeverity.CRITICAL
            if machine.status == MachineStatus.CRITICAL
            else AlertSeverity.WARNING
        )
        recommended_action = (
            "Immediate corrective maintenance required"
            if machine.status == MachineStatus.CRITICAL
            else "Schedule preventive maintenance"
        )
        return self.create_alert(
            machine_id=machine.machine_id,
            severity=severity,
            reason=f"{machine.machine_type.value} {machine.status.value.lower()} condition detected",
            recommended_action=recommended_action
        )

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert."""
        alert = self.alerts.get(alert_id)
        if not alert or alert.status != "Open":
            return False
        alert.status = "Acknowledged"
        alert.acknowledged_by = acknowledged_by
        return True

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        alert = self.alerts.get(alert_id)
        if not alert:
            return False
        alert.status = "Resolved"
        alert.resolved_at = datetime.now()
        store_cls = globals().get("EnterpriseDataStore")
        store = getattr(store_cls, "_instance", None) if store_cls else None
        if store and getattr(store, "_initialized", False):
            for wo in store.work_order_service.get_open_work_orders():
                if wo.alert_id == alert.alert_id or (
                    not wo.alert_id and wo.machine_id == alert.machine_id
                ):
                    store.work_order_service.update_status(wo.work_order_id, WorkOrderStatus.COMPLETED)
        return True

    def get_open_alerts(self) -> List[Alert]:
        """Get all open alerts."""
        return [a for a in self.alerts.values() if a.status == "Open"]

    def get_alerts_by_machine(self, machine_id: str) -> List[Alert]:
        """Get all alerts for a machine."""
        return [
            a for a in self.alerts.values()
            if a.machine_id == machine_id
        ]

    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """Get alerts by severity."""
        return [
            a for a in self.alerts.values()
            if a.severity == severity and a.status == "Open"
        ]

    def get_all_alerts(self) -> List[Alert]:
        """Get all alerts."""
        return list(self.alerts.values())

    def get_alert_summary(self) -> Dict[str, int]:
        """Get alert count by severity (only OPEN alerts counted for severity buckets)."""
        summary = {"CRITICAL": 0, "WARNING": 0, "INFO": 0, "Open": 0}
        for a in self.alerts.values():
            if a.status == "Open":
                summary[a.severity.value] = summary.get(a.severity.value, 0) + 1
                summary["Open"] += 1
        return summary

    def get_critical_alerts(self) -> List[Alert]:
        """Get all critical alerts."""
        return self.get_alerts_by_severity(AlertSeverity.CRITICAL)


# ==================== ENTERPRISE DATA STORE ====================

class EnterpriseDataStore:
    """
    Central data store for the enterprise platform.
    Singleton that holds all runtime data.
    Uses in-memory storage (can be backed by DB later).
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.work_order_service = WorkOrderService()
        self.maintenance_log_service = MaintenanceLogService()
        self.alert_service = AlertService()
        
        # Historical sensor data cache
        self.sensor_history: Dict[str, Dict[str, List[Dict]]] = {}
        
        # Prediction cache
        self.prediction_history: Dict[str, List[Dict]] = {}
        
        # Report cache
        self.generated_reports: List[Dict] = []
    
    def reset(self):
        """Reset all data (for testing/restart)."""
        self.__init__()


# Singleton accessor
def get_data_store() -> EnterpriseDataStore:
    """Get the enterprise data store singleton."""
    return EnterpriseDataStore()
