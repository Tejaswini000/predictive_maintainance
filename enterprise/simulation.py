""""
Enterprise Simulation Engine for Predictive Maintenance Platform

Generates realistic sensor data for multiple factories, production lines,
and machine types. Reuses the existing data_ingestion pattern.
Extends it with multi-machine, multi-sensor support.
All machine data is persisted in SQLite via the DatabaseManager.
"""

import random
import math
import sys
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta

from models import (
    MachineType, MachineInfo, MachineStatus, SensorType,
    AlertSeverity, MACHINE_TYPE_SENSORS,
    get_machine_type_sensors, get_sensor_list
)
from database import DatabaseManager
from data_loader import get_machine_data, MACHINES_XLSX_PATH


# ==================== EQUIPMENT CONFIGURATION ====================

DEFAULT_MACHINE_CONFIG = [
    {"category_id": "REFRIGERATOR", "name": "Refrigerator", "machines": [
        {"id": "REF-001", "type": MachineType.REFRIGERATOR, "manufacturer": "Samsung", "model": "RFG-100"},
        {"id": "REF-002", "type": MachineType.REFRIGERATOR, "manufacturer": "LG", "model": "RFG-200"},
        {"id": "REF-003", "type": MachineType.REFRIGERATOR, "manufacturer": "Whirlpool", "model": "RFG-300"},
        {"id": "REF-004", "type": MachineType.REFRIGERATOR, "manufacturer": "Godrej", "model": "RFG-400"},
        {"id": "REF-005", "type": MachineType.REFRIGERATOR, "manufacturer": "Samsung", "model": "RFG-500"},
        {"id": "REF-006", "type": MachineType.REFRIGERATOR, "manufacturer": "LG", "model": "RFG-600"},
        {"id": "REF-007", "type": MachineType.REFRIGERATOR, "manufacturer": "Whirlpool", "model": "RFG-700"},
        {"id": "REF-008", "type": MachineType.REFRIGERATOR, "manufacturer": "Bosch", "model": "RFG-800"},
        {"id": "REF-009", "type": MachineType.REFRIGERATOR, "manufacturer": "Godrej", "model": "RFG-900"},
        {"id": "REF-010", "type": MachineType.REFRIGERATOR, "manufacturer": "Samsung", "model": "RFG-1000"},
    ]},
    {"category_id": "WASHING_MACHINE", "name": "Washing Machine", "machines": [
        {"id": "WM-001", "type": MachineType.WASHING_MACHINE, "manufacturer": "LG", "model": "WM-100"},
        {"id": "WM-002", "type": MachineType.WASHING_MACHINE, "manufacturer": "Samsung", "model": "WM-200"},
        {"id": "WM-003", "type": MachineType.WASHING_MACHINE, "manufacturer": "Bosch", "model": "WM-300"},
        {"id": "WM-004", "type": MachineType.WASHING_MACHINE, "manufacturer": "Whirlpool", "model": "WM-400"},
        {"id": "WM-005", "type": MachineType.WASHING_MACHINE, "manufacturer": "Godrej", "model": "WM-500"},
        {"id": "WM-006", "type": MachineType.WASHING_MACHINE, "manufacturer": "LG", "model": "WM-600"},
        {"id": "WM-007", "type": MachineType.WASHING_MACHINE, "manufacturer": "Samsung", "model": "WM-700"},
        {"id": "WM-008", "type": MachineType.WASHING_MACHINE, "manufacturer": "Bosch", "model": "WM-800"},
        {"id": "WM-009", "type": MachineType.WASHING_MACHINE, "manufacturer": "Whirlpool", "model": "WM-900"},
        {"id": "WM-010", "type": MachineType.WASHING_MACHINE, "manufacturer": "Godrej", "model": "WM-1000"},
    ]},
    {"category_id": "AIR_CONDITIONER", "name": "Air Conditioner", "machines": [
        {"id": "AC-001", "type": MachineType.AIR_CONDITIONER, "manufacturer": "Daikin", "model": "AC-100"},
        {"id": "AC-002", "type": MachineType.AIR_CONDITIONER, "manufacturer": "Voltas", "model": "AC-200"},
        {"id": "AC-003", "type": MachineType.AIR_CONDITIONER, "manufacturer": "Blue Star", "model": "AC-300"},
        {"id": "AC-004", "type": MachineType.AIR_CONDITIONER, "manufacturer": "Hitachi", "model": "AC-400"},
        {"id": "AC-005", "type": MachineType.AIR_CONDITIONER, "manufacturer": "LG", "model": "AC-500"},
        {"id": "AC-006", "type": MachineType.AIR_CONDITIONER, "manufacturer": "Samsung", "model": "AC-600"},
        {"id": "AC-007", "type": MachineType.AIR_CONDITIONER, "manufacturer": "Daikin", "model": "AC-700"},
        {"id": "AC-008", "type": MachineType.AIR_CONDITIONER, "manufacturer": "Voltas", "model": "AC-800"},
        {"id": "AC-009", "type": MachineType.AIR_CONDITIONER, "manufacturer": "Hitachi", "model": "AC-900"},
        {"id": "AC-010", "type": MachineType.AIR_CONDITIONER, "manufacturer": "Blue Star", "model": "AC-1000"},
    ]},
    {"category_id": "GENERATOR", "name": "Generator", "machines": [
        {"id": "GEN-001", "type": MachineType.GENERATOR, "manufacturer": "Cummins", "model": "GEN-100"},
        {"id": "GEN-002", "type": MachineType.GENERATOR, "manufacturer": "Kirloskar", "model": "GEN-200"},
        {"id": "GEN-003", "type": MachineType.GENERATOR, "manufacturer": "Mahindra", "model": "GEN-300"},
        {"id": "GEN-004", "type": MachineType.GENERATOR, "manufacturer": "Tata Motors", "model": "GEN-400"},
        {"id": "GEN-005", "type": MachineType.GENERATOR, "manufacturer": "Cummins", "model": "GEN-500"},
        {"id": "GEN-006", "type": MachineType.GENERATOR, "manufacturer": "Kirloskar", "model": "GEN-600"},
        {"id": "GEN-007", "type": MachineType.GENERATOR, "manufacturer": "Mahindra", "model": "GEN-700"},
        {"id": "GEN-008", "type": MachineType.GENERATOR, "manufacturer": "Tata Motors", "model": "GEN-800"},
        {"id": "GEN-009", "type": MachineType.GENERATOR, "manufacturer": "Cummins", "model": "GEN-900"},
        {"id": "GEN-010", "type": MachineType.GENERATOR, "manufacturer": "Kirloskar", "model": "GEN-1000"},
    ]},
    {"category_id": "CAR_ENGINE", "name": "Car Engine", "machines": [
        {"id": "ENG-001", "type": MachineType.CAR_ENGINE, "manufacturer": "Honda", "model": "ENG-100"},
        {"id": "ENG-002", "type": MachineType.CAR_ENGINE, "manufacturer": "Hyundai", "model": "ENG-200"},
        {"id": "ENG-003", "type": MachineType.CAR_ENGINE, "manufacturer": "Toyota", "model": "ENG-300"},
        {"id": "ENG-004", "type": MachineType.CAR_ENGINE, "manufacturer": "Honda", "model": "ENG-400"},
        {"id": "ENG-005", "type": MachineType.CAR_ENGINE, "manufacturer": "Toyota", "model": "ENG-500"},
        {"id": "ENG-006", "type": MachineType.CAR_ENGINE, "manufacturer": "Hyundai", "model": "ENG-600"},
        {"id": "ENG-007", "type": MachineType.CAR_ENGINE, "manufacturer": "Mahindra", "model": "ENG-700"},
        {"id": "ENG-008", "type": MachineType.CAR_ENGINE, "manufacturer": "Tata Motors", "model": "ENG-800"},
        {"id": "ENG-009", "type": MachineType.CAR_ENGINE, "manufacturer": "Honda", "model": "ENG-900"},
        {"id": "ENG-010", "type": MachineType.CAR_ENGINE, "manufacturer": "Toyota", "model": "ENG-1000"},
    ]},
]


