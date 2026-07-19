"""
SQLite Database Layer for Predictive Maintenance Platform

Provides persistent storage for machines, alerts, work orders,
maintenance logs, and sensor history.
"""

import sqlite3
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date

from models import (
    MachineInfo, MachineStatus, MachineType, Alert, AlertSeverity,
    WorkOrder, WorkOrderStatus, MaintenanceLog, MaintenanceType,
    SensorType
)

DB_PATH = os.path.join(os.path.dirname(__file__), "predictive_maintenance.db")


def _serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _deserialize_datetime(s: Optional[str]) -> Optional[datetime]:
    if s is None or s == "":
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _serialize_date(d: Optional[date]) -> Optional[str]:
    if d is None:
        return None
    return d.isoformat()


def _deserialize_date(s: Optional[str]) -> Optional[date]:
    if s is None or s == "":
        return None
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


class DatabaseManager:
    """Manages all SQLite operations for the predictive maintenance platform."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_tables(self):
        """Create all tables if they don't exist."""
        conn = self._get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS Machines (
                    machine_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    machine_type TEXT NOT NULL,
                    production_line TEXT DEFAULT '',
                    factory_id TEXT DEFAULT '',
                    manufacturer TEXT DEFAULT 'Default Corp',
                    model_number TEXT DEFAULT '',
                    installation_date TEXT,
                    operating_hours REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'NORMAL',
                    health_score REAL DEFAULT 100.0,
                    failure_probability REAL DEFAULT 0.0,
                    last_maintenance_date TEXT,
                    next_maintenance_date TEXT,
                    supported_sensors TEXT DEFAULT '[]',
                    serial_number TEXT DEFAULT '',
                    color TEXT DEFAULT '',
                    purchase_date TEXT,
                    warranty_expiry TEXT,
                    supplier TEXT DEFAULT '',
                    purchase_cost REAL DEFAULT 0.0,
                    location TEXT DEFAULT '',
                    department TEXT DEFAULT '',
                    assigned_technician TEXT DEFAULT '',
                    capacity TEXT DEFAULT '',
                    power_rating TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS Alerts (
                    alert_id TEXT PRIMARY KEY,
                    machine_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    recommended_action TEXT DEFAULT '',
                    status TEXT DEFAULT 'Open',
                    acknowledged_by TEXT,
                    resolved_at TEXT,
                    FOREIGN KEY (machine_id) REFERENCES Machines(machine_id)
                );

                CREATE TABLE IF NOT EXISTS WorkOrders (
                    work_order_id TEXT PRIMARY KEY,
                    machine_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status TEXT DEFAULT 'Open',
                    priority TEXT DEFAULT 'Medium',
                    assigned_technician TEXT DEFAULT 'Unassigned',
                    created_date TEXT NOT NULL,
                    scheduled_date TEXT,
                    due_date TEXT,
                    completed_date TEXT,
                    estimated_hours REAL DEFAULT 0.0,
                    actual_hours REAL DEFAULT 0.0,
                    parts_replaced TEXT DEFAULT '[]',
                    cost REAL DEFAULT 0.0,
                    remarks TEXT DEFAULT '',
                    created_by TEXT DEFAULT 'AI System',
                    alert_id TEXT,
                    machine_name TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    current_health_score REAL DEFAULT 0.0,
                    current_status TEXT DEFAULT '',
                    maintenance_type TEXT DEFAULT '',
                    issue_description TEXT DEFAULT '',
                    ai_recommendation TEXT DEFAULT '',
                    FOREIGN KEY (machine_id) REFERENCES Machines(machine_id)
                );

                CREATE TABLE IF NOT EXISTS MaintenanceLogs (
                    log_id TEXT PRIMARY KEY,
                    machine_id TEXT NOT NULL,
                    maintenance_date TEXT NOT NULL,
                    technician TEXT NOT NULL,
                    maintenance_type TEXT NOT NULL,
                    issue TEXT DEFAULT '',
                    action_taken TEXT DEFAULT '',
                    parts_replaced TEXT DEFAULT '[]',
                    cost REAL DEFAULT 0.0,
                    duration_hours REAL DEFAULT 0.0,
                    remarks TEXT DEFAULT '',
                    work_order_id TEXT,
                    machine_name TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    start_time TEXT,
                    end_time TEXT,
                    downtime_hours REAL DEFAULT 0.0,
                    before_health REAL DEFAULT 0.0,
                    after_health REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'Completed',
                    created_date TEXT NOT NULL,
                    FOREIGN KEY (machine_id) REFERENCES Machines(machine_id)
                );

                CREATE TABLE IF NOT EXISTS SensorHistory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    sensor_type TEXT NOT NULL,
                    sensor_value REAL NOT NULL,
                    status TEXT DEFAULT 'normal',
                    FOREIGN KEY (machine_id) REFERENCES Machines(machine_id)
                );

                CREATE INDEX IF NOT EXISTS idx_alerts_machine ON Alerts(machine_id);
                CREATE INDEX IF NOT EXISTS idx_alerts_status ON Alerts(status);
                CREATE INDEX IF NOT EXISTS idx_workorders_machine ON WorkOrders(machine_id);
                CREATE INDEX IF NOT EXISTS idx_workorders_status ON WorkOrders(status);
                CREATE INDEX IF NOT EXISTS idx_maintenance_machine ON MaintenanceLogs(machine_id);
                CREATE INDEX IF NOT EXISTS idx_maintenance_workorder ON MaintenanceLogs(work_order_id);
                CREATE INDEX IF NOT EXISTS idx_sensorhistory_machine ON SensorHistory(machine_id);
                CREATE INDEX IF NOT EXISTS idx_sensorhistory_time ON SensorHistory(timestamp);
            """)
            conn.commit()
        finally:
            conn.close()

    # ==================== MACHINE OPERATIONS ====================

    def machine_exists(self, machine_id: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT 1 FROM Machines WHERE machine_id = ?", (machine_id,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_machine_count(self) -> int:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM Machines")
            row = cursor.fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def insert_machine(self, machine: MachineInfo):
        conn = self._get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO Machines
                   (machine_id, name, machine_type, production_line, factory_id,
                    manufacturer, model_number, installation_date, operating_hours,
                    status, health_score, failure_probability,
                    last_maintenance_date, next_maintenance_date, supported_sensors,
                    serial_number, color, purchase_date, warranty_expiry,
                    supplier, purchase_cost, location, department,
                    assigned_technician, capacity, power_rating)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    machine.machine_id,
                    machine.name,
                    machine.machine_type.value if hasattr(machine.machine_type, 'value') else machine.machine_type,
                    machine.production_line,
                    machine.factory_id,
                    machine.manufacturer,
                    machine.model_number,
                    _serialize_datetime(machine.installation_date),
                    machine.operating_hours,
                    machine.status.value if hasattr(machine.status, 'value') else machine.status,
                    machine.health_score,
                    machine.failure_probability,
                    _serialize_datetime(machine.last_maintenance_date),
                    _serialize_datetime(machine.next_maintenance_date),
                    json.dumps([s.value if hasattr(s, 'value') else s for s in machine.supported_sensors]),
                    machine.serial_number,
                    machine.color,
                    _serialize_datetime(machine.purchase_date),
                    _serialize_datetime(machine.warranty_expiry),
                    machine.supplier,
                    machine.purchase_cost,
                    machine.location,
                    machine.department,
                    machine.assigned_technician,
                    machine.capacity,
                    machine.power_rating,
                )
            )
            conn.commit()
        finally:
            conn.close()

    def update_machine(self, machine: MachineInfo):
        """Update an existing machine's dynamic fields."""
        conn = self._get_connection()
        try:
            conn.execute(
                """UPDATE Machines SET
                    operating_hours = ?,
                    status = ?,
                    health_score = ?,
                    failure_probability = ?,
                    last_maintenance_date = ?,
                    next_maintenance_date = ?
                   WHERE machine_id = ?""",
                (
                    machine.operating_hours,
                    machine.status.value if hasattr(machine.status, 'value') else machine.status,
                    machine.health_score,
                    machine.failure_probability,
                    _serialize_datetime(machine.last_maintenance_date),
                    _serialize_datetime(machine.next_maintenance_date),
                    machine.machine_id
                )
            )
            conn.commit()
        finally:
            conn.close()

    def get_machine(self, machine_id: str) -> Optional[MachineInfo]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM Machines WHERE machine_id = ?", (machine_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_machine(row)
        finally:
            conn.close()

    def get_all_machines(self) -> List[MachineInfo]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM Machines ORDER BY machine_id")
            return [self._row_to_machine(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_machines_by_factory(self, factory_id: str) -> List[MachineInfo]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM Machines WHERE factory_id = ? ORDER BY machine_id",
                (factory_id,)
            )
            return [self._row_to_machine(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_machines_by_type(self, machine_type: str) -> List[MachineInfo]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM Machines WHERE machine_type = ? ORDER BY machine_id",
                (machine_type,)
            )
            return [self._row_to_machine(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _row_to_machine(self, row: sqlite3.Row) -> MachineInfo:
        supported_sensors_raw = row["supported_sensors"] if row["supported_sensors"] else "[]"
        try:
            sensor_values = json.loads(supported_sensors_raw)
        except (json.JSONDecodeError, TypeError):
            sensor_values = []
        supported_sensors = []
        for sv in sensor_values:
            try:
                supported_sensors.append(SensorType(sv))
            except ValueError:
                pass

        machine_type_val = row["machine_type"]
        try:
            machine_type = MachineType(machine_type_val)
        except ValueError:
            machine_type = machine_type_val

        status_val = row["status"]
        try:
            status = MachineStatus(status_val)
        except ValueError:
            status = MachineStatus.UNKNOWN

        return MachineInfo(
            machine_id=row["machine_id"],
            name=row["name"],
            machine_type=machine_type,
            production_line=row["production_line"] or "",
            factory_id=row["factory_id"] or "",
            manufacturer=row["manufacturer"] or "Default Corp",
            model_number=row["model_number"] or "",
            installation_date=_deserialize_datetime(row["installation_date"]) or datetime.now(),
            operating_hours=row["operating_hours"] or 0.0,
            status=status,
            health_score=row["health_score"] or 100.0,
            failure_probability=row["failure_probability"] or 0.0,
            last_maintenance_date=_deserialize_datetime(row["last_maintenance_date"]),
            next_maintenance_date=_deserialize_datetime(row["next_maintenance_date"]),
            supported_sensors=supported_sensors,
            serial_number=row["serial_number"] if "serial_number" in row else "",
            color=row["color"] if "color" in row else "",
            purchase_date=_deserialize_datetime(row["purchase_date"]) if "purchase_date" in row else None,
            warranty_expiry=_deserialize_datetime(row["warranty_expiry"]) if "warranty_expiry" in row else None,
            supplier=row["supplier"] if "supplier" in row else "",
            purchase_cost=row["purchase_cost"] if "purchase_cost" in row else 0.0,
            location=row["location"] if "location" in row else "",
            department=row["department"] if "department" in row else "",
            assigned_technician=row["assigned_technician"] if "assigned_technician" in row else "",
            capacity=row["capacity"] if "capacity" in row else "",
            power_rating=row["power_rating"] if "power_rating" in row else "",
        )

    # ==================== ALERT OPERATIONS ====================

    def insert_alert(self, alert: Alert):
        conn = self._get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO Alerts
                   (alert_id, machine_id, severity, reason, timestamp,
                    recommended_action, status, acknowledged_by, resolved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    alert.alert_id,
                    alert.machine_id,
                    alert.severity.value if hasattr(alert.severity, 'value') else alert.severity,
                    alert.reason,
                    _serialize_datetime(alert.timestamp),
                    alert.recommended_action,
                    alert.status,
                    alert.acknowledged_by,
                    _serialize_datetime(alert.resolved_at)
                )
            )
            conn.commit()
        finally:
            conn.close()

    def update_alert(self, alert: Alert):
        conn = self._get_connection()
        try:
            conn.execute(
                """UPDATE Alerts SET
                    status = ?, severity = ?, reason = ?,
                    recommended_action = ?, acknowledged_by = ?,
                    resolved_at = ?
                   WHERE alert_id = ?""",
                (
                    alert.status,
                    alert.severity.value if hasattr(alert.severity, 'value') else alert.severity,
                    alert.reason,
                    alert.recommended_action,
                    alert.acknowledged_by,
                    _serialize_datetime(alert.resolved_at),
                    alert.alert_id
                )
            )
            conn.commit()
        finally:
            conn.close()

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM Alerts WHERE alert_id = ?", (alert_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_alert(row)
        finally:
            conn.close()

    def get_all_alerts(self) -> List[Alert]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM Alerts ORDER BY timestamp DESC")
            return [self._row_to_alert(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_alerts_by_machine(self, machine_id: str) -> List[Alert]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM Alerts WHERE machine_id = ? ORDER BY timestamp DESC",
                (machine_id,)
            )
            return [self._row_to_alert(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_active_alert_by_machine(self, machine_id: str) -> Optional[Alert]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM Alerts WHERE machine_id = ? AND status = 'Open' LIMIT 1",
                (machine_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_alert(row)
        finally:
            conn.close()

    def get_open_alerts(self) -> List[Alert]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM Alerts WHERE status = 'Open' ORDER BY timestamp DESC"
            )
            return [self._row_to_alert(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_alerts_by_severity(self, severity: str) -> List[Alert]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM Alerts WHERE severity = ? AND status = 'Open' ORDER BY timestamp DESC",
                (severity,)
            )
            return [self._row_to_alert(row) for row in cursor.fetchall()]
        finally:
            conn.close()

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
        conn = self._get_connection()
        try:
            # Total alerts
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM Alerts")
            row = cursor.fetchone()
            total = row["cnt"] if row else 0
            
            # Open alerts by severity
            cursor = conn.execute(
                """SELECT severity, COUNT(*) as cnt FROM Alerts
                   WHERE status = 'Open' GROUP BY severity"""
            )
            open_by_severity = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
            for row in cursor.fetchall():
                sev = row["severity"]
                cnt = row["cnt"]
                if sev in open_by_severity:
                    open_by_severity[sev] = cnt
            
            open_count = sum(open_by_severity.values())
            
            # Closed/Resolved alerts
            cursor = conn.execute(
                "SELECT COUNT(*) as cnt FROM Alerts WHERE status IN ('Closed', 'Resolved')"
            )
            row = cursor.fetchone()
            closed_count = row["cnt"] if row else 0
            
            return {
                "total": total,
                "open": open_count,
                "closed": closed_count,
                "critical": open_by_severity["CRITICAL"],
                "warning": open_by_severity["WARNING"],
                "info": open_by_severity["INFO"],
            }
        finally:
            conn.close()

    def _row_to_alert(self, row: sqlite3.Row) -> Alert:
        sev = row["severity"]
        try:
            severity = AlertSeverity(sev)
        except ValueError:
            severity = AlertSeverity.WARNING

        return Alert(
            alert_id=row["alert_id"],
            machine_id=row["machine_id"],
            severity=severity,
            reason=row["reason"],
            timestamp=_deserialize_datetime(row["timestamp"]) or datetime.now(),
            recommended_action=row["recommended_action"] or "",
            status=row["status"] or "Open",
            acknowledged_by=row["acknowledged_by"],
            resolved_at=_deserialize_datetime(row["resolved_at"])
        )

    # ==================== WORK ORDER OPERATIONS ====================

    def insert_work_order(self, wo: WorkOrder):
        conn = self._get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO WorkOrders
                   (work_order_id, machine_id, title, description, status,
                    priority, assigned_technician, created_date, scheduled_date,
                    due_date, completed_date, estimated_hours, actual_hours,
                    parts_replaced, cost, remarks, created_by, alert_id,
                    machine_name, category, current_health_score, current_status,
                    maintenance_type, issue_description, ai_recommendation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    wo.work_order_id,
                    wo.machine_id,
                    wo.title,
                    wo.description,
                    wo.status.value if hasattr(wo.status, 'value') else wo.status,
                    wo.priority,
                    wo.assigned_technician,
                    _serialize_datetime(wo.created_date),
                    _serialize_date(wo.scheduled_date),
                    _serialize_date(wo.due_date),
                    _serialize_datetime(wo.completed_date),
                    wo.estimated_hours,
                    wo.actual_hours,
                    json.dumps(wo.parts_replaced),
                    wo.cost,
                    wo.remarks,
                    wo.created_by,
                    wo.alert_id,
                    wo.machine_name,
                    wo.category,
                    wo.current_health_score,
                    wo.current_status,
                    wo.maintenance_type,
                    wo.issue_description,
                    wo.ai_recommendation
                )
            )
            conn.commit()
        finally:
            conn.close()

    def update_work_order(self, wo: WorkOrder):
        conn = self._get_connection()
        try:
            conn.execute(
                """UPDATE WorkOrders SET
                    status = ?, priority = ?, assigned_technician = ?,
                    scheduled_date = ?, due_date = ?, completed_date = ?,
                    estimated_hours = ?, actual_hours = ?, parts_replaced = ?,
                    cost = ?, remarks = ?, machine_name = ?, category = ?,
                    current_health_score = ?, current_status = ?,
                    maintenance_type = ?, issue_description = ?,
                    ai_recommendation = ?, description = ?, title = ?
                   WHERE work_order_id = ?""",
                (
                    wo.status.value if hasattr(wo.status, 'value') else wo.status,
                    wo.priority,
                    wo.assigned_technician,
                    _serialize_date(wo.scheduled_date),
                    _serialize_date(wo.due_date),
                    _serialize_datetime(wo.completed_date),
                    wo.estimated_hours,
                    wo.actual_hours,
                    json.dumps(wo.parts_replaced),
                    wo.cost,
                    wo.remarks,
                    wo.machine_name,
                    wo.category,
                    wo.current_health_score,
                    wo.current_status,
                    wo.maintenance_type,
                    wo.issue_description,
                    wo.ai_recommendation,
                    wo.description,
                    wo.title,
                    wo.work_order_id
                )
            )
            conn.commit()
        finally:
            conn.close()

    def get_work_order(self, work_order_id: str) -> Optional[WorkOrder]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM WorkOrders WHERE work_order_id = ?", (work_order_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_work_order(row)
        finally:
            conn.close()

    def get_all_work_orders(self) -> List[WorkOrder]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM WorkOrders ORDER BY created_date DESC")
            return [self._row_to_work_order(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_work_orders_by_machine(self, machine_id: str) -> List[WorkOrder]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM WorkOrders WHERE machine_id = ? ORDER BY created_date DESC",
                (machine_id,)
            )
            return [self._row_to_work_order(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_work_orders_by_status(self, status: str) -> List[WorkOrder]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM WorkOrders WHERE status = ? ORDER BY created_date DESC",
                (status,)
            )
            return [self._row_to_work_order(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_open_work_orders(self) -> List[WorkOrder]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM WorkOrders WHERE status IN ('Open', 'In Progress') ORDER BY created_date DESC"
            )
            return [self._row_to_work_order(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def has_active_work_order(self, machine_id: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT 1 FROM WorkOrders WHERE machine_id = ? AND status IN ('Open', 'In Progress') LIMIT 1",
                (machine_id,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_work_order_summary(self) -> Dict[str, int]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM WorkOrders GROUP BY status"
            )
            summary = {"Open": 0, "In Progress": 0, "Completed": 0, "Cancelled": 0}
            for row in cursor.fetchall():
                status_key = row["status"]
                if status_key in summary:
                    summary[status_key] = row["cnt"]
            return summary
        finally:
            conn.close()

    def delete_work_order(self, work_order_id: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute("DELETE FROM WorkOrders WHERE work_order_id = ?", (work_order_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_work_order(self, row: sqlite3.Row) -> WorkOrder:
        status_val = row["status"]
        try:
            status = WorkOrderStatus(status_val)
        except ValueError:
            status = WorkOrderStatus.OPEN

        parts_raw = row["parts_replaced"] if row["parts_replaced"] else "[]"
        try:
            parts_replaced = json.loads(parts_raw)
        except (json.JSONDecodeError, TypeError):
            parts_replaced = []

        return WorkOrder(
            work_order_id=row["work_order_id"],
            machine_id=row["machine_id"],
            title=row["title"],
            description=row["description"] or "",
            status=status,
            priority=row["priority"] or "Medium",
            assigned_technician=row["assigned_technician"] or "Unassigned",
            created_date=_deserialize_datetime(row["created_date"]) or datetime.now(),
            scheduled_date=_deserialize_date(row["scheduled_date"]),
            due_date=_deserialize_date(row["due_date"]),
            completed_date=_deserialize_datetime(row["completed_date"]),
            estimated_hours=row["estimated_hours"] or 0.0,
            actual_hours=row["actual_hours"] or 0.0,
            parts_replaced=parts_replaced,
            cost=row["cost"] or 0.0,
            remarks=row["remarks"] or "",
            created_by=row["created_by"] or "AI System",
            alert_id=row["alert_id"],
            machine_name=row["machine_name"] or "",
            category=row["category"] or "",
            current_health_score=row["current_health_score"] or 0.0,
            current_status=row["current_status"] or "",
            maintenance_type=row["maintenance_type"] or "",
            issue_description=row["issue_description"] or "",
            ai_recommendation=row["ai_recommendation"] or ""
        )

    # ==================== MAINTENANCE LOG OPERATIONS ====================

    def insert_maintenance_log(self, log: MaintenanceLog):
        conn = self._get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO MaintenanceLogs
                   (log_id, machine_id, maintenance_date, technician,
                    maintenance_type, issue, action_taken, parts_replaced,
                    cost, duration_hours, remarks, work_order_id,
                    machine_name, category, description, start_time,
                    end_time, downtime_hours, before_health, after_health,
                    status, created_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    log.log_id,
                    log.machine_id,
                    _serialize_datetime(log.maintenance_date),
                    log.technician,
                    log.maintenance_type.value if hasattr(log.maintenance_type, 'value') else log.maintenance_type,
                    log.issue,
                    log.action_taken,
                    json.dumps(log.parts_replaced),
                    log.cost,
                    log.duration_hours,
                    log.remarks,
                    log.work_order_id,
                    log.machine_name,
                    log.category,
                    log.description,
                    _serialize_datetime(log.start_time),
                    _serialize_datetime(log.end_time),
                    log.downtime_hours,
                    log.before_health,
                    log.after_health,
                    log.status,
                    _serialize_datetime(log.created_date)
                )
            )
            conn.commit()
        finally:
            conn.close()

    def update_maintenance_log(self, log_id: str, **kwargs):
        """Update fields on an existing maintenance log."""
        if not kwargs:
            return
        set_clause = ", ".join(f"{key} = ?" for key in kwargs)
        values = [kwargs[key] for key in kwargs]
        values.append(log_id)
        conn = self._get_connection()
        try:
            conn.execute(
                f"UPDATE MaintenanceLogs SET {set_clause} WHERE log_id = ?",
                values
            )
            conn.commit()
        finally:
            conn.close()

    def get_maintenance_log(self, log_id: str) -> Optional[MaintenanceLog]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM MaintenanceLogs WHERE log_id = ?", (log_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_maintenance_log(row)
        finally:
            conn.close()

    def get_maintenance_log_by_work_order(self, work_order_id: str) -> Optional[MaintenanceLog]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM MaintenanceLogs WHERE work_order_id = ? LIMIT 1",
                (work_order_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_maintenance_log(row)
        finally:
            conn.close()

    def get_all_maintenance_logs(self) -> List[MaintenanceLog]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM MaintenanceLogs ORDER BY maintenance_date DESC")
            return [self._row_to_maintenance_log(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_maintenance_logs_by_machine(self, machine_id: str) -> List[MaintenanceLog]:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM MaintenanceLogs WHERE machine_id = ? ORDER BY maintenance_date DESC",
                (machine_id,)
            )
            return [self._row_to_maintenance_log(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_recent_maintenance_logs(self, days: int = 30) -> List[MaintenanceLog]:
        cutoff = datetime.now()
        cutoff_str = _serialize_datetime(cutoff)
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM MaintenanceLogs WHERE maintenance_date >= ? ORDER BY maintenance_date DESC",
                (cutoff_str,)
            )
            return [self._row_to_maintenance_log(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_maintenance_log(self, log_id: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute("DELETE FROM MaintenanceLogs WHERE log_id = ?", (log_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_maintenance_log_by_work_order(self, work_order_id: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM MaintenanceLogs WHERE work_order_id = ?",
                (work_order_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_maintenance_log(self, row: sqlite3.Row) -> MaintenanceLog:
        maint_type_val = row["maintenance_type"]
        try:
            maintenance_type = MaintenanceType(maint_type_val)
        except ValueError:
            maintenance_type = MaintenanceType.PREVENTIVE

        parts_raw = row["parts_replaced"] if row["parts_replaced"] else "[]"
        try:
            parts_replaced = json.loads(parts_raw)
        except (json.JSONDecodeError, TypeError):
            parts_replaced = []

        return MaintenanceLog(
            log_id=row["log_id"],
            machine_id=row["machine_id"],
            maintenance_date=_deserialize_datetime(row["maintenance_date"]) or datetime.now(),
            technician=row["technician"] or "",
            maintenance_type=maintenance_type,
            issue=row["issue"] or "",
            action_taken=row["action_taken"] or "",
            parts_replaced=parts_replaced,
            cost=row["cost"] or 0.0,
            duration_hours=row["duration_hours"] or 0.0,
            remarks=row["remarks"] or "",
            work_order_id=row["work_order_id"],
            machine_name=row["machine_name"] or "",
            category=row["category"] or "",
            description=row["description"] or "",
            start_time=_deserialize_datetime(row["start_time"]),
            end_time=_deserialize_datetime(row["end_time"]),
            downtime_hours=row["downtime_hours"] or 0.0,
            before_health=row["before_health"] or 0.0,
            after_health=row["after_health"] or 0.0,
            status=row["status"] or "Completed",
            created_date=_deserialize_datetime(row["created_date"]) or datetime.now()
        )

    # ==================== SENSOR HISTORY OPERATIONS ====================

    def insert_sensor_reading(self, machine_id: str, timestamp: datetime,
                              sensor_type: str, sensor_value: float, status: str = "normal"):
        conn = self._get_connection()
        try:
            conn.execute(
                "INSERT INTO SensorHistory (machine_id, timestamp, sensor_type, sensor_value, status) VALUES (?, ?, ?, ?, ?)",
                (machine_id, _serialize_datetime(timestamp), sensor_type, sensor_value, status)
            )
            conn.commit()
        finally:
            conn.close()

    def get_sensor_history(self, machine_id: str, sensor_type: Optional[str] = None,
                           limit: int = 1000) -> List[Dict]:
        conn = self._get_connection()
        try:
            if sensor_type:
                cursor = conn.execute(
                    "SELECT * FROM SensorHistory WHERE machine_id = ? AND sensor_type = ? ORDER BY timestamp DESC LIMIT ?",
                    (machine_id, sensor_type, limit)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM SensorHistory WHERE machine_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (machine_id, limit)
                )
            results = []
            for row in cursor.fetchall():
                results.append({
                    "machine_id": row["machine_id"],
                    "timestamp": row["timestamp"],
                    "sensor_type": row["sensor_type"],
                    "sensor_value": row["sensor_value"],
                    "status": row["status"]
                })
            return results
        finally:
            conn.close()

    # ==================== SEEDING ====================

    def seed_machines(self, machines: List[MachineInfo]):
        """Seed the database with machines if the Machines table is empty."""
        if self.get_machine_count() > 0:
            return  # Already seeded
        for machine in machines:
            self.insert_machine(machine)

    def clear_all_data(self):
        """Clear all data from all tables (for testing)."""
        conn = self._get_connection()
        try:
            conn.executescript("""
                DELETE FROM SensorHistory;
                DELETE FROM MaintenanceLogs;
                DELETE FROM WorkOrders;
                DELETE FROM Alerts;
                DELETE FROM Machines;
            """)
            conn.commit()
        finally:
            conn.close()