"""
Enterprise Data Models for Predictive Maintenance Platform

Extends the existing SensorData with multi-factory, multi-machine support.
All models are backward-compatible with existing code.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date
from dataclasses import dataclass, field, asdict
from enum import Enum


# ==================== ENUMS ====================

class MachineType(str, Enum):
    REFRIGERATOR = "Refrigerator"
    WASHING_MACHINE = "Washing Machine"
    AIR_CONDITIONER = "Air Conditioner"
    GENERATOR = "Generator"
    CAR_ENGINE = "Car Engine"
    WATER_PUMP = "Water Pump"
    ELEVATOR = "Elevator"
    SOLAR_INVERTER = "Solar Inverter"
    AIR_COMPRESSOR = "Air Compressor"
    WIND_TURBINE = "Wind Turbine"
    UPS_SYSTEM = "UPS System"
    BOILER = "Boiler"
    DIESEL_GENERATOR = "Diesel Generator"
    HVAC_UNIT = "HVAC Unit"
    INDUSTRIAL_FAN = "Industrial Fan"

class MachineStatus(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"

class SensorType(str, Enum):
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    VOLTAGE = "voltage"
    CURRENT = "current"
    VIBRATION = "vibration"
    RPM = "rpm"
    HUMIDITY = "humidity"
    OIL_LEVEL = "oil_level"
    FLOW_RATE = "flow_rate"
    NOISE_LEVEL = "noise_level"
    POWER_CONSUMPTION = "power_consumption"
    LOAD = "load"
    DOOR_STATUS = "door_status"
    COMPRESSOR_CURRENT = "compressor_current"
    MOTOR_RPM = "motor_rpm"
    WATER_LEVEL = "water_level"
    OIL_PRESSURE = "oil_pressure"
    COOLANT_TEMPERATURE = "coolant_temperature"
    ENGINE_RPM = "engine_rpm"
    FUEL_LEVEL = "fuel_level"
    BATTERY_VOLTAGE = "battery_voltage"
    ROOM_TEMPERATURE = "room_temperature"
    COMPRESSOR_TEMPERATURE = "compressor_temperature"
    FAN_SPEED = "fan_speed"
    MOTOR_CURRENT = "motor_current"
    DOOR_SENSOR = "door_sensor"
    SPEED = "speed"
    POWER_OUTPUT = "power_output"
    EFFICIENCY = "efficiency"

class AlertSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"

class WorkOrderStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

class MaintenanceType(str, Enum):
    PREVENTIVE = "Preventive"
    CORRECTIVE = "Corrective"
    PREDICTIVE = "Predictive"
    EMERGENCY = "Emergency"
    INSPECTION = "Inspection"
    REPAIR = "Repair"
    REPLACEMENT = "Replacement"


# ==================== FACTORY & LINE MODELS ====================

@dataclass
class ProductionLine:
    """Represents a production line within a factory."""
    line_id: str
    name: str
    factory_id: str
    description: str = ""

@dataclass
class Factory:
    """Represents a manufacturing factory/plant."""
    factory_id: str
    name: str
    location: str = ""
    production_lines: Dict[str, ProductionLine] = field(default_factory=dict)

    def add_line(self, line: ProductionLine):
        self.production_lines[line.line_id] = line

    def get_line(self, line_id: str) -> Optional[ProductionLine]:
        return self.production_lines.get(line_id)


# ==================== MACHINE MODEL ====================

@dataclass
class MachineInfo:
    """Extended machine information for enterprise platform."""
    machine_id: str
    name: str
    machine_type: MachineType
    production_line: str = ""
    factory_id: str = ""
    manufacturer: str = "Default Corp"
    model_number: str = ""
    installation_date: datetime = field(default_factory=datetime.now)
    operating_hours: float = 0.0
    status: MachineStatus = MachineStatus.NORMAL
    health_score: float = 100.0
    failure_probability: float = 0.0
    last_maintenance_date: Optional[datetime] = None
    next_maintenance_date: Optional[datetime] = None
    supported_sensors: List[SensorType] = field(default_factory=list)
    # ML Prediction metadata (set dynamically by ML predictor)
    ml_prediction: Optional[Dict] = None
    condition: str = "Normal"
    cause: str = ""
    maintenance_recommendation: str = "Within 30 days"
    recent_failure_causes: List[str] = field(default_factory=list)
    # Extended fields from Excel master data
    serial_number: str = ""
    color: str = ""
    purchase_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    supplier: str = ""
    purchase_cost: float = 0.0
    location: str = ""
    department: str = ""
    assigned_technician: str = ""
    capacity: str = ""
    power_rating: str = ""

    @property
    def machine_category(self) -> str:
        return self.machine_type.value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "machine_id": self.machine_id,
            "name": self.name,
            "machine_type": self.machine_type.value,
            "production_line": self.production_line,
            "factory_id": self.factory_id,
            "manufacturer": self.manufacturer,
            "model_number": self.model_number,
            "installation_date": self.installation_date.isoformat() if self.installation_date else None,
            "operating_hours": self.operating_hours,
            "status": self.status.value,
            "health_score": self.health_score,
            "failure_probability": self.failure_probability,
            "last_maintenance_date": self.last_maintenance_date.isoformat() if self.last_maintenance_date else None,
            "next_maintenance_date": self.next_maintenance_date.isoformat() if self.next_maintenance_date else None,
            "supported_sensors": [s.value for s in self.supported_sensors],
            "condition": self.condition,
            "cause": self.cause,
            "maintenance_recommendation": self.maintenance_recommendation,
            "serial_number": self.serial_number,
            "color": self.color,
            "purchase_date": self.purchase_date.isoformat() if self.purchase_date else None,
            "warranty_expiry": self.warranty_expiry.isoformat() if self.warranty_expiry else None,
            "supplier": self.supplier,
            "purchase_cost": self.purchase_cost,
            "location": self.location,
            "department": self.department,
            "assigned_technician": self.assigned_technician,
            "capacity": self.capacity,
            "power_rating": self.power_rating,
        }


# ==================== SENSOR DATA ====================

@dataclass
class EnterpriseSensorData:
    """Extended sensor data with all supported sensor types."""
    machine_id: str
    timestamp: datetime
    sensor_type: SensorType
    sensor_value: float
    status: str = "normal"
    
    # Backward compatibility fields
    temperature: float = 0.0
    vibration: float = 0.0
    pressure: float = 0.0
    noise_level: float = 0.0


# ==================== ALERT MODEL ====================

@dataclass
class Alert:
    """Represents a system alert."""
    alert_id: str
    machine_id: str
    severity: AlertSeverity
    reason: str
    timestamp: datetime
    recommended_action: str
    status: str = "Open"  # Open, Acknowledged, Resolved
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "machine_id": self.machine_id,
            "severity": self.severity.value,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "recommended_action": self.recommended_action,
            "status": self.status
        }


# ==================== WORK ORDER MODEL ====================

@dataclass
class WorkOrder:
    """Represents a maintenance work order."""
    work_order_id: str
    machine_id: str
    title: str
    description: str
    status: WorkOrderStatus = WorkOrderStatus.OPEN
    priority: str = "Medium"  # Low, Medium, High, Critical
    assigned_technician: str = "Unassigned"
    created_date: datetime = field(default_factory=datetime.now)
    scheduled_date: Optional[date] = None
    due_date: Optional[date] = None
    completed_date: Optional[datetime] = None
    estimated_hours: float = 0.0
    actual_hours: float = 0.0
    parts_replaced: List[str] = field(default_factory=list)
    cost: float = 0.0
    remarks: str = ""
    created_by: str = "AI System"
    alert_id: Optional[str] = None
    machine_name: str = ""
    category: str = ""
    current_health_score: float = 0.0
    current_status: str = ""
    maintenance_type: str = ""
    issue_description: str = ""
    ai_recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_order_id": self.work_order_id,
            "machine_id": self.machine_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "assigned_technician": self.assigned_technician,
            "created_date": self.created_date.isoformat(),
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed_date": self.completed_date.isoformat() if self.completed_date else None,
            "estimated_hours": self.estimated_hours,
            "actual_hours": self.actual_hours,
            "parts_replaced": self.parts_replaced,
            "cost": self.cost,
            "remarks": self.remarks,
            "created_by": self.created_by,
            "alert_id": self.alert_id,
            "machine_name": self.machine_name,
            "category": self.category,
            "current_health_score": self.current_health_score,
            "current_status": self.current_status,
            "maintenance_type": self.maintenance_type,
            "issue_description": self.issue_description,
            "ai_recommendation": self.ai_recommendation
        }


# ==================== MAINTENANCE LOG MODEL ====================

@dataclass
class MaintenanceLog:
    """Represents a maintenance history record."""
    log_id: str
    machine_id: str
    maintenance_date: datetime
    technician: str
    maintenance_type: MaintenanceType
    issue: str
    action_taken: str
    parts_replaced: List[str] = field(default_factory=list)
    cost: float = 0.0
    duration_hours: float = 0.0
    remarks: str = ""
    work_order_id: Optional[str] = None
    machine_name: str = ""
    category: str = ""
    description: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    downtime_hours: float = 0.0
    before_health: float = 0.0
    after_health: float = 0.0
    status: str = "Completed"
    created_date: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_id": self.log_id,
            "machine_id": self.machine_id,
            "maintenance_date": self.maintenance_date.isoformat(),
            "technician": self.technician,
            "maintenance_type": self.maintenance_type.value,
            "issue": self.issue,
            "action_taken": self.action_taken,
            "parts_replaced": self.parts_replaced,
            "cost": self.cost,
            "duration_hours": self.duration_hours,
            "remarks": self.remarks,
            "work_order_id": self.work_order_id,
            "machine_name": self.machine_name,
            "category": self.category,
            "description": self.description,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "downtime_hours": self.downtime_hours,
            "before_health": self.before_health,
            "after_health": self.after_health,
            "status": self.status,
            "created_date": self.created_date.isoformat()
        }


# ==================== ANALYTICS MODEL ====================

@dataclass
class MachineAnalytics:
    """Analytics data for a machine over a period."""
    machine_id: str
    period_start: datetime
    period_end: datetime
    health_score: float = 100.0
    mtbf_hours: float = 0.0  # Mean Time Between Failures
    mttr_hours: float = 0.0  # Mean Time To Repair
    downtime_hours: float = 0.0
    availability_percent: float = 100.0
    utilization_percent: float = 0.0
    prediction_accuracy: float = 0.0
    maintenance_cost: float = 0.0
    failure_rate: float = 0.0
    total_predictions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==================== REPORT MODEL ====================

@dataclass
class Report:
    """Represents a generated report."""
    report_id: str
    report_type: str  # daily, weekly, monthly, machine, factory, maintenance, prediction
    title: str
    generated_at: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    generated_by: str = "AI System"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type,
            "title": self.title,
            "generated_at": self.generated_at.isoformat(),
            "data": self.data,
            "generated_by": self.generated_by
        }


# ==================== MACHINE TYPE SENSOR CONFIG ====================

# Define which sensors each machine type supports with nominal ranges
MACHINE_TYPE_SENSORS: Dict[MachineType, Dict[str, Dict]] = {
    MachineType.REFRIGERATOR: {
        "temperature": {"min": 2, "max": 12, "unit": "°C", "nominal": 5},
        "door_status": {"min": 0, "max": 1, "unit": "state", "nominal": 1},
        "compressor_current": {"min": 1.0, "max": 8.0, "unit": "A", "nominal": 3.5},
        "power_consumption": {"min": 0.2, "max": 2.5, "unit": "kW", "nominal": 0.9},
    },
    MachineType.WASHING_MACHINE: {
        "motor_rpm": {"min": 300, "max": 1800, "unit": "RPM", "nominal": 900},
        "water_level": {"min": 10, "max": 100, "unit": "%", "nominal": 70},
        "current": {"min": 2.0, "max": 15.0, "unit": "A", "nominal": 6.0},
        "vibration": {"min": 0.1, "max": 3.5, "unit": "mm/s", "nominal": 0.8},
    },
    MachineType.AIR_CONDITIONER: {
        "room_temperature": {"min": 18, "max": 32, "unit": "°C", "nominal": 24},
        "compressor_temperature": {"min": 35, "max": 85, "unit": "°C", "nominal": 55},
        "current": {"min": 2.0, "max": 20.0, "unit": "A", "nominal": 8.0},
        "fan_speed": {"min": 400, "max": 1800, "unit": "RPM", "nominal": 900},
    },
    MachineType.GENERATOR: {
        "oil_pressure": {"min": 20, "max": 80, "unit": "psi", "nominal": 45},
        "voltage": {"min": 210, "max": 250, "unit": "V", "nominal": 230},
        "current": {"min": 10, "max": 80, "unit": "A", "nominal": 35},
        "temperature": {"min": 45, "max": 95, "unit": "°C", "nominal": 70},
        "rpm": {"min": 1200, "max": 1800, "unit": "RPM", "nominal": 1500},
    },
    MachineType.CAR_ENGINE: {
        "coolant_temperature": {"min": 80, "max": 120, "unit": "°C", "nominal": 95},
        "engine_rpm": {"min": 600, "max": 6500, "unit": "RPM", "nominal": 2200},
        "oil_pressure": {"min": 20, "max": 80, "unit": "psi", "nominal": 45},
        "fuel_level": {"min": 5, "max": 100, "unit": "%", "nominal": 70},
        "battery_voltage": {"min": 11.5, "max": 14.8, "unit": "V", "nominal": 12.6},
    },
    MachineType.WATER_PUMP: {
        "pressure": {"min": 2, "max": 12, "unit": "bar", "nominal": 5},
        "temperature": {"min": 20, "max": 70, "unit": "°C", "nominal": 35},
        "current": {"min": 2.0, "max": 18.0, "unit": "A", "nominal": 7.0},
        "vibration": {"min": 0.2, "max": 3.0, "unit": "mm/s", "nominal": 1.0},
    },
    MachineType.ELEVATOR: {
        "motor_current": {"min": 5.0, "max": 30.0, "unit": "A", "nominal": 12.0},
        "door_sensor": {"min": 0, "max": 1, "unit": "state", "nominal": 1},
        "vibration": {"min": 0.1, "max": 2.8, "unit": "mm/s", "nominal": 0.7},
        "speed": {"min": 0.5, "max": 3.0, "unit": "m/s", "nominal": 1.5},
    },
    MachineType.SOLAR_INVERTER: {
        "voltage": {"min": 220, "max": 260, "unit": "V", "nominal": 240},
        "current": {"min": 2.0, "max": 18.0, "unit": "A", "nominal": 8.0},
        "power_output": {"min": 300, "max": 2200, "unit": "W", "nominal": 1200},
        "efficiency": {"min": 80, "max": 99, "unit": "%", "nominal": 94},
    },
    MachineType.AIR_COMPRESSOR: {
        "pressure": {"min": 5, "max": 15, "unit": "bar", "nominal": 8},
        "temperature": {"min": 30, "max": 80, "unit": "°C", "nominal": 50},
        "current": {"min": 5, "max": 25, "unit": "A", "nominal": 12},
        "vibration": {"min": 0.3, "max": 3.5, "unit": "mm/s", "nominal": 1.2},
    },
    MachineType.WIND_TURBINE: {
        "vibration": {"min": 0.2, "max": 4.0, "unit": "mm/s", "nominal": 1.1},
        "rpm": {"min": 10, "max": 180, "unit": "RPM", "nominal": 80},
        "voltage": {"min": 300, "max": 700, "unit": "V", "nominal": 500},
        "temperature": {"min": 20, "max": 80, "unit": "°C", "nominal": 40},
    },
    MachineType.UPS_SYSTEM: {
        "voltage": {"min": 210, "max": 250, "unit": "V", "nominal": 230},
        "current": {"min": 2.0, "max": 20.0, "unit": "A", "nominal": 8.0},
        "battery_voltage": {"min": 11.5, "max": 14.8, "unit": "V", "nominal": 12.6},
        "temperature": {"min": 20, "max": 45, "unit": "°C", "nominal": 30},
    },
    MachineType.BOILER: {
        "pressure": {"min": 5, "max": 25, "unit": "bar", "nominal": 12},
        "temperature": {"min": 80, "max": 180, "unit": "°C", "nominal": 120},
        "water_level": {"min": 20, "max": 100, "unit": "%", "nominal": 75},
    },
    MachineType.DIESEL_GENERATOR: {
        "oil_pressure": {"min": 20, "max": 80, "unit": "psi", "nominal": 45},
        "voltage": {"min": 210, "max": 250, "unit": "V", "nominal": 230},
        "current": {"min": 10, "max": 90, "unit": "A", "nominal": 40},
        "temperature": {"min": 45, "max": 95, "unit": "°C", "nominal": 70},
        "rpm": {"min": 1200, "max": 1800, "unit": "RPM", "nominal": 1500},
    },
    MachineType.HVAC_UNIT: {
        "room_temperature": {"min": 18, "max": 32, "unit": "°C", "nominal": 24},
        "current": {"min": 2.0, "max": 20.0, "unit": "A", "nominal": 8.0},
        "fan_speed": {"min": 400, "max": 1800, "unit": "RPM", "nominal": 900},
        "pressure": {"min": 1.5, "max": 8, "unit": "bar", "nominal": 3.5},
    },
    MachineType.INDUSTRIAL_FAN: {
        "vibration": {"min": 0.2, "max": 3.5, "unit": "mm/s", "nominal": 1.0},
        "current": {"min": 1.5, "max": 15.0, "unit": "A", "nominal": 5.0},
        "rpm": {"min": 300, "max": 1800, "unit": "RPM", "nominal": 900},
        "temperature": {"min": 25, "max": 75, "unit": "°C", "nominal": 40},
    },
}


def get_machine_type_sensors(machine_type: MachineType) -> Dict[str, Dict]:
    """Get sensor configurations for a machine type."""
    return MACHINE_TYPE_SENSORS.get(machine_type, MACHINE_TYPE_SENSORS[MachineType.REFRIGERATOR])


def get_sensor_list(machine_type: MachineType) -> List[str]:
    """Get list of sensor names for a machine type."""
    return list(get_machine_type_sensors(machine_type).keys())
