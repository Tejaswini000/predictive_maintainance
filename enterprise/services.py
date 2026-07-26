"""
Enterprise Services for Predictive Maintenance Platform

Manages work orders, maintenance logs, alert lifecycle, and technician assignment.
Reuses existing AI agents for diagnostics and decision-making.
All data is persisted in SQLite via the DatabaseManager.

SINGLE SOURCE OF TRUTH: MachineInfo.status
All alerts, work orders, dashboard counts, and derived data are computed
from the authoritative machine state.

SYNCHRONIZATION RULES:
1. One machine can have at most ONE active alert, ONE active work order, ONE active maintenance log.
2. Alert lifecycle: NORMAL→WARNING (create), WARNING→CRITICAL (upgrade), CRITICAL→NORMAL (close)
3. Work Order lifecycle: Open alert → create WO if none exists. Closed alert → complete linked WO.
4. Maintenance Log lifecycle: Create one log linked to WO. When WO completed → update log.
5. No duplicates anywhere.
6. When work order completed → update last_maintenance_date, close alert, calculate next maintenance.
"""

import uuid
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
for path in (str(PACKAGE_DIR), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from models import (
    MachineInfo, MachineStatus, Alert, AlertSeverity,
    WorkOrder, WorkOrderStatus, MaintenanceLog, MaintenanceType,
    MachineType
)
from database import DatabaseManager
import logging

logger = logging.getLogger(__name__)


# Initialize the database manager as a singleton
_db_manager = None

def get_db() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


# ==================== ENTERPRISE DATA STORE (forward declaration) ====================
# We need a reliable way to get the store singleton without circular imports
_data_store_instance = None

def set_data_store(store):
    """Set the EnterpriseDataStore singleton (called by EnterpriseDataStore.__init__)."""
    global _data_store_instance
    _data_store_instance = store

def get_data_store():
    """Get the EnterpriseDataStore singleton reliably."""
    global _data_store_instance
    if _data_store_instance is None:
        # Lazy initialization
        from services import EnterpriseDataStore
        _data_store_instance = EnterpriseDataStore()
    return _data_store_instance


# ==================== WORK ORDER SERVICE ====================

class WorkOrderService:
    """Manages the complete work order lifecycle. Persisted via SQLite."""

    def __init__(self):
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
        """Get the EnterpriseDataStore singleton reliably."""
        return get_data_store()

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
        """Create a new work order from AI-detected issues.
        
        Only ONE active work order per machine is allowed.
        If an active work order already exists, returns the existing one.
        """
        db = get_db()

        # Check for existing active work orders from DB
        if db.has_active_work_order(machine_id):
            existing_wos = db.get_work_orders_by_machine(machine_id)
            for existing in existing_wos:
                if existing.status in (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS):
                    if alert_id and not existing.alert_id:
                        existing.alert_id = alert_id
                        db.update_work_order(existing)
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

        db.insert_work_order(wo)

        # Auto-create a Scheduled Preventive Maintenance Log linked to this work order
        self._create_scheduled_maintenance_log(wo)

        return wo

    def _get_realistic_maintenance_date(self, machine: Optional[MachineInfo] = None) -> datetime:
        """Return a realistic maintenance timestamp with unique hour/minute/second per machine."""
        # Use a unique random offset based on machine_id to prevent clustering
        if machine and machine.last_maintenance_date:
            # Spread across 30-180 days with random hours/minutes
            days_offset = random.randint(30, 180)
            hours_offset = random.randint(0, 23)
            minutes_offset = random.randint(0, 59)
            seconds_offset = random.randint(0, 59)
            return min(
                datetime.now(),
                machine.last_maintenance_date + timedelta(
                    days=days_offset,
                    hours=hours_offset,
                    minutes=minutes_offset,
                    seconds=seconds_offset
                )
            )
        # Random historical date spread across 45-180 days with unique time
        return datetime.now() - timedelta(
            days=random.randint(45, 180),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )

    def _get_maintenance_type_for_work_order(self, wo: WorkOrder, machine: Optional[MachineInfo] = None) -> MaintenanceType:
        """Use different maintenance types so the history looks less repetitive."""
        if wo.priority == "High" or (machine and machine.status == MachineStatus.CRITICAL):
            return random.choice([MaintenanceType.CORRECTIVE, MaintenanceType.REPLACEMENT, MaintenanceType.EMERGENCY])
        if random.random() < 0.3:
            return random.choice([MaintenanceType.PREVENTIVE, MaintenanceType.INSPECTION])
        return MaintenanceType.PREVENTIVE

    def _create_scheduled_maintenance_log(self, wo: WorkOrder):
        """Create a Scheduled Maintenance Log when a work order is created.
        Only ONE maintenance log per work order is allowed.
        Also ensures only ONE active maintenance log per machine.
        """
        store = self._get_store()
        if not store or not getattr(store, "_initialized", False):
            return

        # Check if a maintenance log already exists for this work order
        logger.debug("_create_scheduled_maintenance_log checking existing logs for wo=%s machine=%s", wo.work_order_id, wo.machine_id)
        existing_log = store.maintenance_log_service.get_log_by_work_order(wo.work_order_id)
        logger.debug("existing_log=%r", existing_log)
        if existing_log:
            # If an existing log references a different machine, ignore the orphaned mapping
            if existing_log.machine_id == wo.machine_id:
                return  # Already exists for this work order and machine, do not create duplicate
            logger.debug("existing_log for different machine (orphaned) machine=%s wo=%s", existing_log.machine_id, wo.work_order_id)

        # Check if there's already an active (Scheduled/In Progress) maintenance log for this machine
        logs = store.maintenance_log_service.get_logs_by_machine(wo.machine_id)
        for log in logs:
            if log.status in ("Scheduled", "In Progress") and log.work_order_id:
                # Link this work order to the existing log instead of creating a new one
                if log.work_order_id != wo.work_order_id:
                    existing_wo = get_db().get_work_order(log.work_order_id)
                    if existing_wo and existing_wo.status in (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS):
                        # There's already an active maintenance log for another active work order
                        # Don't create another one for this machine
                        logger.debug("_create_scheduled_maintenance_log found active log %s status=%s", log.log_id, log.status)
                        return
            elif log.status in ("Scheduled", "In Progress") and not log.work_order_id:
                # An orphaned active log exists - don't create another
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
        maintenance_type = self._get_maintenance_type_for_work_order(wo, machine)
        maintenance_date = self._get_realistic_maintenance_date(machine)

        store.maintenance_log_service.add_log(
            machine_id=wo.machine_id,
            technician=wo.assigned_technician,
            maintenance_type=maintenance_type,
            issue=wo.issue_description or wo.title,
            action_taken=self._get_realistic_maintenance_action(wo, machine),
            cost=0.0,
            duration_hours=2.0,
            remarks="",
            work_order_id=wo.work_order_id,
            machine_name=machine_name,
            category=category,
            description=(
                f"{maintenance_type.value} maintenance scheduled automatically after AI prediction.\nIssue: {wo.issue_description or ''}"
            ),
            start_time=maintenance_date,
            end_time=None,
            downtime_hours=0.0,
            before_health=before_health,
            after_health=0.0,
            status="Scheduled",
            maintenance_date=maintenance_date
        )
        logger.debug("_create_scheduled_maintenance_log created log for %s machine=%s date=%s", wo.work_order_id, wo.machine_id, maintenance_date)

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
        db = get_db()
        wo = db.get_work_order(work_order_id)
        if not wo:
            return False
        wo.status = new_status
        if new_status == WorkOrderStatus.COMPLETED:
            wo.completed_date = datetime.now()
            self._complete_maintenance_log_from_work_order(wo)
        db.update_work_order(wo)
        return True

    def assign_technician(self, work_order_id: str, technician: str) -> bool:
        """Assign/reassign technician."""
        db = get_db()
        wo = db.get_work_order(work_order_id)
        if not wo:
            return False
        wo.assigned_technician = technician
        db.update_work_order(wo)
        return True

    def update_progress(self, work_order_id: str, actual_hours: float,
                        parts_replaced: List[str], cost: float, remarks: str) -> bool:
        """Update work order progress."""
        db = get_db()
        wo = db.get_work_order(work_order_id)
        if not wo:
            return False
        wo.actual_hours = actual_hours
        wo.parts_replaced = parts_replaced
        wo.cost = cost
        wo.remarks = remarks
        db.update_work_order(wo)
        return True

    def get_work_orders_by_machine(self, machine_id: str, include_completed: bool = False) -> List[WorkOrder]:
        """Get active work orders for a machine by default, with optional history access."""
        db = get_db()
        work_orders = db.get_work_orders_by_machine(machine_id)
        if include_completed:
            return work_orders
        return [wo for wo in work_orders if wo.status in (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)]

    def get_work_orders_by_status(self, status: WorkOrderStatus) -> List[WorkOrder]:
        """Get work orders by status."""
        db = get_db()
        return db.get_work_orders_by_status(status.value if hasattr(status, 'value') else status)

    def get_all_work_orders(self) -> List[WorkOrder]:
        """Get all work orders."""
        db = get_db()
        return db.get_all_work_orders()

    def get_open_work_orders(self) -> List[WorkOrder]:
        """Get open and in-progress work orders."""
        db = get_db()
        return db.get_open_work_orders()

    def has_active_work_order(self, machine_id: str) -> bool:
        """Return True if a machine already has an open or in-progress work order."""
        db = get_db()
        return db.has_active_work_order(machine_id)

    def get_work_order_summary(self) -> Dict[str, int]:
        """Get summary of work orders by status."""
        db = get_db()
        return db.get_work_order_summary()

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
        """Create one active work order for warning or critical machine states.
        
        Only ONE active work order per machine is ever created.
        If an active work order already exists, returns the existing one.
        """
        if machine.status == MachineStatus.NORMAL:
            return None
        if machine.status not in (MachineStatus.WARNING, MachineStatus.CRITICAL):
            return None

        # Check if an active work order already exists
        if self.has_active_work_order(machine.machine_id):
            existing_wos = self.get_work_orders_by_machine(machine.machine_id)
            for existing in existing_wos:
                if existing.status in (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS):
                    existing.current_health_score = machine.health_score
                    existing.current_status = machine.status.value
                    existing.issue_description = machine.cause or existing.issue_description
                    existing.ai_recommendation = self._build_recommendation_from_cause(machine)
                    # Link alert_id if not already set
                    if alert and not existing.alert_id:
                        existing.alert_id = alert.alert_id
                    db = get_db()
                    db.update_work_order(existing)
                    return existing

        is_critical = machine.status == MachineStatus.CRITICAL
        maintenance_type = MaintenanceType.CORRECTIVE if is_critical else MaintenanceType.PREVENTIVE
        priority = "High" if is_critical else "Medium"
        due_date = date.today() if is_critical else date.today() + timedelta(days=1)
        # Debugging: ensure we capture what cause is present on the machine
        logger.debug("auto_create_from_machine_status - machine=%s cause=%r recent=%s", machine.machine_id, machine.cause, getattr(machine, 'recent_failure_causes', []))
        cause = machine.cause or "Performance drift"
        # Prefer explicit or recent causes over the generic default so work orders
        # and maintenance activities reflect meaningful root causes.
        if not cause or not cause.strip() or cause.lower().startswith("sensor readings"):
            recent = list(getattr(machine, "recent_failure_causes", []))
            if recent:
                cause = recent[-1]
        issue_description = f"{machine.name} is in {machine.condition or machine.status.value.title()} condition with {machine.health_score:.1f}% health. Detected cause: {cause}."
        ai_recommendation = self._build_recommendation_from_cause(machine)
        title = self._build_work_order_title(machine, cause)
        description = self._build_work_order_description(machine, cause, ai_recommendation, priority)

        wo = self.create_work_order(
            machine_id=machine.machine_id,
            title=title,
            description=description,
            priority=priority,
            scheduled_date=due_date,
            estimated_hours=self._estimate_hours(priority),
            alert_id=alert.alert_id if alert else None
        )
        wo.due_date = due_date
        wo.machine_name = machine.name
        wo.category = machine.machine_category
        wo.current_health_score = machine.health_score
        wo.current_status = machine.condition or machine.status.value.title()
        wo.maintenance_type = maintenance_type.value
        wo.issue_description = issue_description
        wo.ai_recommendation = ai_recommendation
        db = get_db()
        db.update_work_order(wo)
        return wo

    def _build_recommendation_from_cause(self, machine: MachineInfo) -> str:
        cause = (machine.cause or "Performance drift").lower()
        if "bearing" in cause or "drum" in cause:
            return "Inspect and replace worn bearings or rebalance the drum assembly."
        if "refrigerant" in cause or "cooling" in cause or "condenser" in cause or "evaporator" in cause:
            return "Inspect the refrigeration circuit, recharge refrigerant if needed, and clean the condenser."
        if "alternator" in cause or "voltage" in cause or "electrical" in cause:
            return "Inspect electrical insulation, cooling paths, and replace failing components as needed."
        if "oil" in cause or "coolant" in cause or "timing" in cause or "spark" in cause:
            return "Perform engine diagnostics, replace worn consumables, and verify lubrication or cooling integrity."
        if "pump" in cause or "motor" in cause or "fan" in cause:
            return "Inspect the pump or motor assembly and replace degraded components."
        return "Schedule targeted inspection and corrective maintenance based on the detected fault."

    def _build_work_order_title(self, machine: MachineInfo, cause: str) -> str:
        title_map = {
            "bearing": "Bearing Replacement",
            "drum": "Drum Inspection",
            "refrigerant": "Refrigerant Leak Inspection",
            "cooling": "Cooling System Inspection",
            "alternator": "Alternator Cooling Inspection",
            "voltage": "Electrical System Inspection",
            "oil": "Oil System Diagnostics",
            "coolant": "Cooling System Diagnostics",
            "timing": "Timing Belt Inspection",
            "spark": "Ignition Component Inspection",
            "pump": "Pump Replacement",
            "motor": "Motor Inspection",
            "fan": "Fan Motor Replacement",
        }
        lower_cause = cause.lower()
        for token, title in title_map.items():
            if token in lower_cause:
                return f"{title}: {machine.name}"
        return f"Maintenance Required: {machine.name}"

    def _build_work_order_description(self, machine: MachineInfo, cause: str, recommendation: str, priority: str) -> str:
        return (
            f"Machine ID: {machine.machine_id}\n"
            f"Machine Name: {machine.name}\n"
            f"Category: {machine.machine_category}\n"
            f"Current Health Score: {machine.health_score:.1f}%\n"
            f"Current Status: {machine.condition or machine.status.value.title()}\n"
            f"Priority: {priority}\n"
            f"Detected Cause: {cause}\n"
            f"AI Recommendation: {recommendation}"
        )

    # Parts lookup by machine category
    _PARTS_BY_CATEGORY = {
        "Refrigerator": ["Compressor", "Thermostat", "Condenser Fan", "Door Gasket"],
        "Washing Machine": ["Water Pump", "Drive Belt", "Drum Bearing", "Motor"],
        "Air Conditioner": ["Air Filter", "Condenser Coil", "Cooling Fan", "Compressor"],
        "Generator": ["Oil Filter", "Spark Plug", "Battery", "Fuel Filter"],
        "Car Engine": ["Engine Oil", "Air Filter", "Timing Belt", "Coolant Pump"],
    }

    # Technician remarks pool
    _TECHNICIAN_REMARKS = [
        "Preventive maintenance completed successfully.",
        "Replaced worn components and verified normal operation.",
        "Machine tested after maintenance. Performance restored.",
        "No abnormal vibration detected after servicing.",
        "Routine preventive maintenance completed.",
    ]

    def _get_parts_for_category(self, category: str) -> list:
        """Get realistic parts for a machine category. Returns 1-3 random parts."""
        parts = self._PARTS_BY_CATEGORY.get(category, ["General Component"])
        count = random.randint(1, min(3, len(parts)))
        return random.sample(parts, count)

    def _get_realistic_maintenance_action(self, wo: WorkOrder, machine: Optional[MachineInfo] = None) -> str:
        cause = (wo.issue_description or wo.description or "").lower()
        if "bearing" in cause or "drum" in cause:
            return "Bearing replacement and drum balancing"
        if "refrigerant" in cause or "cooling" in cause or "condenser" in cause or "evaporator" in cause:
            return "Refrigerant recharge and condenser cleaning"
        if "alternator" in cause or "voltage" in cause or "electrical" in cause:
            return "Electrical wiring repair and component testing"
        if "oil" in cause or "coolant" in cause or "timing" in cause or "spark" in cause:
            return "Lubrication completed and ignition system serviced"
        if "pump" in cause or "motor" in cause or "fan" in cause:
            return "Motor inspection and pump replacement"
        return "System inspection and preventive maintenance"

    def _get_technician_remark(self) -> str:
        """Get a random technician remark."""
        return random.choice(self._TECHNICIAN_REMARKS)

    def _complete_maintenance_log_from_work_order(self, wo: WorkOrder):
        """Update the existing scheduled maintenance log when a work order is completed.
        
        This is the CENTRAL method for completing maintenance. It:
        1. Updates the maintenance log with completion data
        2. Updates the machine's last_maintenance_date
        3. Calculates next_maintenance_date
        4. Closes the related alert
        5. Updates the work order with actual values
        """
        store = self._get_store()
        if not store or not getattr(store, "_initialized", False):
            return

        # Find the existing maintenance log linked to this work order
        existing_log = store.maintenance_log_service.get_log_by_work_order(wo.work_order_id)
        if not existing_log:
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

        # Generate parts replaced based on machine category
        category = wo.category or (machine.machine_category if machine else "")

        # Generate realistic maintenance values with unique timestamps
        from simulation import _get_realistic_maintenance_cost
        cause_text = wo.issue_description or wo.title or "General maintenance"
        maintenance_cost = _get_realistic_maintenance_cost(cause_text, category)
        actual_duration = round(random.uniform(1, 4), 1)
        downtime = round(random.uniform(0.5, 2), 1)
        
        # Use a unique completion time per work order to prevent clustering
        completion_time = existing_log.maintenance_date or datetime.now()
        if completion_time > datetime.now():
            completion_time = datetime.now()
        # Add random microsecond offset so even same-second completions are unique
        completion_time = completion_time.replace(microsecond=random.randint(0, 999999))

        # Generate parts replaced based on machine category
        parts_replaced = self._get_parts_for_category(category)

        # Generate technician remarks
        remarks = self._get_technician_remark()
        action_taken = self._get_realistic_maintenance_action(wo, machine)

        # Health After: improve by random 8-20%, never exceed 100%
        health_improvement = random.uniform(8, 20)
        after_health = min(100.0, round(before_health + health_improvement, 1))

        if machine:
            machine.health_score = after_health
            machine.failure_probability = round(max(0.01, (100 - machine.health_score) / 100 * 0.45), 3)
            if machine.health_score >= 85:
                machine.status = MachineStatus.NORMAL
            
            # CRITICAL: Update last_maintenance_date on the machine
            machine.last_maintenance_date = completion_time
            
            # Calculate next maintenance date (30-90 days from now with unique random time)
            next_maint_days = random.randint(30, 90)
            next_maint_hours = random.randint(0, 23)
            next_maint_minutes = random.randint(0, 59)
            machine.next_maintenance_date = completion_time + timedelta(
                days=next_maint_days,
                hours=next_maint_hours,
                minutes=next_maint_minutes
            )

        maintenance_type = MaintenanceType.CORRECTIVE if wo.priority == "High" else MaintenanceType.PREVENTIVE
        if wo.maintenance_type:
            try:
                maintenance_type = MaintenanceType(wo.maintenance_type)
            except ValueError:
                maintenance_type = MaintenanceType.CORRECTIVE if wo.priority == "High" else MaintenanceType.PREVENTIVE

        end_time = completion_time
        start_time = existing_log.start_time or (end_time - timedelta(hours=actual_duration))

        # Update the existing log with completion data
        store.maintenance_log_service.update_log(
            existing_log.log_id,
            status="Completed",
            maintenance_type=maintenance_type,
            action_taken=action_taken,
            parts_replaced=parts_replaced,
            cost=maintenance_cost,
            duration_hours=actual_duration,
            remarks=remarks,
            description=wo.description,
            start_time=start_time,
            end_time=end_time,
            downtime_hours=downtime,
            after_health=after_health,
            maintenance_date=completion_time
        )

        # Update the work order with generated values
        wo.actual_hours = actual_duration
        wo.parts_replaced = parts_replaced
        wo.cost = maintenance_cost
        wo.remarks = remarks
        db = get_db()
        db.update_work_order(wo)

        # Close the related alert (Alert Status: Open → Closed)
        if wo.alert_id:
            alert = db.get_alert(wo.alert_id)
            if alert and alert.status == "Open":
                alert.status = "Closed"
                alert.resolved_at = completion_time
                db.update_alert(alert)
        else:
            # Try to find alert by machine_id
            alert = store.alert_service.get_active_alert_by_machine(wo.machine_id)
            if alert and alert.status == "Open":
                alert.status = "Closed"
                alert.resolved_at = completion_time
                db.update_alert(alert)
                wo.alert_id = alert.alert_id
                db.update_work_order(wo)

        # CRITICAL: Persist machine changes (last_maintenance_date, next_maintenance_date, health, status)
        if machine:
            db.update_machine(machine)

    def delete_work_order(self, work_order_id: str) -> bool:
        """Delete a work order and its linked maintenance log."""
        db = get_db()
        result = db.delete_work_order(work_order_id)
        if result:
            db.delete_maintenance_log_by_work_order(work_order_id)
        return result

    def deduplicate_work_orders(self, machine_id: str) -> int:
        """
        Remove duplicate active work orders for a machine.
        Keeps only the most recent active work order, closes the rest.
        Returns the number of duplicates removed.
        """
        db = get_db()
        wos = db.get_work_orders_by_machine(machine_id)
        active_wos = [wo for wo in wos if wo.status in (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)]
        
        if len(active_wos) <= 1:
            return 0
        
        # Sort by created_date descending, keep the most recent
        active_wos.sort(key=lambda wo: wo.created_date, reverse=True)
        keep = active_wos[0]
        removed = 0
        
        for wo in active_wos[1:]:
            if wo.work_order_id != keep.work_order_id:
                wo.status = WorkOrderStatus.CANCELLED
                db.update_work_order(wo)
                removed += 1
        
        return removed


# ==================== MAINTENANCE LOG SERVICE ====================

class MaintenanceLogService:
    """Manages maintenance history records. Persisted via SQLite."""

    def __init__(self):
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
        status: str = "Completed",
        maintenance_date: Optional[datetime] = None
    ) -> MaintenanceLog:
        """Add a maintenance log entry.
        
        Only ONE maintenance log per work_order_id is allowed.
        If a log already exists for this work order, returns the existing one.
        """
        logger.debug("MaintenanceLogService.add_log called for machine=%s work_order=%s", machine_id, work_order_id)
        db = get_db()

        # Check for duplicate work_order_id
        if work_order_id:
            existing = db.get_maintenance_log_by_work_order(work_order_id)
            if existing:
                # If the existing log belongs to the same machine, return it to avoid duplicates.
                # If it references a different machine (an orphaned mapping), ignore it and
                # allow creation of a new log for this machine. Orphaned mappings are cleaned
                # up by deduplication routines elsewhere.
                if existing.machine_id == machine_id:
                    return existing
                else:
                        logger.debug("add_log found orphaned maintenance log %s for work_order=%s machine=%s; creating new log for machine=%s", existing.log_id, work_order_id, existing.machine_id, machine_id)

        # Prevent duplicate active (Scheduled/In Progress) logs per machine
        existing_logs = db.get_maintenance_logs_by_machine(machine_id)
        for existing_log in existing_logs:
            if existing_log.status in ("Scheduled", "In Progress"):
                return existing_log

        # Ensure unique timestamp to prevent clustering
        if maintenance_date is None:
            maintenance_date = datetime.now()
        # Add random microsecond offset for uniqueness
        if maintenance_date.microsecond < 100000:
            maintenance_date = maintenance_date.replace(microsecond=random.randint(0, 999999))

        log = MaintenanceLog(
            log_id=self._generate_id(),
            machine_id=machine_id,
            maintenance_date=maintenance_date,
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
            # Prefer an explicit description, fall back to the issue text (cause) so that
            # maintenance logs contain human-readable information about the root cause.
            description=description or issue or action_taken,
            start_time=start_time,
            end_time=end_time,
            downtime_hours=downtime_hours if downtime_hours is not None else duration_hours,
            before_health=before_health,
            after_health=after_health,
            status=status
        )
        db.insert_maintenance_log(log)
        return log

    def get_logs_by_machine(self, machine_id: str) -> List[MaintenanceLog]:
        """Get all logs for a machine."""
        db = get_db()
        logs = db.get_maintenance_logs_by_machine(machine_id)
        logger.debug("get_logs_by_machine machine=%s count=%d", machine_id, len(logs))
        return logs

    def get_recent_logs(self, days: int = 30) -> List[MaintenanceLog]:
        """Get logs from recent days."""
        db = get_db()
        return db.get_recent_maintenance_logs(days)

    def get_all_logs(self) -> List[MaintenanceLog]:
        """Get all maintenance logs."""
        db = get_db()
        return db.get_all_maintenance_logs()

    def seed_historical_logs(self, machine: MachineInfo) -> List[MaintenanceLog]:
        """Populate a realistic maintenance history for a machine based on its purchase date."""
        db = get_db()
        existing_logs = db.get_maintenance_logs_by_machine(machine.machine_id)
        if existing_logs:
            return existing_logs

        if not machine.purchase_date:
            machine.purchase_date = datetime.now() - timedelta(days=365)

        start_date = machine.purchase_date
        years_since_purchase = max(1, (datetime.now() - start_date).days // 365)
        log_count = min(6, 2 + years_since_purchase)
        logs = []
        for idx in range(log_count):
            # Each log gets a unique timestamp spread across the lifecycle
            offset_days = 180 * (idx + 1) + random.randint(0, 60)
            offset_hours = random.randint(0, 12 * (idx + 1))
            offset_minutes = random.randint(0, 59)
            maintenance_date = start_date + timedelta(
                days=offset_days,
                hours=offset_hours,
                minutes=offset_minutes
            )
            if maintenance_date > datetime.now():
                maintenance_date = datetime.now() - timedelta(
                    days=random.randint(30, 180),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
            maintenance_type = random.choice([MaintenanceType.INSPECTION, MaintenanceType.PREVENTIVE, MaintenanceType.CORRECTIVE, MaintenanceType.REPLACEMENT])
            issue = self._issue_for_machine(machine, idx)
            action = self._action_for_machine(machine, issue)
            log = MaintenanceLog(
                log_id=self._generate_id(),
                machine_id=machine.machine_id,
                maintenance_date=maintenance_date,
                technician=random.choice(["Rajesh Kumar", "Priya Sharma", "Amit Singh", "Sneha Patel"]),
                maintenance_type=maintenance_type,
                issue=issue,
                action_taken=action,
                parts_replaced=self._parts_for_issue(issue, machine.machine_category),
                cost=round(random.uniform(300, 3000), 2),
                duration_hours=round(random.uniform(1, 4), 1),
                remarks="",
                machine_name=machine.name,
                category=machine.machine_category,
                description=action,
                status="Completed",
                created_date=maintenance_date,
            )
            db.insert_maintenance_log(log)
            logs.append(log)
        return logs

    def _issue_for_machine(self, machine: MachineInfo, index: int) -> str:
        issues = {
            MachineType.WASHING_MACHINE: ["High drum vibration", "Bearing wear", "Water pump degradation", "Motor current exceeded threshold"],
            MachineType.REFRIGERATOR: ["Compressor overheating", "Door seal leakage", "Cooling efficiency reduced", "Evaporator icing"],
            MachineType.AIR_CONDITIONER: ["Condenser overheating", "Low refrigerant pressure", "Compressor overload", "Fan motor failure"],
            MachineType.GENERATOR: ["Alternator overheating", "Fuel pressure fluctuation", "Voltage instability", "Engine vibration increased"],
            MachineType.CAR_ENGINE: ["Low oil pressure", "Coolant overheating", "Spark plug degradation", "Timing belt wear"],
        }
        candidates = issues.get(machine.machine_type, ["Performance drift"])
        return candidates[index % len(candidates)]

    def _action_for_machine(self, machine: MachineInfo, issue: str) -> str:
        lower_issue = issue.lower()
        if "bearing" in lower_issue or "drum" in lower_issue:
            return "Drum bearings replaced and alignment recalibrated"
        if "refrigerant" in lower_issue or "cooling" in lower_issue or "condenser" in lower_issue or "evaporator" in lower_issue:
            return "Refrigerant recharged and condenser cleaned"
        if "alternator" in lower_issue or "voltage" in lower_issue:
            return "Electrical wiring repaired and alternator tested"
        if "oil" in lower_issue or "coolant" in lower_issue or "timing" in lower_issue or "spark" in lower_issue:
            return "Lubrication completed and ignition or cooling components serviced"
        if "pump" in lower_issue or "motor" in lower_issue or "fan" in lower_issue:
            return "Motor serviced and pump or fan replaced"
        return "Preventive maintenance completed"

    def _parts_for_issue(self, issue: str, category: str) -> List[str]:
        lower_issue = issue.lower()
        if "bearing" in lower_issue:
            return ["Bearing Kit"]
        if "refrigerant" in lower_issue or "cooling" in lower_issue or "condenser" in lower_issue or "evaporator" in lower_issue:
            return ["Condenser Coil", "Filter"]
        if "alternator" in lower_issue or "voltage" in lower_issue:
            return ["Voltage Regulator"]
        if "oil" in lower_issue or "coolant" in lower_issue or "timing" in lower_issue or "spark" in lower_issue:
            return ["Gasket", "Sensor"]
        if "pump" in lower_issue or "motor" in lower_issue or "fan" in lower_issue:
            return ["Motor", "Pump"]
        return ["General Component"]

    def get_total_maintenance_cost(self, machine_id: Optional[str] = None) -> float:
        """Get total maintenance cost."""
        logs = self.get_logs_by_machine(machine_id) if machine_id else self.get_all_logs()
        return sum(log.cost for log in logs)

    def get_log_by_work_order(self, work_order_id: str) -> Optional[MaintenanceLog]:
        """Find a maintenance log by its linked work order ID."""
        db = get_db()
        return db.get_maintenance_log_by_work_order(work_order_id)

    def update_log(self, log_id: str, **kwargs) -> Optional[MaintenanceLog]:
        """Update fields on an existing maintenance log."""
        db = get_db()

        # Convert enum values and special types for DB storage
        db_kwargs = {}
        for key, value in kwargs.items():
            if key == "maintenance_type":
                if hasattr(value, 'value'):
                    db_kwargs[key] = value.value
                else:
                    db_kwargs[key] = value
            elif key == "maintenance_date":
                from database import _serialize_datetime
                db_kwargs[key] = _serialize_datetime(value)
            elif key == "start_time":
                from database import _serialize_datetime
                db_kwargs[key] = _serialize_datetime(value)
            elif key == "end_time":
                from database import _serialize_datetime
                db_kwargs[key] = _serialize_datetime(value)
            elif key == "parts_replaced" and isinstance(value, list):
                import json
                db_kwargs[key] = json.dumps(value)
            else:
                db_kwargs[key] = value

        if db_kwargs:
            db.update_maintenance_log(log_id, **db_kwargs)

        return db.get_maintenance_log(log_id)

    def delete_log(self, log_id: str) -> bool:
        """Delete a maintenance log by ID."""
        db = get_db()
        return db.delete_maintenance_log(log_id)

    def delete_log_by_work_order(self, work_order_id: str) -> bool:
        """Delete the maintenance log linked to a work order."""
        db = get_db()
        return db.delete_maintenance_log_by_work_order(work_order_id)

    def deduplicate_maintenance_logs(self, machine_id: str) -> int:
        """
        Remove duplicate active maintenance logs for a machine.
        Keeps only the most recent active log, deletes the rest.
        Returns the number of duplicates removed.
        """
        db = get_db()
        logs = db.get_maintenance_logs_by_machine(machine_id)
        active_logs = [log for log in logs if log.status in ("Scheduled", "In Progress")]
        
        if len(active_logs) <= 1:
            return 0
        
        # Sort by created_date descending, keep the most recent
        active_logs.sort(key=lambda log: log.created_date, reverse=True)
        keep = active_logs[0]
        removed = 0
        
        for log in active_logs[1:]:
            if log.log_id != keep.log_id:
                db.delete_maintenance_log(log.log_id)
                removed += 1
        
        return removed


# ==================== ALERT SERVICE ====================

class AlertService:
    """
    Manages alert lifecycle with automatic synchronization to machine status.
    
    SINGLE SOURCE OF TRUTH: machine.status
    Alerts are DERIVED from machine.status, never the other way around.
    
    Synchronization Rules:
    - NORMAL   → Close all open WARNING and CRITICAL alerts. Machine must have zero active alerts.
    - WARNING  → Ensure exactly one active WARNING alert exists. No duplicates.
    - CRITICAL → Ensure exactly one active CRITICAL alert exists. Upgrade WARNING to CRITICAL if present.
    
    Alert Lifecycle:
    NORMAL → WARNING:     Create one WARNING alert.
    WARNING → WARNING:    Update timestamp/details. Do NOT create another alert.
    WARNING → CRITICAL:   Upgrade the existing alert to CRITICAL. Do NOT create a new alert.
    CRITICAL → CRITICAL:  Update the existing alert only.
    WARNING/CRITICAL → NORMAL: Close the existing alert. Do not leave an OPEN alert.
    """

    def __init__(self):
        pass  # All storage now in SQLite

    def get_active_alert_by_machine(self, machine_id: str) -> Optional[Alert]:
        """Return the active (OPEN only) alert for a machine, if one exists."""
        db = get_db()
        return db.get_active_alert_by_machine(machine_id)

    def has_active_alert(self, machine_id: str) -> bool:
        """Return True if a machine already has an OPEN alert."""
        return self.get_active_alert_by_machine(machine_id) is not None

    def _get_alert_timestamp(self, machine: MachineInfo) -> datetime:
        """Create a realistic alert timestamp based on machine activity history."""
        now = datetime.now()
        if machine.last_maintenance_date:
            days_since_maintenance = max(7, min(365, (now - machine.last_maintenance_date).days))
            return now - timedelta(days=days_since_maintenance + (7 if machine.status == MachineStatus.WARNING else 0))
        if machine.operating_hours:
            return now - timedelta(days=int(min(180, max(7, machine.operating_hours / 8))))
        return now

    def create_alert(self, machine_id: str, severity: AlertSeverity,
                     reason: str, recommended_action: str, timestamp: Optional[datetime] = None) -> Alert:
        """Create a new alert.
        
        If an active alert already exists for this machine, returns the existing one.
        This ensures MAXIMUM ONE active alert per machine.
        """
        alert_id = f"ALT-{machine_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        existing = self.get_active_alert_by_machine(machine_id)
        if existing:
            return existing

        alert = Alert(
            alert_id=alert_id,
            machine_id=machine_id,
            severity=severity,
            reason=reason,
            timestamp=timestamp or datetime.now(),
            recommended_action=recommended_action
        )
        db = get_db()
        db.insert_alert(alert)
        return alert

    def close_alert(self, alert: Alert) -> bool:
        """Close an alert (set status to Closed with timestamp).
        
        If already closed, still returns True (idempotent).
        """
        db = get_db()
        if alert.status == "Closed":
            return True  # Already closed, idempotent
        alert.status = "Closed"
        alert.resolved_at = datetime.now()
        db.update_alert(alert)
        return True

    def close_all_open_alerts_by_machine(self, machine_id: str) -> int:
        """Close all OPEN alerts for a machine. Returns count of alerts closed."""
        db = get_db()
        count = 0
        all_alerts = db.get_alerts_by_machine(machine_id)
        for alert in all_alerts:
            if alert.status == "Open":
                alert.status = "Closed"
                alert.resolved_at = datetime.now()
                db.update_alert(alert)
                count += 1
        return count

    def auto_create_from_machine_status(self, machine: MachineInfo) -> Optional[Alert]:
        """
        Synchronize alerts to match machine status (single source of truth).
        
        This is the CENTRAL method for alert lifecycle management.
        All alert creation, upgrade, and closure flows through this method.
        
        NORMAL → WARNING:     Create one WARNING alert.
        WARNING → WARNING:    Update existing alert. Do NOT create another.
        WARNING → CRITICAL:   Upgrade existing alert to CRITICAL. Do NOT create new.
        CRITICAL → CRITICAL:  Update existing alert only.
        WARNING/CRITICAL → NORMAL: Close existing alert.
        """
        db = get_db()
        machine_type_name = machine.machine_type.value if hasattr(machine.machine_type, 'value') else str(machine.machine_type)
        
        if machine.status == MachineStatus.NORMAL:
            # Close ALL open alerts for this machine
            self.close_all_open_alerts_by_machine(machine.machine_id)
            return None

        if machine.status not in (MachineStatus.WARNING, MachineStatus.CRITICAL):
            return None

        expected_severity = (
            AlertSeverity.CRITICAL if machine.status == MachineStatus.CRITICAL
            else AlertSeverity.WARNING
        )
        recommended_action = (
            "Immediate corrective maintenance required"
            if machine.status == MachineStatus.CRITICAL
            else "Schedule preventive maintenance"
        )
        if machine.cause:
            reason = machine.cause if machine.cause.endswith('.') else f"{machine.cause} detected"
        else:
            reason = (
                f"{machine_type_name} critical fault detected"
                if machine.status == MachineStatus.CRITICAL
                else f"{machine_type_name} performance drift detected"
            )
        if machine.machine_id:
            reason = f"{reason} on {machine.machine_id}"

        # Check existing open alerts for this machine
        existing = self.get_active_alert_by_machine(machine.machine_id)
        if existing:
            if machine.status == MachineStatus.CRITICAL and existing.severity == AlertSeverity.WARNING:
                # Upgrade WARNING to CRITICAL
                existing.severity = AlertSeverity.CRITICAL
                existing.reason = reason
                existing.recommended_action = recommended_action
                existing.timestamp = datetime.now()
                db.update_alert(existing)
            elif machine.status == MachineStatus.WARNING and existing.severity == AlertSeverity.CRITICAL:
                # Downgrade CRITICAL to WARNING (if machine went from CRITICAL to WARNING)
                existing.severity = AlertSeverity.WARNING
                existing.reason = reason
                existing.recommended_action = recommended_action
                existing.timestamp = datetime.now()
                db.update_alert(existing)
            elif existing.severity != expected_severity:
                # Update severity/reason if different
                existing.severity = expected_severity
                existing.reason = reason
                existing.recommended_action = recommended_action
                existing.timestamp = datetime.now()
                db.update_alert(existing)
            else:
                # Same severity - just update timestamp and details
                existing.reason = reason
                existing.recommended_action = recommended_action
                existing.timestamp = datetime.now()
                db.update_alert(existing)
            return existing

        # Active alerts must use the current simulation timestamp, not historical dates.
        # Historical alerts belong in Alert History, not as active alerts.
        return self.create_alert(
            machine_id=machine.machine_id,
            severity=expected_severity,
            reason=reason,
            recommended_action=recommended_action,
            timestamp=datetime.now()
        )

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert. (Marks it as Acknowledged but it remains active.)"""
        db = get_db()
        alert = db.get_alert(alert_id)
        if not alert or alert.status != "Open":
            return False
        alert.status = "Acknowledged"
        alert.acknowledged_by = acknowledged_by
        db.update_alert(alert)
        return True

    def resolve_alert(self, alert_id: str) -> bool:
        """Sets alert status to Closed (historical record).
        
        Does NOT auto-complete work orders - that's a separate concern.
        """
        db = get_db()
        alert = db.get_alert(alert_id)
        if not alert:
            return False
        alert.status = "Closed"
        alert.resolved_at = datetime.now()
        db.update_alert(alert)
        return True

    def get_open_alerts(self) -> List[Alert]:
        """Get all open alerts."""
        db = get_db()
        return db.get_open_alerts()

    def get_alerts_by_machine(self, machine_id: str) -> List[Alert]:
        """Get all alerts for a machine."""
        db = get_db()
        return db.get_alerts_by_machine(machine_id)

    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """Get alerts by severity."""
        db = get_db()
        return db.get_alerts_by_severity(severity.value if hasattr(severity, 'value') else severity)

    def get_all_alerts(self) -> List[Alert]:
        """Get all alerts."""
        db = get_db()
        return db.get_all_alerts()

    def get_alert_summary(self) -> Dict[str, int]:
        """
        Get a mathematically consistent alert summary.
        
        Returns:
            total:      All alerts regardless of status
            open:       Alerts where status == 'Open'
            closed:     Alerts where status == 'Closed' or 'Resolved'
            critical:   Open alerts where severity == 'CRITICAL'
            warning:    Open alerts where severity == 'WARNING'
            info:       Open alerts where severity == 'INFO'
            
        Invariants:
            open == critical + warning + info
            total == open + closed
        """
        db = get_db()
        return db.get_alert_summary()

    def get_critical_alerts(self) -> List[Alert]:
        """Get all critical alerts."""
        return self.get_alerts_by_severity(AlertSeverity.CRITICAL)

    def deduplicate_alerts(self, machine_id: str) -> int:
        """
        Remove duplicate open alerts for a machine.
        Keeps only the most recent open alert, closes the rest.
        Returns the number of duplicates removed.
        """
        db = get_db()
        alerts = db.get_alerts_by_machine(machine_id)
        open_alerts = [a for a in alerts if a.status == "Open"]
        
        if len(open_alerts) <= 1:
            return 0
        
        # Sort by timestamp descending, keep the most recent
        open_alerts.sort(key=lambda a: a.timestamp, reverse=True)
        keep = open_alerts[0]
        removed = 0
        
        for alert in open_alerts[1:]:
            if alert.alert_id != keep.alert_id:
                alert.status = "Closed"
                alert.resolved_at = datetime.now()
                db.update_alert(alert)
                removed += 1
        
        return removed


# ==================== SYNCHRONIZATION ENGINE ====================

class SynchronizationEngine:
    """
    Central synchronization engine that ensures all modules display consistent data.
    
    Whenever machine health changes (simulation, refresh, prediction, Excel update, etc.):
    1. Recalculate Machine Status from health score
    2. Synchronize Alert to match machine status
    3. Synchronize Work Order to match machine status
    4. Synchronize Maintenance Log to match work order status
    5. Update last_maintenance_date when work orders are completed
    6. All derived data (dashboard counts, analytics, reports) automatically
       reads from the single source of truth.
    
    Call synchronize_all() after any state change to ensure consistency.
    """
    
    def __init__(self):
        pass
    
    def synchronize_machine(self, machine: MachineInfo) -> None:
        """
        Synchronize all derived data for a single machine.
        
        Steps:
        1. Ensure machine.status is correct based on health_score
        2. Deduplicate any existing duplicates
        3. Synchronize alert FIRST (so work order can link to it)
        4. Synchronize work orders (with alert_id from step 3)
        5. RELOAD machine from DB after work order processing
        6. DERIVE last_maintenance_date from latest completed maintenance log
        7. Recalculate status AGAIN after work order changes
        8. Persist machine changes
        """
        from simulation import EnterpriseSimulator
        db = get_db()
        
        # Step 1: Ensure machine status is correct based on health score
        self._recalculate_status(machine)
        
        data_store = get_data_store()
        
        # Step 2: Deduplicate any existing duplicates before creating new ones
        data_store.alert_service.deduplicate_alerts(machine.machine_id)
        data_store.work_order_service.deduplicate_work_orders(machine.machine_id)
        data_store.maintenance_log_service.deduplicate_maintenance_logs(machine.machine_id)

        # Ensure only one active work order and one active alert remain for the machine
        active_wos = [wo for wo in db.get_work_orders_by_machine(machine.machine_id) if wo.status in (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)]
        if len(active_wos) > 1:
            for wo in active_wos[1:]:
                wo.status = WorkOrderStatus.CANCELLED
                db.update_work_order(wo)
        
        # Step 3: Synchronize alert FIRST (before work order)
        # This ensures the alert exists and can be linked to the work order
        if machine.status in (MachineStatus.WARNING, MachineStatus.CRITICAL):
            data_store.alert_service.auto_create_from_machine_status(machine)
        
        # Step 4: Synchronize work orders (with alert_id from step 3)
        if machine.status in (MachineStatus.WARNING, MachineStatus.CRITICAL):
            alert = data_store.alert_service.get_active_alert_by_machine(machine.machine_id)
            data_store.work_order_service.auto_create_from_machine_status(machine, alert)
        elif machine.status == MachineStatus.NORMAL:
            # Close all open work orders for this machine
            self._close_open_work_orders(machine)
        
        # Step 5: RELOAD machine from DB to pick up any changes from work order completion
        db_machine = db.get_machine(machine.machine_id)
        if db_machine:
            machine.health_score = db_machine.health_score
            machine.status = db_machine.status
            machine.failure_probability = db_machine.failure_probability
            machine.last_maintenance_date = db_machine.last_maintenance_date
            machine.next_maintenance_date = db_machine.next_maintenance_date
        
        # Step 6: Derive last_maintenance_date from the latest completed maintenance log
        # This ensures Machine Details always shows the same date as Maintenance Logs
        latest_log = db.get_latest_completed_maintenance_log(machine.machine_id)
        if latest_log:
            machine.last_maintenance_date = latest_log.maintenance_date
        elif machine.last_maintenance_date is not None:
            # No completed maintenance logs exist - clear the fake date
            machine.last_maintenance_date = None
        
        # Step 7: Recalculate status AFTER work order changes (maintenance may have improved health)
        self._recalculate_status(machine)
        
        # Step 8: Persist machine changes
        db.update_machine(machine)
    
    def _close_open_work_orders(self, machine: MachineInfo) -> int:
        """
        Close all open work orders for a machine.
        When closing work orders, properly complete them with maintenance log updates.
        The machine object is passed directly so it gets updated with new health/status.
        Returns count closed.
        """
        db = get_db()
        data_store = get_data_store()
        wos = db.get_work_orders_by_machine(machine.machine_id)
        count = 0
        for wo in wos:
            if wo.status in (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS):
                # Properly complete the work order with maintenance log update
                wo.status = WorkOrderStatus.COMPLETED
                wo.completed_date = datetime.now()
                data_store.work_order_service._complete_maintenance_log_from_work_order(wo)
                db.update_work_order(wo)
                count += 1
        return count
    
    def _get_effective_status(self, machine: MachineInfo) -> MachineStatus:
        """Return the authoritative machine state from ML prediction when available."""
        ml_prediction = getattr(machine, "ml_prediction", None) or {}
        predicted_status = ml_prediction.get("predicted_status")
        if isinstance(predicted_status, str):
            normalized_status = predicted_status.upper()
            if normalized_status == "CRITICAL":
                return MachineStatus.CRITICAL
            if normalized_status == "WARNING":
                return MachineStatus.WARNING
            if normalized_status == "NORMAL":
                return MachineStatus.NORMAL

        if machine.health_score < 60:
            return MachineStatus.CRITICAL
        if machine.health_score < 85:
            return MachineStatus.WARNING
        return MachineStatus.NORMAL

    def _recalculate_status(self, machine: MachineInfo) -> None:
        """Recalculate the authoritative machine state while preserving ML-driven decisions."""
        machine.status = self._get_effective_status(machine)
        machine.condition = "Critical" if machine.status == MachineStatus.CRITICAL else "Warning" if machine.status == MachineStatus.WARNING else "Normal"
        if not machine.cause:
            machine.cause = "Sensor readings within normal range"
        if machine.status == MachineStatus.CRITICAL or machine.health_score < 60 or machine.failure_probability >= 0.55:
            machine.maintenance_recommendation = "Immediate Inspection Required"
        elif machine.status == MachineStatus.WARNING or machine.health_score < 85 or machine.failure_probability >= 0.25:
            machine.maintenance_recommendation = "Within 7 Days"
        elif machine.failure_probability >= 0.12:
            machine.maintenance_recommendation = "Within 14 Days"
        else:
            machine.maintenance_recommendation = "Within 30 Days"
    
    def synchronize_all(self) -> None:
        """
        Synchronize ALL machines and their derived data.
        
        This is the master synchronization method that should be called
        after any bulk state change (simulation step, data refresh, etc.).
        """
        from simulation import EnterpriseSimulator
        simulator = EnterpriseSimulator()
        all_machines = simulator.get_all_machines()
        
        for machine in all_machines:
            self.synchronize_machine(machine)
    
    def validate_consistency(self) -> Dict[str, Any]:
        """
        Validate that all derived data is consistent with the single source of truth.
        
        Returns a dict with validation results and any inconsistencies found.
        """
        from simulation import EnterpriseSimulator
        simulator = EnterpriseSimulator()
        data_store = get_data_store()
        db = get_db()
        
        all_machines = simulator.get_all_machines()
        issues = []
        
        for machine in all_machines:
            # Check 1: Machine status follows the authoritative ML-driven state when available
            expected_status = self._get_effective_status(machine)
            
            if machine.status != expected_status:
                issues.append(f"{machine.machine_id}: status={machine.status.value} but health={machine.health_score}% (expected {expected_status.value})")
            
            # Check 2: Active alert matches machine status
            active_alert = data_store.alert_service.get_active_alert_by_machine(machine.machine_id)
            
            if machine.status == MachineStatus.NORMAL:
                if active_alert is not None:
                    issues.append(f"{machine.machine_id}: NORMAL but has active alert {active_alert.alert_id}")
            elif machine.status == MachineStatus.WARNING:
                if active_alert is None:
                    issues.append(f"{machine.machine_id}: WARNING but no active alert")
                elif active_alert.severity != AlertSeverity.WARNING:
                    issues.append(f"{machine.machine_id}: WARNING but alert severity is {active_alert.severity.value}")
            elif machine.status == MachineStatus.CRITICAL:
                if active_alert is None:
                    issues.append(f"{machine.machine_id}: CRITICAL but no active alert")
                elif active_alert.severity != AlertSeverity.CRITICAL:
                    issues.append(f"{machine.machine_id}: CRITICAL but alert severity is {active_alert.severity.value}")
            
            # Check 3: No duplicate active alerts
            all_alerts = db.get_alerts_by_machine(machine.machine_id)
            open_alerts = [a for a in all_alerts if a.status == "Open"]
            if len(open_alerts) > 1:
                issues.append(f"{machine.machine_id}: {len(open_alerts)} open alerts (max 1 allowed)")
            
            # Check 4: No duplicate active work orders
            if machine.status in (MachineStatus.WARNING, MachineStatus.CRITICAL):
                active_wos = [wo for wo in db.get_work_orders_by_machine(machine.machine_id) 
                             if wo.status in (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)]
                if len(active_wos) > 1:
                    issues.append(f"{machine.machine_id}: {len(active_wos)} active work orders (max 1 allowed)")
            
            # Check 5: No duplicate active maintenance logs
            logs = db.get_maintenance_logs_by_machine(machine.machine_id)
            active_logs = [log for log in logs if log.status in ("Scheduled", "In Progress")]
            if len(active_logs) > 1:
                issues.append(f"{machine.machine_id}: {len(active_logs)} active maintenance logs (max 1 allowed)")
            
            # Check 6: Last maintenance date should not be N/A if maintenance logs exist
            completed_logs = [log for log in logs if log.status == "Completed"]
            if completed_logs and machine.last_maintenance_date is None:
                issues.append(f"{machine.machine_id}: has {len(completed_logs)} completed maintenance logs but last_maintenance_date is None")
            
            # Check 7: Last maintenance date must match latest completed log
            if completed_logs:
                latest_log = completed_logs[0]  # Already sorted DESC by DB query
                if machine.last_maintenance_date != latest_log.maintenance_date:
                    issues.append(f"{machine.machine_id}: last_maintenance_date ({machine.last_maintenance_date}) != latest completed log date ({latest_log.maintenance_date})")
        
        # Check 7: Dashboard counts match machine states
        critical_machines = sum(1 for m in all_machines if m.status == MachineStatus.CRITICAL)
        warning_machines = sum(1 for m in all_machines if m.status == MachineStatus.WARNING)
        healthy_machines = sum(1 for m in all_machines if m.status == MachineStatus.NORMAL)
        
        open_alerts = data_store.alert_service.get_open_alerts()
        critical_alerts = [a for a in open_alerts if a.severity == AlertSeverity.CRITICAL]
        warning_alerts = [a for a in open_alerts if a.severity == AlertSeverity.WARNING]
        
        return {
            "consistent": len(issues) == 0,
            "total_machines": len(all_machines),
            "critical_machines": critical_machines,
            "warning_machines": warning_machines,
            "healthy_machines": healthy_machines,
            "open_alerts": len(open_alerts),
            "critical_alerts": len(critical_alerts),
            "warning_alerts": len(warning_alerts),
            "issues": issues
        }
    
    def auto_repair(self) -> int:
        """
        Automatically repair any inconsistencies found.
        
        Returns the number of machines that were repaired.
        """
        validation = self.validate_consistency()
        if validation["consistent"]:
            return 0
        
        # Step 1: Backfill last_maintenance_date from completed maintenance logs
        self._backfill_maintenance_dates()
        
        # Step 2: Re-synchronize all machines to fix inconsistencies
        self.synchronize_all()
        
        # Re-validate
        revalidation = self.validate_consistency()
        if revalidation["consistent"]:
            return len(validation["issues"])
        
        # If still inconsistent, do a more aggressive repair
        from simulation import EnterpriseSimulator
        simulator = EnterpriseSimulator()
        data_store = get_data_store()
        db = get_db()
        
        repair_count = 0
        for machine in simulator.get_all_machines():
            # Force recalculate status using the same authoritative logic as runtime
            machine.status = self._get_effective_status(machine)
            
            # Force deduplicate
            data_store.alert_service.deduplicate_alerts(machine.machine_id)
            data_store.work_order_service.deduplicate_work_orders(machine.machine_id)
            data_store.maintenance_log_service.deduplicate_maintenance_logs(machine.machine_id)
            
            # Force close all open alerts for NORMAL machines
            if machine.status == MachineStatus.NORMAL:
                data_store.alert_service.close_all_open_alerts_by_machine(machine.machine_id)
            else:
                # Force create/update alert
                data_store.alert_service.auto_create_from_machine_status(machine)
            
            db.update_machine(machine)
            repair_count += 1
        
        return repair_count
    
    def _backfill_maintenance_dates(self) -> int:
        """
        Fix last_maintenance_date for ALL machines by deriving it from the latest 
        completed maintenance log.
        
        This handles:
        1. Machines with no last_maintenance_date set
        2. Machines with mismatched last_maintenance_date (different from latest log)
        
        Returns the number of machines corrected.
        """
        from simulation import EnterpriseSimulator
        simulator = EnterpriseSimulator()
        db = get_db()
        
        count = 0
        for machine in simulator.get_all_machines():
            # Get the latest completed maintenance log
            latest_log = db.get_latest_completed_maintenance_log(machine.machine_id)
            
            if latest_log:
                # Derive last_maintenance_date from the maintenance log
                if machine.last_maintenance_date != latest_log.maintenance_date:
                    machine.last_maintenance_date = latest_log.maintenance_date
                    
                    # Also set next_maintenance_date if not set (30-90 days from last)
                    if machine.next_maintenance_date is None:
                        next_maint_days = random.randint(30, 90)
                        machine.next_maintenance_date = machine.last_maintenance_date + timedelta(days=next_maint_days)
                    
                    db.update_machine(machine)
                    count += 1
            else:
                # No completed maintenance logs exist - clear any fake date
                if machine.last_maintenance_date is not None:
                    machine.last_maintenance_date = None
                    db.update_machine(machine)
                    count += 1
        
        return count


# Singleton accessor for synchronization engine
_sync_engine = None

def get_sync_engine() -> SynchronizationEngine:
    """Get the synchronization engine singleton."""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = SynchronizationEngine()
    return _sync_engine


# ==================== ENTERPRISE DATA STORE ====================

class EnterpriseDataStore:
    """
    Central data store for the enterprise platform.
    Singleton that holds references to all services.
    All data is persisted in SQLite.
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
        
        # Register this instance as the global singleton for reliable access
        set_data_store(self)
        
        # Historical sensor data cache (still in-memory, populated from DB as needed)
        self.sensor_history: Dict[str, Dict[str, List[Dict]]] = {}
        
        # Prediction cache (in-memory, rebuilt on restart)
        self.prediction_history: Dict[str, List[Dict]] = {}
        
        # Report cache (in-memory)
        self.generated_reports: List[Dict] = []
    
    def reset(self):
        """Reset all data (for testing/restart)."""
        self.__init__()


# Singleton accessor (backward compatibility)
def get_data_store_old() -> EnterpriseDataStore:
    """Get the enterprise data store singleton."""
    return EnterpriseDataStore()