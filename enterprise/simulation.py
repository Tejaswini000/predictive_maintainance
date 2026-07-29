""""
Enterprise Simulation Engine for Predictive Maintenance Platform

Generates realistic sensor data for multiple factories, production lines,
and machine types. Reuses the existing data_ingestion pattern.
Extends it with multi-machine, multi-sensor support.
All machine data is persisted in SQLite via the DatabaseManager.

REALISTIC TIMELINE:
- Historical events generated from purchase_date, spread across months/years
- New simulation events use distributed timestamps (not all at datetime.now())
- Every machine has independent history

ALERT -> WORK ORDER -> MAINTENANCE CHAIN:
- Sensor Reading -> ML Prediction -> Failure Cause -> Alert -> Work Order -> Maintenance
- Every maintenance record originates from a work order
- Every work order originates from an alert
- Never create maintenance without an originating alert

MACHINE-SPECIFIC FAILURES:
- Each machine type has unique failure causes
- Each failure cause maps to specific work order titles and maintenance actions

SINGLE SOURCE OF TRUTH:
- MachineInfo.status is the authoritative state
- All alerts, work orders, dashboard counts derived from machine state
- SynchronizationEngine ensures consistency
"""

import random
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
for path in (str(PACKAGE_DIR), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from models import (
    MachineType, MachineInfo, MachineStatus, SensorType,
    AlertSeverity, MACHINE_TYPE_SENSORS,
    get_machine_type_sensors, get_sensor_list
)
from database import DatabaseManager
from services import format_alert_reason, select_alert_event
from data_loader import get_machine_data, load_machines_from_excel, MACHINES_XLSX_PATH
from ml_model import get_predictor, predict_machine_status
import logging

logger = logging.getLogger(__name__)


# ==================== EQUIPMENT CONFIGURATION ====================

FAILURE_CAUSE_LIBRARY = {
    MachineType.REFRIGERATOR: [
        "Compressor overheating",
        "Low refrigerant pressure",
        "Door seal leakage",
        "Cooling efficiency reduced",
        "Evaporator icing",
    ],
    MachineType.WASHING_MACHINE: [
        "High drum vibration",
        "Bearing wear",
        "Motor current exceeded threshold",
        "Water pump degradation",
        "Drum speed instability detected",
    ],
    MachineType.AIR_CONDITIONER: [
        "Condenser overheating",
        "Low refrigerant pressure",
        "Compressor overload",
        "Fan motor failure",
        "Cooling efficiency reduced",
    ],
    MachineType.GENERATOR: [
        "Alternator overheating",
        "Fuel pressure fluctuation",
        "Voltage instability",
        "Engine vibration increased",
        "Load current exceeded safe range",
    ],
    MachineType.CAR_ENGINE: [
        "Low oil pressure",
        "Coolant overheating",
        "Spark plug degradation",
        "Timing belt wear",
        "Engine RPM instability detected",
    ],
}

# Machine-specific work order titles mapped to failure causes
WORK_ORDER_TITLE_LIBRARY = {
    "Compressor overheating": "Compressor Overhaul",
    "Low refrigerant pressure": "Refrigerant Leak Inspection",
    "Door seal leakage": "Door Seal Replacement",
    "Cooling efficiency reduced": "Cooling System Service",
    "Evaporator icing": "Evaporator Defrost & Inspection",
    "High drum vibration": "Bearing Inspection & Balancing",
    "Bearing wear": "Bearing Replacement",
    "Motor current exceeded threshold": "Motor Diagnostics",
    "Water pump degradation": "Water Pump Replacement",
    "Drum speed instability detected": "Drum Speed Calibration",
    "Condenser overheating": "Condenser Cleaning & Service",
    "Compressor overload": "Compressor Electrical Test",
    "Fan motor failure": "Fan Motor Replacement",
    "Alternator overheating": "Alternator Cooling Fan Inspection",
    "Fuel pressure fluctuation": "Fuel Pump & Filter Service",
    "Voltage instability": "Voltage Regulator Replacement",
    "Engine vibration increased": "Engine Mount Inspection",
    "Load current exceeded safe range": "Load Bank Test",
    "Low oil pressure": "Oil Pump Inspection",
    "Coolant overheating": "Cooling System Flush",
    "Spark plug degradation": "Spark Plug Replacement",
    "Timing belt wear": "Timing Belt Replacement",
    "Engine RPM instability detected": "ECU Diagnostic & Tune-Up",
}

# Machine-specific maintenance actions mapped to failure causes
MAINTENANCE_ACTION_LIBRARY = {
    "Compressor overheating": "Compressor windings tested, thermal overload replaced, refrigerant topped up",
    "Low refrigerant pressure": "Refrigerant leak detected and sealed, system recharged",
    "Door seal leakage": "Door gasket replaced, seal integrity tested",
    "Cooling efficiency reduced": "Condenser coils cleaned, air flow restored, fans checked",
    "Evaporator icing": "Evaporator defrosted, drain line cleared, temperature sensor checked",
    "High drum vibration": "Drum bearings inspected, counterweights adjusted, drum rebalanced",
    "Bearing wear": "Worn bearings removed and replaced, shaft alignment verified",
    "Motor current exceeded threshold": "Motor windings tested, capacitor replaced, current draw normalized",
    "Water pump degradation": "Water pump disassembled, impeller cleared, seals replaced",
    "Drum speed instability detected": "Speed sensor recalibrated, control board firmware updated",
    "Condenser overheating": "Condenser fins cleaned, fan blades replaced, airflow restored",
    "Compressor overload": "Start capacitor replaced, contactor cleaned, compressor amp draw verified",
    "Fan motor failure": "Fan motor replaced, bearings lubricated, balance verified",
    "Alternator overheating": "Cooling fan replaced, alternator diode tested, heat sink cleaned",
    "Fuel pressure fluctuation": "Fuel filter replaced, fuel pump pressure tested, lines purged",
    "Voltage instability": "AVR module replaced, output voltage calibrated, load test passed",
    "Engine vibration increased": "Engine mounts torqued, flex coupling inspected, alignment checked",
    "Load current exceeded safe range": "Load bank connected, breaker panel inspected, current draw logged",
    "Low oil pressure": "Oil pump replaced, oil galleries flushed, pressure switch calibrated",
    "Coolant overheating": "Radiator flushed, thermostat replaced, water pump inspected",
    "Spark plug degradation": "Spark plugs replaced, ignition coils tested, compression checked",
    "Timing belt wear": "Timing belt and tensioner replaced, valve timing verified",
    "Engine RPM instability detected": "ECU reflashed, throttle body cleaned, idle air control valve replaced",
}

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


# ==================== REALISTIC MAINTENANCE COST CALCULATION ====================

def _get_realistic_maintenance_cost(cause: str, machine_category: str) -> float:
    """Calculate realistic maintenance cost based on machine category and cause.
    
    Simple inspection/cleaning → lower cost.
    Replacement or repair → higher cost.
    Similar causes have similar cost ranges.
    """
    cause_lower = cause.lower()
    cat = machine_category.lower() if machine_category else ""
    
    # Generator costs
    if "generator" in cat:
        if "oil" in cause_lower:
            return round(random.uniform(800, 1500), 2)
        if "electrical" in cause_lower or "voltage" in cause_lower:
            return round(random.uniform(500, 1200), 2)
        if "fuel" in cause_lower:
            return round(random.uniform(1000, 2000), 2)
        if "alternator" in cause_lower:
            return round(random.uniform(1200, 2500), 2)
        if "load" in cause_lower or "current" in cause_lower:
            return round(random.uniform(800, 1800), 2)
        if "engine" in cause_lower or "vibration" in cause_lower:
            return round(random.uniform(1000, 2000), 2)
        return round(random.uniform(600, 1500), 2)
    
    # Air Conditioner costs
    if "air conditioner" in cat or "ac" in cat:
        if "filter" in cause_lower:
            return round(random.uniform(300, 800), 2)
        if "refrigerant" in cause_lower:
            return round(random.uniform(800, 1500), 2)
        if "coil" in cause_lower or "condenser" in cause_lower:
            return round(random.uniform(700, 1500), 2)
        if "compressor" in cause_lower:
            return round(random.uniform(1500, 3000), 2)
        if "fan" in cause_lower or "motor" in cause_lower:
            return round(random.uniform(800, 1800), 2)
        if "cooling" in cause_lower:
            return round(random.uniform(600, 1400), 2)
        return round(random.uniform(400, 1200), 2)
    
    # Refrigerator costs
    if "refrigerator" in cat or "ref" in cat:
        if "condenser" in cause_lower:
            return round(random.uniform(400, 900), 2)
        if "thermostat" in cause_lower or "temperature" in cause_lower:
            return round(random.uniform(600, 1200), 2)
        if "cooling" in cause_lower or "evaporator" in cause_lower:
            return round(random.uniform(800, 1500), 2)
        if "compressor" in cause_lower:
            return round(random.uniform(1200, 2500), 2)
        if "door" in cause_lower or "seal" in cause_lower:
            return round(random.uniform(300, 800), 2)
        return round(random.uniform(400, 1000), 2)
    
    # Car Engine costs
    if "car engine" in cat or "engine" in cat:
        if "oil" in cause_lower:
            return round(random.uniform(1200, 2500), 2)
        if "air filter" in cause_lower or "filter" in cause_lower:
            return round(random.uniform(500, 1000), 2)
        if "spark" in cause_lower or "ignition" in cause_lower:
            return round(random.uniform(800, 1500), 2)
        if "tune" in cause_lower or "ecu" in cause_lower or "rpm" in cause_lower:
            return round(random.uniform(2000, 4000), 2)
        if "timing" in cause_lower or "belt" in cause_lower:
            return round(random.uniform(1500, 3000), 2)
        if "coolant" in cause_lower or "overheating" in cause_lower:
            return round(random.uniform(1000, 2500), 2)
        return round(random.uniform(600, 2000), 2)
    
    # Washing Machine costs
    if "washing" in cat or "wm" in cat:
        if "drum" in cause_lower:
            return round(random.uniform(400, 900), 2)
        if "belt" in cause_lower:
            return round(random.uniform(500, 1000), 2)
        if "pump" in cause_lower:
            return round(random.uniform(600, 1200), 2)
        if "bearing" in cause_lower:
            return round(random.uniform(700, 1500), 2)
        if "motor" in cause_lower:
            return round(random.uniform(800, 2000), 2)
        if "vibration" in cause_lower or "speed" in cause_lower:
            return round(random.uniform(400, 1000), 2)
        return round(random.uniform(400, 1000), 2)
    
    # Default fallback
    if "inspection" in cause_lower or "cleaning" in cause_lower or "check" in cause_lower:
        return round(random.uniform(300, 1000), 2)
    if "replacement" in cause_lower or "repair" in cause_lower or "overhaul" in cause_lower:
        return round(random.uniform(1000, 3000), 2)
    return round(random.uniform(500, 2000), 2)


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


# ==================== TIMESTAMP HELPERS ====================

def _random_timestamp_between(start: datetime, end: datetime) -> datetime:
    """Generate a random datetime uniformly distributed between start and end."""
    if start >= end:
        return end
    delta = (end - start).total_seconds()
    random_seconds = random.uniform(0, delta)
    return start + timedelta(seconds=random_seconds)


def _random_timestamp_around(base: datetime, max_hours_before: float = 1.0) -> datetime:
    """Generate a random timestamp within max_hours_before before base."""
    seconds = random.uniform(0, max_hours_before * 3600)
    return base - timedelta(seconds=seconds)


# ==================== PURCHASE DATE GENERATION ====================

def _generate_purchase_date(machine_id: str) -> datetime:
    """Generate a realistic purchase date between 2018 and 2024.
    
    Different machines get different dates. Uses hash of machine_id
    as seed for reproducibility, then adds random variation.
    """
    seed = hash(machine_id) % 10000
    rng = random.Random(seed)
    
    # Start: Jan 1, 2018
    start = datetime(2018, 1, 1)
    # End: Dec 31, 2024
    end = datetime(2024, 12, 31)
    
    # Spread purchases across the range
    total_days = (end - start).days
    # Use a combination of deterministic and random offset
    base_offset = (seed % 1000) / 1000.0 * total_days
    # Add some randomness for variation across runs
    random_offset = rng.uniform(-180, 180)  # +/- 6 months variation
    
    offset_days = max(0, min(total_days, int(base_offset + random_offset)))
    purchase_date = start + timedelta(days=offset_days)
    
    # Random time of day
    purchase_date = purchase_date.replace(
        hour=rng.randint(8, 17),
        minute=rng.randint(0, 59),
        second=rng.randint(0, 59),
        microsecond=0
    )
    
    return purchase_date


# ==================== FACTORY SIMULATION ====================

class EnterpriseSimulator:
    """
    Simulates an entire enterprise factory environment with multiple
    factories, production lines, and machines generating sensor data.

    REALISTIC TIMELINE:
    - Historical events generated from purchase_date
    - Events spread across months/years, not milliseconds apart
    - Each machine has independent history with distributed timestamps

    DATA CONSISTENCY:
    - Single source of truth: MachineInfo.status
    - All alerts, work orders, maintenance logs derived from machine state
    - SynchronizationEngine ensures cross-page consistency
    """

    _instance: Optional["EnterpriseSimulator"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.factories: Dict[str, Dict] = {}
        self.machines: Dict[str, MachineInfo] = {}
        self.work_orders: List = []  # Will use WorkOrder model
        self.maintenance_logs: List = []
        self._simulation_time: Optional[datetime] = None
        self._health_trends: Dict[str, float] = {}  # Track health changes
        self._failure_prob_trends: Dict[str, float] = {}
        self._history_seeded: bool = False
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
            self._refresh_static_machine_info(db)
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

        def _normalize_purchase_date(machine: MachineInfo) -> MachineInfo:
            """Ensure purchase date is between 2018 and 2024."""
            if not machine.purchase_date:
                machine.purchase_date = _generate_purchase_date(machine.machine_id)
            elif machine.purchase_date.year < 2018 or machine.purchase_date.year > 2024:
                machine.purchase_date = _generate_purchase_date(machine.machine_id)
            return machine

        # Build factory/category structure from Excel data
        for machine in excel_machines:
            # Ensure purchase date exists and is in 2018-2024 range
            machine = _normalize_purchase_date(machine)
            
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

    def _refresh_static_machine_info(self, db: DatabaseManager) -> None:
        """Keep Excel master data authoritative while preserving dynamic simulation state."""
        try:
            excel_machines = {
                machine.machine_id: machine
                for machine in load_machines_from_excel(MACHINES_XLSX_PATH)
            }
        except Exception as exc:
            print(f"Warning: Could not refresh static machine info from Excel: {exc}", file=sys.stderr)
            return

        for db_machine in db.get_all_machines():
            excel_machine = excel_machines.get(db_machine.machine_id)
            if not excel_machine:
                continue
            db.update_machine_static_info(excel_machine)
    
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
    
    # ==================== ML PREDICTION INTEGRATION ====================
    
    def _predict_with_ml(self, machine: MachineInfo, latest_readings: Optional[Dict] = None) -> Optional[Dict]:
        """
        Use the ML model to predict machine status from sensor readings.
        
        Generates live sensor readings for the machine, then passes them
        to the Random Forest model for prediction.
        
        Returns:
            Dict with predicted_status, confidence, probabilities, or None if ML fails.
        """
        try:
            # Generate current sensor readings
            readings = latest_readings if latest_readings is not None else self.get_latest_readings(machine.machine_id)
            if not readings:
                return None
            
            # Build sensor readings dict for ML model
            # Map simulation sensor names to ML feature names
            sensor_readings = {}
            sensor_name_mapping = {
                # Refrigerator sensors
                "temperature": "temperature",
                "door_status": None,  # Not used by ML
                "compressor_current": "current",
                "power_consumption": "power_consumption",
                # Washing Machine sensors
                "motor_rpm": "rpm",
                "water_level": None,
                "current": "current",
                "vibration": "vibration",
                # Air Conditioner sensors
                "room_temperature": "temperature",
                "compressor_temperature": "temperature",
                "fan_speed": "rpm",
                # Generator sensors
                "oil_pressure": "pressure",
                "voltage": "voltage",
                "rpm": "rpm",
                # Car Engine sensors
                "coolant_temperature": "temperature",
                "engine_rpm": "rpm",
                "fuel_level": None,
                "battery_voltage": "voltage",
            }
            
            for sensor_name, reading in readings.items():
                ml_name = sensor_name_mapping.get(sensor_name)
                if ml_name:
                    sensor_readings[ml_name] = reading["sensor_value"]
            
            # If no mapped values found, use raw sensor names directly
            if not sensor_readings:
                for sensor_name, reading in readings.items():
                    sensor_readings[sensor_name] = reading["sensor_value"]
            
            # Calculate days since last maintenance
            if machine.last_maintenance_date:
                days_since_maint = (datetime.now() - machine.last_maintenance_date).days
            else:
                days_since_maint = 365  # Assume long ago if never maintained
            
            # Get maintenance count from DB
            from database import DatabaseManager
            db = DatabaseManager()
            logs = db.get_maintenance_logs_by_machine(machine.machine_id)
            maintenance_count = len([log for log in logs if log.status == "Completed"])
            
            # Run ML prediction
            result = predict_machine_status(
                machine_type=machine.machine_type.value,
                sensor_readings=sensor_readings,
                operating_hours=machine.operating_hours,
                days_since_last_maintenance=days_since_maint,
                maintenance_count=maintenance_count
            )
            
            return result
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("ML prediction warning for %s: %s", machine.machine_id, e)
            return None
    
    def _status_to_condition(self, status: MachineStatus) -> str:
        if status == MachineStatus.CRITICAL:
            return "Critical"
        if status == MachineStatus.WARNING:
            return "Warning"
        return "Normal"

    def _build_cause(self, machine: MachineInfo, latest_readings: Optional[Dict], ml_result: Optional[Dict]) -> str:
        if not latest_readings:
            return "Sensor readings within normal range"

        sensor_values = {}
        for sensor_name, reading in latest_readings.items():
            if isinstance(reading, dict):
                sensor_values[sensor_name] = reading.get("sensor_value", 0)

        sensor_config = get_machine_type_sensors(machine.machine_type)
        ranked = []
        for sensor_name, value in sensor_values.items():
            config = sensor_config.get(sensor_name)
            if not config:
                continue
            span = max(config["max"] - config["min"], 1)
            deviation = abs(value - config["nominal"]) / span
            ranked.append((deviation, sensor_name))
        ranked.sort(reverse=True)

        top_sensor = ranked[0][1] if ranked else next(iter(sensor_values), "")
        status = str((ml_result or {}).get("predicted_status") or machine.status.value).upper()

        cause_candidates = list(FAILURE_CAUSE_LIBRARY.get(machine.machine_type, []))
        if not cause_candidates:
            return "Sensor readings within normal range"

        sensor_map = {
            MachineType.REFRIGERATOR: {
                "temperature": ["Cooling efficiency reduced", "Compressor overheating"],
                "current": ["Compressor overheating", "Low refrigerant pressure"],
                "pressure": ["Low refrigerant pressure", "Door seal leakage"],
            },
            MachineType.WASHING_MACHINE: {
                "vibration": ["High drum vibration", "Bearing wear"],
                "current": ["Motor current exceeded threshold", "Bearing wear"],
                "rpm": ["Drum speed instability detected", "Water pump degradation"],
                "temperature": ["Motor temperature high", "Temperature spike detected"],
            },
            MachineType.AIR_CONDITIONER: {
                "temperature": ["Condenser overheating", "Cooling efficiency reduced"],
                "current": ["Compressor overload", "Low refrigerant pressure"],
                "pressure": ["Low refrigerant pressure", "Fan motor failure"],
            },
            MachineType.GENERATOR: {
                "temperature": ["Alternator overheating", "Voltage instability"],
                "pressure": ["Fuel pressure fluctuation", "Engine vibration increased"],
                "voltage": ["Voltage instability", "Load current exceeded safe range"],
            },
            MachineType.CAR_ENGINE: {
                "temperature": ["Coolant overheating", "Low oil pressure"],
                "pressure": ["Low oil pressure", "Timing belt wear"],
                "rpm": ["Engine RPM instability detected", "Spark plug degradation"],
            },
        }

        preferred = list(sensor_map.get(machine.machine_type, {}).get(top_sensor, []))
        candidate_pool = []
        recent_causes = list(getattr(machine, "recent_failure_causes", []))
        for cause in preferred or cause_candidates:
            if cause not in recent_causes:
                candidate_pool.append(cause)
        if not candidate_pool:
            candidate_pool = [cause for cause in cause_candidates if cause not in recent_causes]
        if not candidate_pool:
            candidate_pool = cause_candidates

        if status in {"CRITICAL", "WARNING"} or ranked and ranked[0][0] >= 0.08:
            selected = random.choice(candidate_pool)
        else:
            selected = random.choice(candidate_pool[:2] or candidate_pool)

        history = recent_causes + [selected]
        if len(history) > 4:
            history = history[-4:]
        machine.recent_failure_causes = history
        return selected

    def _build_maintenance_recommendation(self, status: MachineStatus, health_score: float,
                                          failure_probability: float) -> str:
        if status == MachineStatus.CRITICAL or health_score < 60 or failure_probability >= 0.55:
            return "Immediate Inspection Required"
        if failure_probability >= 0.40:
            return "Within 48 Hours"
        if status == MachineStatus.WARNING or health_score < 85 or failure_probability >= 0.25:
            return "Within 7 Days"
        if failure_probability >= 0.12:
            return "Within 14 Days"
        return "Within 30 Days"

    def _update_machine_prediction_state(self, machine: MachineInfo, ml_result: Optional[Dict] = None,
                                         latest_readings: Optional[Dict] = None, persist: bool = True) -> MachineInfo:
        """Update the machine's condition, health, failure probability, cause, and recommendation from the latest prediction."""
        if ml_result is None:
            predicted_status = machine.status.value
            confidence = 0.5
            probabilities = {}
        else:
            predicted_status = ml_result.get("predicted_status") or machine.status.value
            confidence = ml_result.get("confidence", 0)
            probabilities = ml_result.get("probabilities", {})

        status_map = {
            "NORMAL": MachineStatus.NORMAL,
            "WARNING": MachineStatus.WARNING,
            "CRITICAL": MachineStatus.CRITICAL,
        }
        new_status = status_map.get(str(predicted_status).upper(), machine.status)

        if ml_result is not None:
            if new_status == MachineStatus.CRITICAL:
                target_health = random.uniform(20, 45)
            elif new_status == MachineStatus.WARNING:
                target_health = random.uniform(60, 84)
            else:
                target_health = random.uniform(85, 100)

            blended_health = round((machine.health_score * 0.4) + (target_health * 0.6), 1)
            if new_status == MachineStatus.CRITICAL:
                machine.health_score = max(10, min(59, blended_health))
            elif new_status == MachineStatus.WARNING:
                machine.health_score = max(60, min(84, blended_health))
            else:
                machine.health_score = max(85, min(100, blended_health))
        else:
            if machine.health_score < 60:
                new_status = MachineStatus.CRITICAL
            elif machine.health_score < 85:
                new_status = MachineStatus.WARNING
            else:
                new_status = MachineStatus.NORMAL

        machine.status = new_status
        machine.condition = self._status_to_condition(new_status)
        base_failure_probability = round(
            max(0.01, min(0.95, (100 - machine.health_score) / 100)),
            3,
        )
        if new_status == MachineStatus.CRITICAL:
            machine.failure_probability = max(0.41, base_failure_probability)
        elif new_status == MachineStatus.WARNING:
            machine.failure_probability = min(0.55, max(0.16, base_failure_probability))
        else:
            machine.failure_probability = min(0.15, base_failure_probability)
        machine.cause = self._build_cause(machine, latest_readings, ml_result)
        machine.maintenance_recommendation = self._build_maintenance_recommendation(
            new_status, machine.health_score, machine.failure_probability
        )
        machine.ml_prediction = {
            "predicted_status": new_status.value,
            "confidence": round(confidence, 4),
            "probabilities": probabilities,
            "model_used": (ml_result or {}).get("model_used"),
            "timestamp": datetime.now().isoformat(),
        }

        if persist:
            from database import DatabaseManager
            DatabaseManager().update_machine(machine)

        return machine

    def _apply_ml_status(self, machine: MachineInfo, ml_result: Dict, latest_readings: Optional[Dict] = None) -> None:
        """Backward-compatible wrapper that applies the shared prediction-state update."""
        self._update_machine_prediction_state(machine, ml_result=ml_result, latest_readings=latest_readings, persist=False)

    # ==================== HISTORICAL DATA GENERATION ====================

    def seed_history(self):
        """
        Generate realistic historical events for ALL machines from their purchase_date.
        
        For each machine:
        1. Determine purchase_date (defaults to 2018-2024 if not set)
        2. Generate 2-5 historical maintenance cycles:
           a. Months of healthy operation
           b. Warning alert appears (random date)
           c. Several days later, work order created
           d. Technician assigned
           e. Maintenance completed (machine returns to healthy)
        3. All timestamps are randomly distributed across the machine's lifetime
        4. The machine's last_maintenance_date is updated to the most recent maintenance
        5. Current health determines if machine needs an active alert/work order NOW
        
        This ensures NO bunched timestamps and realistic event distribution.
        """
        if self._history_seeded:
            return
        self._history_seeded = True

        from services import get_data_store, get_sync_engine
        data_store = get_data_store()
        sync_engine = get_sync_engine()
        db = DatabaseManager()

        now = datetime.now()

        for machine_id, machine in self.machines.items():
            # Check if history already exists for this machine
            existing_alerts = db.get_alerts_by_machine(machine_id)
            if existing_alerts:
                # History already generated for this machine
                continue

            # Determine purchase date (between 2018 and 2024)
            purchase_date = machine.purchase_date
            if not purchase_date:
                purchase_date = _generate_purchase_date(machine_id)
                machine.purchase_date = purchase_date

            # Ensure purchase_date is not in the future and within 2018-2024 range
            if purchase_date > now or purchase_date < datetime(2018, 1, 1) or purchase_date > datetime(2024, 12, 31):
                purchase_date = _generate_purchase_date(machine_id)
                machine.purchase_date = purchase_date

            # Calculate machine lifetime in days
            lifetime_days = max(365, (now - purchase_date).days)

            # Generate 2-5 historical maintenance cycles
            num_cycles = random.randint(2, min(5, lifetime_days // 180))
            
            # Distribute cycles evenly across the machine's lifetime
            for cycle_idx in range(num_cycles):
                # Start: healthy operation period
                cycle_start_offset = (cycle_idx * lifetime_days) // num_cycles
                cycle_start = purchase_date + timedelta(days=cycle_start_offset)
                
                # Ensure we leave room for the cycle
                max_cycle_end = purchase_date + timedelta(days=((cycle_idx + 1) * lifetime_days) // num_cycles)
                if max_cycle_end > now:
                    max_cycle_end = now - timedelta(days=1)
                
                # Random offset within this cycle window
                cycle_phase = random.uniform(0.1, 0.8)
                warning_date = cycle_start + timedelta(
                    days=(max_cycle_end - cycle_start).days * cycle_phase
                )
                
                # Alert timestamp: random hour/minute/second on this day
                warning_date = warning_date.replace(
                    hour=random.randint(6, 20),
                    minute=random.randint(0, 59),
                    second=random.randint(0, 59),
                    microsecond=random.randint(0, 999999)
                )
                
                # Ensure no future dates for history
                if warning_date > now:
                    warning_date = now - timedelta(days=random.randint(30, 90))
                
                # The failure cause for this cycle
                cause = self._select_failure_cause(machine)
                
                # Work Order created 1-5 days after alert
                wo_delay_days = random.randint(1, 5)
                wo_delay_hours = random.randint(0, 23)
                wo_date = warning_date + timedelta(days=wo_delay_days, hours=wo_delay_hours)
                if wo_date > now:
                    wo_date = now - timedelta(days=random.randint(1, 14))
                
                # Generate work order title from cause
                wo_title = self._get_work_order_title(cause, machine)
                
                # Create the work order
                technician = random.choice([
                    "Rajesh Kumar", "Priya Sharma", "Amit Singh", 
                    "Sneha Patel", "Vikram Reddy", "Anita Desai",
                    "Ravi Verma", "Neha Gupta", "Arun Nair", "Pooja Joshi"
                ])
                
                maintenance_action = self._get_maintenance_action(cause)
                
                # Health before maintenance
                severity = AlertSeverity.WARNING
                before_health = random.uniform(50, 74) if severity == AlertSeverity.WARNING else random.uniform(20, 49)
                
                recent_alert_events = list(getattr(machine, "recent_alert_events", []))
                reason, cause = select_alert_event(
                    machine.machine_type,
                    machine.machine_id,
                    preferred_cause=cause,
                    recent_events=recent_alert_events
                )
                recent_alert_events.append((reason.replace(f"{machine.machine_id}: ", ""), cause))
                machine.recent_alert_events = recent_alert_events[-4:]

                # Create alert record in database
                from models import Alert
                db_alert = Alert(
                    alert_id=f"HIST-ALT-{machine_id}-{cycle_idx}-{random.randint(1000, 9999)}",
                    machine_id=machine_id,
                    severity=severity,
                    reason=reason,
                    timestamp=warning_date,
                    recommended_action="Schedule maintenance",
                    status="Closed",
                    resolved_at=wo_date + timedelta(hours=random.uniform(2, 8))
                )
                db.insert_alert(db_alert)
                
                # Create work order linked to alert
                from models import WorkOrder, WorkOrderStatus
                wo = WorkOrder(
                    work_order_id=f"HIST-WO-{machine_id}-{cycle_idx}-{random.randint(1000, 9999)}",
                    machine_id=machine_id,
                    title=wo_title,
                    description=f"Historical maintenance: {cause}",
                    status=WorkOrderStatus.COMPLETED,
                    priority="Medium",
                    assigned_technician=technician,
                    created_date=wo_date,
                    scheduled_date=wo_date.date(),
                    due_date=wo_date.date(),
                    completed_date=wo_date + timedelta(hours=random.uniform(2, 6)),
                    estimated_hours=random.uniform(2, 6),
                    actual_hours=random.uniform(1.5, 5),
                    created_by="AI System",
                    alert_id=db_alert.alert_id,
                    machine_name=machine.name,
                    category=machine.machine_category,
                    current_health_score=before_health,
                    current_status="Warning",
                    maintenance_type="Corrective",
                    issue_description=cause,
                    ai_recommendation=f"Recommended action: {maintenance_action}"
                )
                db.insert_work_order(wo)
                
                # Maintenance completed 2-12 hours after work order
                maint_delay_hours = random.uniform(2, 12)
                maint_date = wo_date + timedelta(hours=maint_delay_hours)
                if maint_date > now:
                    maint_date = now - timedelta(hours=random.uniform(1, 12))
                
                # Health after maintenance (improved)
                after_health = min(100.0, before_health + random.uniform(15, 40))
                
                cost = _get_realistic_maintenance_cost(cause, machine.machine_category)
                duration = round(random.uniform(1, 6), 1)
                downtime = round(random.uniform(0.5, 3), 1)
                
                # Create maintenance log linked to work order AND alert
                from models import MaintenanceLog, MaintenanceType
                log = MaintenanceLog(
                    log_id=f"HIST-LOG-{machine_id}-{cycle_idx}-{random.randint(1000, 9999)}",
                    machine_id=machine_id,
                    maintenance_date=maint_date,
                    technician=technician,
                    maintenance_type=MaintenanceType.CORRECTIVE,
                    issue=cause,
                    action_taken=maintenance_action,
                    parts_replaced=self._get_parts_for_cause(cause),
                    cost=cost,
                    duration_hours=duration,
                    remarks=f"Maintenance completed. {cause} resolved. Machine returned to healthy operation.",
                    work_order_id=wo.work_order_id,
                    machine_name=machine.name,
                    category=machine.machine_category,
                    description=reason,
                    start_time=wo_date,
                    end_time=maint_date,
                    downtime_hours=downtime,
                    before_health=round(before_health, 1),
                    after_health=round(after_health, 1),
                    status="Completed",
                    created_date=wo_date
                )
                db.insert_maintenance_log(log)
                
                # Update machine's last_maintenance_date to most recent
                if machine.last_maintenance_date is None or maint_date > machine.last_maintenance_date:
                    machine.last_maintenance_date = maint_date
                    machine.health_score = after_health
                    
                    # Set next maintenance date 30-90 days after
                    machine.next_maintenance_date = maint_date + timedelta(days=random.randint(30, 90))
            
            # After history generation, set machine to current state
            if machine.last_maintenance_date:
                days_since_maint = (now - machine.last_maintenance_date).days
                if days_since_maint > 90:
                    # Machine likely degrading again
                    machine.health_score = random.uniform(65, 85)
                elif days_since_maint > 45:
                    machine.health_score = random.uniform(75, 92)
                else:
                    machine.health_score = random.uniform(85, 100)
            else:
                machine.health_score = random.uniform(85, 100)
            
            # Recalculate status from health
            if machine.health_score < 60:
                machine.status = MachineStatus.CRITICAL
            elif machine.health_score < 85:
                machine.status = MachineStatus.WARNING
            else:
                machine.status = MachineStatus.NORMAL
            
            machine.failure_probability = round(max(0.01, (100 - machine.health_score) / 100 * 0.85), 3)
            machine.condition = self._status_to_condition(machine.status)
            
            # Set operating hours based on purchase date
            machine.operating_hours = random.uniform(
                lifetime_days * 4,  # Conservative: 4h/day
                lifetime_days * 12  # Aggressive: 12h/day
            )
            
            # Ensure next_maintenance_date is after last_maintenance_date
            if machine.last_maintenance_date and machine.next_maintenance_date:
                if machine.next_maintenance_date <= machine.last_maintenance_date:
                    machine.next_maintenance_date = machine.last_maintenance_date + timedelta(days=random.randint(30, 90))
            
            db.update_machine(machine)
        
        # Now synchronize one more time to ensure current state is consistent
        sync_engine.synchronize_all()
        
        self._history_seeded = True

    def _select_failure_cause(self, machine: MachineInfo) -> str:
        """Select a failure cause appropriate for the machine type, avoiding repeats."""
        candidates = list(FAILURE_CAUSE_LIBRARY.get(machine.machine_type, []))
        if not candidates:
            return "Performance drift"
        
        recent = list(getattr(machine, "recent_failure_causes", []))
        # Filter out recently used causes
        available = [c for c in candidates if c not in recent]
        if not available:
            available = candidates
        
        selected = random.choice(available)
        # Track this cause
        history = recent + [selected]
        if len(history) > 4:
            history = history[-4:]
        machine.recent_failure_causes = history
        
        return selected

    def _get_work_order_title(self, cause: str, machine: MachineInfo) -> str:
        """Get machine-specific work order title for a failure cause."""
        # Try exact match first
        if cause in WORK_ORDER_TITLE_LIBRARY:
            return f"{WORK_ORDER_TITLE_LIBRARY[cause]}: {machine.name}"
        
        # Fall back to keyword matching
        cause_lower = cause.lower()
        for key, title in WORK_ORDER_TITLE_LIBRARY.items():
            if key.lower() in cause_lower:
                return f"{title}: {machine.name}"
        
        # Default fallback per machine type
        defaults = {
            MachineType.REFRIGERATOR: "Refrigeration System Service",
            MachineType.WASHING_MACHINE: "Washing Mechanism Inspection",
            MachineType.AIR_CONDITIONER: "HVAC System Diagnostics",
            MachineType.GENERATOR: "Generator System Check",
            MachineType.CAR_ENGINE: "Engine System Diagnostics",
        }
        return f"{defaults.get(machine.machine_type, 'Equipment Service')}: {machine.name}"

    def _get_maintenance_action(self, cause: str) -> str:
        """Get machine-specific maintenance action for a failure cause."""
        if cause in MAINTENANCE_ACTION_LIBRARY:
            return MAINTENANCE_ACTION_LIBRARY[cause]
        
        cause_lower = cause.lower()
        for key, action in MAINTENANCE_ACTION_LIBRARY.items():
            if key.lower() in cause_lower:
                return action
        
        return "System inspection and preventive maintenance completed"

    def _get_parts_for_cause(self, cause: str) -> list:
        """Get realistic parts list for a failure cause."""
        cause_lower = cause.lower()
        if "bearing" in cause_lower or "drum" in cause_lower:
            return ["Bearing Kit", "Sealant"]
        if "refrigerant" in cause_lower or "cooling" in cause_lower or "condenser" in cause_lower:
            return ["Condenser Coil", "Refrigerant R134a", "Filter"]
        if "evaporator" in cause_lower:
            return ["Evaporator Coil", "Defrost Thermostat"]
        if "alternator" in cause_lower or "voltage" in cause_lower:
            return ["Voltage Regulator", "Rectifier Diode"]
        if "fuel" in cause_lower:
            return ["Fuel Filter", "Fuel Pump Gasket"]
        if "oil" in cause_lower:
            return ["Oil Filter", "Oil Pump Seal", "Gasket Set"]
        if "coolant" in cause_lower:
            return ["Thermostat", "Coolant Hose", "Gasket"]
        if "timing" in cause_lower or "spark" in cause_lower:
            return ["Timing Belt Kit", "Spark Plug Set"]
        if "pump" in cause_lower or "motor" in cause_lower or "fan" in cause_lower:
            return ["Motor Bearing", "Fan Blade", "Capacitor"]
        if "compressor" in cause_lower:
            return ["Compressor", "Start Relay", "Overload Protector"]
        return ["General Maintenance Kit", "Lubricant"]

    # ==================== HEALTH SIMULATION ====================
    
    def simulate_health_degradation(self):
        """Simulate a completely new monitoring cycle for all machines.
        
        Every call produces a visibly new system state with REALISTIC TIMESTAMPS
        distributed across the machine's history, not all at the same millisecond.
        
        For each machine:
        1. Applies realistic state transitions
        2. Updates health_score, failure_probability
        3. ML prediction refines the state
        4. SynchronizationEngine ensures consistent alerts, work orders, logs
        
        SINGLE SOURCE OF TRUTH: machine.status is the authoritative state.
        All derived data (alerts, work orders, logs) is synchronized.
        """
        from services import get_data_store, get_sync_engine
        data_store = get_data_store()
        sync_engine = get_sync_engine()
        db = DatabaseManager()

        for machine_id, machine in self.machines.items():
            current_health = machine.health_score
            current_status = machine.status
            
            # ---- Step 1: Compute drift from state transitions ----
            if current_status == MachineStatus.NORMAL:
                roll = random.random()
                if roll < 0.60:
                    drift = random.uniform(-4.0, 3.0)
                else:
                    drift = random.uniform(-25.0, -10.0)
                    
            elif current_status == MachineStatus.WARNING:
                roll = random.random()
                if roll < 0.25:
                    drift = random.uniform(15.0, 35.0)
                elif roll < 0.70:
                    drift = random.uniform(-12.0, 8.0)
                else:
                    drift = random.uniform(-30.0, -15.0)
                    
            else:  # CRITICAL
                roll = random.random()
                if roll < 0.40:
                    drift = random.uniform(15.0, 30.0)
                elif roll < 0.70:
                    drift = random.uniform(35.0, 55.0)
                else:
                    drift = random.uniform(-15.0, -3.0)

            # ---- Step 2: Apply drift to health_score ----
            machine.health_score = round(current_health + drift, 1)
            machine.health_score = max(5, min(100, machine.health_score))
            
            # ---- Step 3: Update failure probability ----
            machine.failure_probability = round(
                max(0.01, min(0.95, (100 - machine.health_score) / 100 * 0.85)), 3
            )
            
            # ---- Step 4: Update status based on new health score ----
            if machine.health_score < 60:
                machine.status = MachineStatus.CRITICAL
            elif machine.health_score < 85:
                machine.status = MachineStatus.WARNING
            else:
                machine.status = MachineStatus.NORMAL
            
            # ---- Step 5: Apply ML prediction ----
            latest_readings = self.get_latest_readings(machine.machine_id)
            ml_result = self._predict_with_ml(machine, latest_readings=latest_readings)
            self._apply_ml_status(machine, ml_result, latest_readings=latest_readings)
            
            # ---- Step 6: Update operating hours ----
            machine.operating_hours += random.uniform(0.8, 2.0)
            
            # ---- Step 8: Ensure failure_probability ranges ----
            if machine.status == MachineStatus.CRITICAL:
                machine.failure_probability = max(0.41, machine.failure_probability)
            elif machine.status == MachineStatus.WARNING:
                machine.failure_probability = min(0.55, max(0.16, machine.failure_probability))
            else:
                machine.failure_probability = min(0.15, machine.failure_probability)

            # ---- Step 9: Synchronize all derived data (alerts, work orders, logs) ----
            sync_engine.synchronize_machine(machine)

            # ---- Step 10: Override next_maintenance_date AFTER sync (sync may change it) ----
            # Set to 2-3 months from today for consistent planning
            machine.next_maintenance_date = datetime.now() + timedelta(days=random.randint(60, 90))
            db.update_machine(machine)

            # ---- Step 11: Track prediction history ----
            ml_info = {}
            if machine.ml_prediction:
                ml_info = {
                    "ml_predicted_status": machine.ml_prediction.get("predicted_status"),
                    "ml_confidence": machine.ml_prediction.get("confidence"),
                    "ml_probabilities": machine.ml_prediction.get("probabilities"),
                }
            
            data_store.prediction_history[machine.machine_id] = data_store.prediction_history.get(machine.machine_id, []) + [{
                "timestamp": datetime.now().isoformat(),
                "health_score": machine.health_score,
                "predicted_failure": machine.failure_probability,
                "status": machine.status.value,
                **ml_info
            }]

    # ==================== MAINTENANCE CONDITION HISTORY ====================
    
    def generate_maintenance_condition_history(self, machine: MachineInfo) -> List[Dict]:
        """Generate realistic maintenance condition history for a machine.
        
        Returns a list of dicts with 'date' and 'condition' keys.
        Last entry always represents today's machine condition.
        Previous entries are randomly generated between purchase_date and today.
        """
        now = datetime.now()
        purchase_date = machine.purchase_date or _generate_purchase_date(machine.machine_id)
        
        history = []
        
        # Generate 3-6 random historical entries
        num_entries = random.randint(3, 6)
        
        # Distribute entries between purchase_date and now
        total_days = max(1, (now - purchase_date).days)
        
        # Create realistic condition progression
        conditions = ["NORMAL", "WARNING", "CRITICAL", "NORMAL", "WARNING", "NORMAL"]
        
        for i in range(num_entries):
            # Spread entries across the machine's lifetime
            offset_ratio = (i + 1) / (num_entries + 1)
            entry_date = purchase_date + timedelta(days=int(total_days * offset_ratio))
            
            # Add some randomness to the date
            entry_date += timedelta(days=random.randint(-15, 15))
            
            # Ensure date is not in the future or before purchase
            if entry_date > now:
                entry_date = now - timedelta(days=random.randint(1, 30))
            if entry_date < purchase_date:
                entry_date = purchase_date + timedelta(days=random.randint(30, 60))
            
            # Pick a condition from the cycle
            condition = conditions[i % len(conditions)]
            
            history.append({
                "date": entry_date.strftime("%Y-%m-%d"),
                "condition": condition
            })
        
        # Add today's condition as the last entry (must match current status)
        current_status = machine.status.value  # NORMAL, WARNING, or CRITICAL
        history.append({
            "date": now.strftime("%Y-%m-%d"),
            "condition": current_status
        })
        
        return history

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