# ==================== MACHINE NAME GENERATION ====================

def generate_machine_name(machine_id: str, machine_type: MachineType) -> str:
    """Generate a human-readable machine name."""
    prefix = {
        MachineType.REFRIGERATOR: "Refrigerator Unit",
        MachineType.WASHING_MACHINE: "Washing Unit",
        MachineType.AIR_CONDITIONER: "AC Unit",
        MachineType.GENERATOR: "Generator Unit",
        MachineType.CAR_ENGINE: "Engine Unit",
    }
    return f"{prefix.get(machine_type, 'Equipment')} {machine_id}"


# ==================== FACTORY SIMULATION ====================

class EnterpriseSimulator:
    """
    Simulates an entire enterprise factory environment with multiple
    factories, production lines, and machines generating sensor data.
    """
    
    def __init__(self):
        self.factories: Dict[str, Dict] = {}
        self.machines: Dict[str, MachineInfo] = {}
        self.work_orders: List = []  # Will use WorkOrder model
        self.maintenance_logs: List = []
        self._simulation_time: Optional[datetime] = None
        self._health_trends: Dict[str, float] = {}  # Track health changes
        self._failure_prob_trends: Dict[str, float] = {}
        self._initialize_factories()
    
    def _initialize_factories(self):
        """Initialize the equipment-category inventory from the Excel file.
        
        Loads machine data from data/machines.xlsx.
        If the file is missing or unreadable, shows a friendly error.
        On first run (Machines table empty), seeds the database with Excel data.
        On subsequent runs, loads existing machine data from SQLite.
        """
        db = DatabaseManager()
        
        # Check if machines already exist in the database
        if db.get_machine_count() > 0:
            # Load existing machines from SQLite
            db_machines = db.get_all_machines()
            for machine in db_machines:
                self.machines[machine.machine_id] = machine
                self._health_trends[machine.machine_id] = machine.health_score
                self._failure_prob_trends[machine.machine_id] = machine.failure_probability
                
                # Rebuild factory structure
                factory_id = machine.factory_id
                if factory_id not in self.factories:
                    self.factories[factory_id] = {
                        "name": factory_id,
                        "location": "",
                        "lines": {}
                    }
                self.factories[factory_id]["lines"][machine.machine_id] = {
                    "name": machine.name,
                    "machines": [machine]
                }
            return

        # First run: load machines from the Excel file
        excel_machines = get_machine_data()
        
        if not excel_machines:
            # Excel file not found or empty - show user-friendly message
            error_msg = (
                "Machine master file not found or could not be read.\n\n"
                f"Expected location: {MACHINES_XLSX_PATH}\n\n"
                "Please place machines.xlsx inside the data folder and restart the application."
            )
            print(f"ERROR: {error_msg}", file=sys.stderr)
            return

        # Build factory/category structure from Excel data
        for machine in excel_machines:
            self.machines[machine.machine_id] = machine
            self._health_trends[machine.machine_id] = machine.health_score
            self._failure_prob_trends[machine.machine_id] = machine.failure_probability
            
            factory_id = machine.factory_id or "Uncategorized"
            
            if factory_id not in self.factories:
                self.factories[factory_id] = {
                    "name": factory_id,
                    "location": "",
                    "lines": {}
                }
            self.factories[factory_id]["lines"][machine.machine_id] = {
                "name": machine.name,
                "machines": [machine]
            }

        # Seed the database with the loaded machines
        db.seed_machines(list(self.machines.values()))
    
    def get_all_factories(self) -> Dict[str, Dict]:
        """Get all equipment categories as a compatibility view of the fleet."""
        result = {}
        for fid, fconfig in self.factories.items():
            result[fid] = {
                "factory_id": fid,
                "name": fconfig["name"],
                "location": fconfig.get("location", ""),
                "line_count": len(fconfig["lines"]),
                "machine_count": sum(len(l.get("machines", [])) for l in fconfig["lines"].values())
            }
        return result
    
    def get_factory_machines(self, factory_id: str) -> List[MachineInfo]:
        """Get all machines in a category."""
        return [m for m in self.machines.values() if m.factory_id == factory_id]
    
    def get_line_machines(self, factory_id: str, line_id: str) -> List[MachineInfo]:
        """Get all machines in a specific category (compatibility stub)."""
        return [m for m in self.machines.values() if m.factory_id == factory_id]
    
    def get_machine(self, machine_id: str) -> Optional[MachineInfo]:
        """Get a specific machine by ID."""
        return self.machines.get(machine_id)
    
    def get_machines_by_type(self, machine_type: MachineType) -> List[MachineInfo]:
        """Get all machines of a specific type."""
        return [m for m in self.machines.values() if m.machine_type == machine_type]
    
    def get_all_machines(self) -> List[MachineInfo]:
        """Get all machines across all factories."""
        return list(self.machines.values())
    
    # ==================== SENSOR DATA GENERATION ====================
    
    def _generate_sensor_value(self, machine: MachineInfo, sensor_name: str, 
                               current_time: datetime, is_anomaly: bool = False) -> Tuple[float, str]:
        """
        Generate a realistic sensor value for a machine.
        
        Returns:
            Tuple of (sensor_value, status)
        """
        sensor_config = get_machine_type_sensors(machine.machine_type)
        
        if sensor_name not in sensor_config:
            return 0.0, "normal"
        
        config = sensor_config[sensor_name]
        nominal = config["nominal"]
        min_val = config["min"]
        max_val = config["max"]
        
        # Health factor - unhealthy machines drift toward extremes
        health_factor = machine.health_score / 100.0
        
        # Time-based variation (simulate diurnal patterns)
        hour = current_time.hour
        time_factor = 1.0 + 0.05 * math.sin(hour * math.pi / 12)
        
        # Random noise
        noise_range = (max_val - min_val) * 0.03
        noise = random.gauss(0, noise_range / 3)
        
        if is_anomaly:
            # Anomaly: drift significantly from nominal
            drift_direction = random.choice([-1, 1])
            anomaly_magnitude = random.uniform(0.3, 0.7) * (max_val - min_val)
            value = nominal + drift_direction * anomaly_magnitude + noise
        else:
            # Normal value with small drift based on health
            drift = (1.0 - health_factor) * (max_val - nominal) * 0.3
            if random.random() < 0.5:
                drift = -drift * 0.5
            value = nominal * time_factor + drift + noise
        
        # Clamp to valid range
        value = max(min_val, min(max_val, value))
        value = round(value, 2)
        
        # Determine status
        range_width = max_val - min_val
        normalized_deviation = abs(value - nominal) / range_width
        
        if normalized_deviation > 0.6:
            status = "critical"
        elif normalized_deviation > 0.35:
            status = "warning"
        else:
            status = "normal"
        
        return value, status
    
    def generate_sensor_readings(self, machine_id: str, count: int = 1, 
                                  anomaly_chance: float = 0.1) -> Dict[str, List[Dict]]:
        """
        Generate multiple sensor readings for a machine.
        
        Returns:
            Dict mapping sensor names to lists of reading dicts
        """
        machine = self.machines.get(machine_id)
        if not machine:
            return {}
        
        if self._simulation_time is None:
            self._simulation_time = datetime.now()
        
        sensor_config = get_machine_type_sensors(machine.machine_type)
        result = {}
        
        for sensor_name in sensor_config:
            readings = []
            for i in range(count):
                timestamp = self._simulation_time - timedelta(seconds=(count - i) * 5)
                is_anomaly = random.random() < anomaly_chance
                value, status = self._generate_sensor_value(
                    machine, sensor_name, timestamp, is_anomaly
                )
                
                readings.append({
                    "machine_id": machine_id,
                    "timestamp": timestamp,
                    "sensor_type": sensor_name,
                    "sensor_value": value,
                    "status": status,
                    "unit": sensor_config[sensor_name]["unit"]
                })
            
            result[sensor_name] = readings
        
        # Update simulation time
        self._simulation_time += timedelta(seconds=5 * count)
        
        return result
    
    def generate_all_sensor_readings(self, count: int = 1, 
                                      anomaly_chance: float = 0.1) -> Dict[str, Dict[str, List[Dict]]]:
        """
        Generate sensor readings for ALL machines.
        
        Returns:
            Dict mapping machine_id -> {sensor_name -> [readings]}
        """
        all_data = {}
        for machine_id in self.machines:
            all_data[machine_id] = self.generate_sensor_readings(
                machine_id, count, anomaly_chance
            )
        return all_data
    
    def get_latest_readings(self, machine_id: str) -> Dict[str, Dict]:
        """
        Get the latest reading for each sensor of a machine.
        
        Returns:
            Dict mapping sensor_name -> {value, status, unit, timestamp}
        """
        readings = self.generate_sensor_readings(machine_id, count=1)
        latest = {}
        for sensor_name, sensor_readings in readings.items():
            if sensor_readings:
                latest[sensor_name] = sensor_readings[0]
        return latest
    
    def generate_historical_data(self, machine_id: str, hours: int = 24, 
                                  readings_per_hour: int = 12) -> Dict[str, List[Dict]]:
        """
        Generate historical sensor data for a machine.
        
        Args:
            machine_id: Machine identifier
            hours: Hours of historical data
            readings_per_hour: Readings per hour
            
        Returns:
            Dict mapping sensor_name -> [reading dicts]
        """
        total_readings = hours * readings_per_hour
        return self.generate_sensor_readings(machine_id, count=total_readings)
    
    # ==================== HEALTH SIMULATION ====================
    
    def simulate_health_degradation(self):
        """Simulate a completely new monitoring cycle for all machines.
        
        Every call produces a visibly new system state. For each machine:
        
        1. Applies realistic state transitions based on current status:
           NORMAL   → NORMAL (60%) | WARNING (40%)
           WARNING  → NORMAL (25%) | WARNING (45%) | CRITICAL (30%)
           CRITICAL → WARNING (40%) | NORMAL (after maintenance, 30%) | CRITICAL (30%)
        
        2. Recalculates Health Score, Failure Probability, and Status.
        
        3. All derived data (alerts, work orders, maintenance logs) is
           synchronized via the SynchronizationEngine.
        
        Single source of truth: machine.status is the authoritative state.
        """
        from services import get_data_store, get_sync_engine
        data_store = get_data_store()
        sync_engine = get_sync_engine()
        db = DatabaseManager()

        for machine_id, machine in self.machines.items():
            current_health = machine.health_score
            current_status = machine.status
            
            # ---- Apply realistic state transitions ----
            if current_status == MachineStatus.NORMAL:
                # NORMAL → NORMAL (60%) | WARNING (40%)
                roll = random.random()
                if roll < 0.60:
                    # Stay NORMAL: small random drift
                    drift = random.uniform(-4.0, 3.0)
                else:
                    # Transition to WARNING: significant drop
                    drift = random.uniform(-25.0, -10.0)
                    
            elif current_status == MachineStatus.WARNING:
                # WARNING → NORMAL (25%) | WARNING (45%) | CRITICAL (30%)
                roll = random.random()
                if roll < 0.25:
                    # Recovered to NORMAL: big improvement
                    drift = random.uniform(15.0, 35.0)
                elif roll < 0.70:
                    # Stay WARNING: moderate drift either direction
                    drift = random.uniform(-12.0, 8.0)
                else:
                    # Transition to CRITICAL: steep drop
                    drift = random.uniform(-30.0, -15.0)
                    
            else:  # CRITICAL
                # CRITICAL → WARNING (40%) | NORMAL (after maintenance, 30%) | CRITICAL (30%)
                roll = random.random()
                if roll < 0.40:
                    # Improved to WARNING: moderate improvement
                    drift = random.uniform(15.0, 30.0)
                elif roll < 0.70:
                    # Full recovery to NORMAL (maintenance completed)
                    drift = random.uniform(35.0, 55.0)
                else:
                    # Stay CRITICAL: continue degrading
                    drift = random.uniform(-15.0, -3.0)

            new_health = current_health + drift
            new_health = max(5, min(100, round(new_health, 1)))
            
            machine.health_score = new_health
            
            # ---- Recalculate failure probability based on new health ----
            base_failure = (100 - machine.health_score) / 100.0
            jitter = random.uniform(0.85, 1.15)
            machine.failure_probability = round(
                max(0.01, min(0.95, base_failure * jitter * 0.85)), 3
            )

            # ---- Update operating hours ----
            machine.operating_hours += random.uniform(0.8, 2.0)
            
            # ---- Schedule next maintenance for healthy machines ----
            if machine.health_score >= 85 and random.random() < 0.3:
                machine.next_maintenance_date = datetime.now() + timedelta(days=random.randint(7, 30))
            elif machine.health_score < 40 and random.random() < 0.4:
                # Critical machines get urgent maintenance scheduled
                machine.next_maintenance_date = datetime.now() + timedelta(hours=random.randint(2, 12))

            # ---- Synchronize all derived data (alerts, work orders, logs) ----
            sync_engine.synchronize_machine(machine)

            # ---- Track prediction history ----
            data_store.prediction_history[machine.machine_id] = data_store.prediction_history.get(machine.machine_id, []) + [{
                "timestamp": datetime.now().isoformat(),
                "health_score": machine.health_score,
                "predicted_failure": machine.failure_probability,
                "status": machine.status.value
            }]

    def get_stats(self) -> Dict[str, Any]:
        """Get overall simulation statistics from the single source of truth: machine.status.
        
        All counts (warning_count, critical_count, healthy_count) are computed
        from machine.status directly, NOT from alert counts.
        open_alerts is computed separately for informational purposes.
        """
        from services import get_data_store
        data_store = get_data_store()
        
        all_machines = self.get_all_machines()
        
        if not all_machines:
            return {}
        
        status_counts = {}
        type_counts = {}
        total_health = 0
        critical_count = 0
        warning_count = 0
        healthy_count = 0
        
        for m in all_machines:
            status_counts[m.status.value] = status_counts.get(m.status.value, 0) + 1
            type_counts[m.machine_type.value] = type_counts.get(m.machine_type.value, 0) + 1
            total_health += m.health_score
            
            if m.status == MachineStatus.CRITICAL:
                critical_count += 1
            elif m.status == MachineStatus.WARNING:
                warning_count += 1
            elif m.status == MachineStatus.NORMAL:
                healthy_count += 1
        
        # Open alerts count (informational, NOT used for machine status counts)
        all_alerts = data_store.alert_service.get_all_alerts()
        open_alerts = [a for a in all_alerts if a.status == "Open"]
        
        return {
            "total_factories": len(self.factories),
            "total_categories": len(self.factories),
            "total_machines": len(all_machines),
            "average_health": round(total_health / len(all_machines), 1) if all_machines else 0,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "healthy_count": healthy_count,
            "open_alerts": len(open_alerts),
            "status_distribution": status_counts,
            "type_distribution": type_counts,
            "factory_counts": {
                fid: len(self.get_factory_machines(fid))
                for fid in self.factories
            },
            "category_counts": {
                fid: len(self.get_factory_machines(fid))
                for fid in self.factories
            }
        }


# Helper function for backward compatibility
def get_simulator() -> EnterpriseSimulator:
    """Get or create the enterprise simulator singleton."""
    return EnterpriseSimulator()