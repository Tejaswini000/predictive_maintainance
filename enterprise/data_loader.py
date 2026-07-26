"""
Machine Data Loader for Predictive Maintenance Platform

Loads machine master data from an Excel file (data/machines.xlsx)
and creates MachineInfo objects. Replaces the old random generation logic.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import traceback

import pandas as pd

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
for path in (str(PACKAGE_DIR), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from models import (
    MachineInfo, MachineType, MachineStatus, SensorType,
    MACHINE_TYPE_SENSORS, get_machine_type_sensors, get_sensor_list
)

# Path to the machine master file
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
MACHINES_XLSX_PATH = os.path.join(DATA_DIR, "machines.xlsx")


# ==================== CATEGORY TO MACHINETYPE MAPPING ====================

CATEGORY_TO_MACHINETYPE = {
    "Refrigerator": MachineType.REFRIGERATOR,
    "Washing Machine": MachineType.WASHING_MACHINE,
    "Air Conditioner": MachineType.AIR_CONDITIONER,
    "Generator": MachineType.GENERATOR,
    "Car Engine": MachineType.CAR_ENGINE,
    "Water Pump": MachineType.WATER_PUMP,
    "Elevator": MachineType.ELEVATOR,
    "Solar Inverter": MachineType.SOLAR_INVERTER,
    "Air Compressor": MachineType.AIR_COMPRESSOR,
    "Wind Turbine": MachineType.WIND_TURBINE,
    "UPS System": MachineType.UPS_SYSTEM,
    "Boiler": MachineType.BOILER,
    "Diesel Generator": MachineType.DIESEL_GENERATOR,
    "HVAC Unit": MachineType.HVAC_UNIT,
    "Industrial Fan": MachineType.INDUSTRIAL_FAN,
}

STATUS_MAPPING = {
    "Active": MachineStatus.NORMAL,
    "NORMAL": MachineStatus.NORMAL,
    "WARNING": MachineStatus.WARNING,
    "CRITICAL": MachineStatus.CRITICAL,
    "OFFLINE": MachineStatus.OFFLINE,
    "MAINTENANCE": MachineStatus.MAINTENANCE,
    "UNKNOWN": MachineStatus.UNKNOWN,
}


def _parse_date(value) -> Optional[datetime]:
    """Parse a date value from Excel into a datetime object."""
    if pd.isna(value) or value is None or value == "":
        return None
    try:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, datetime.min.time())
        # Try parsing string
        return datetime.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        try:
            return pd.to_datetime(value).to_pydatetime()
        except (ValueError, TypeError):
            return None


def _parse_float(value) -> float:
    """Parse a float value from Excel."""
    if pd.isna(value) or value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _parse_int(value) -> int:
    """Parse an integer value from Excel."""
    if pd.isna(value) or value is None or value == "":
        return 0
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def _parse_str(value) -> str:
    """Parse a string value from Excel."""
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def _get_machine_type(category: str) -> MachineType:
    """Map a category string to a MachineType enum."""
    return CATEGORY_TO_MACHINETYPE.get(category, MachineType.REFRIGERATOR)


def _get_status(status_str: str) -> MachineStatus:
    """Map a status string to a MachineStatus enum."""
    return STATUS_MAPPING.get(status_str.strip().upper(), MachineStatus.NORMAL)


def _get_supported_sensors(machine_type: MachineType) -> List[SensorType]:
    """Get the list of supported sensors for a machine type."""
    sensor_config = get_machine_type_sensors(machine_type)
    sensor_name_map = {
        "temperature": SensorType.TEMPERATURE,
        "pressure": SensorType.PRESSURE,
        "vibration": SensorType.VIBRATION,
        "noise_level": SensorType.NOISE_LEVEL,
        "rpm": SensorType.RPM,
        "humidity": SensorType.HUMIDITY,
        "oil_level": SensorType.OIL_LEVEL,
        "flow_rate": SensorType.FLOW_RATE,
        "power_consumption": SensorType.POWER_CONSUMPTION,
        "voltage": SensorType.VOLTAGE,
        "current": SensorType.CURRENT,
        "door_status": SensorType.DOOR_STATUS,
        "compressor_current": SensorType.COMPRESSOR_CURRENT,
        "motor_rpm": SensorType.MOTOR_RPM,
        "water_level": SensorType.WATER_LEVEL,
        "oil_pressure": SensorType.OIL_PRESSURE,
        "coolant_temperature": SensorType.COOLANT_TEMPERATURE,
        "engine_rpm": SensorType.ENGINE_RPM,
        "fuel_level": SensorType.FUEL_LEVEL,
        "battery_voltage": SensorType.BATTERY_VOLTAGE,
        "room_temperature": SensorType.ROOM_TEMPERATURE,
        "compressor_temperature": SensorType.COMPRESSOR_TEMPERATURE,
        "fan_speed": SensorType.FAN_SPEED,
        "motor_current": SensorType.MOTOR_CURRENT,
        "door_sensor": SensorType.DOOR_SENSOR,
        "speed": SensorType.SPEED,
        "power_output": SensorType.POWER_OUTPUT,
        "efficiency": SensorType.EFFICIENCY,
        "load": SensorType.LOAD,
    }
    supported = []
    for sensor_name in sensor_config:
        if sensor_name in sensor_name_map:
            supported.append(sensor_name_map[sensor_name])
    return supported


def load_machines_from_excel(filepath: str = MACHINES_XLSX_PATH) -> List[MachineInfo]:
    """
    Load machine data from the Excel file.
    
    Returns a list of MachineInfo objects created from the Excel rows.
    
    Raises:
        FileNotFoundError: If the Excel file does not exist.
        ValueError: If the Excel file cannot be read or parsed.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"Machine master file not found at: {filepath}\n"
            "Please place machines.xlsx inside the data folder."
        )
    
    try:
        df = pd.read_excel(filepath, sheet_name=0, engine='openpyxl')
    except Exception as e:
        raise ValueError(
            f"Could not read machine master file: {filepath}\n"
            f"Error: {str(e)}\n"
            "Please ensure the file is a valid Excel (.xlsx) file."
        )
    
    if df.empty:
        raise ValueError(
            f"Machine master file is empty: {filepath}\n"
            "Please ensure the file contains machine data."
        )
    
    # Normalize column names: strip whitespace and handle common variations
    df.columns = [str(col).strip() for col in df.columns]
    
    # Build a lookup for column name variations
    column_map = {}
    for col in df.columns:
        col_lower = col.lower().strip()
        if col_lower in ('machine id', 'machine_id', 'id', 'machineid'):
            column_map['machine_id'] = col
        elif col_lower in ('machine name', 'machine_name', 'name', 'machinename'):
            column_map['name'] = col
        elif col_lower in ('category', 'machine type', 'machine_type', 'type'):
            column_map['category'] = col
        elif col_lower in ('manufacturer', 'make', 'brand'):
            column_map['manufacturer'] = col
        elif col_lower in ('model number', 'model_number', 'model', 'model no'):
            column_map['model_number'] = col
        elif col_lower in ('serial number', 'serial_number', 'serial', 'serial no'):
            column_map['serial_number'] = col
        elif col_lower in ('color', 'colour'):
            column_map['color'] = col
        elif col_lower in ('purchase date', 'purchase_date', 'date purchased'):
            column_map['purchase_date'] = col
        elif col_lower in ('installation date', 'installation_date', 'install date', 'date installed'):
            column_map['installation_date'] = col
        elif col_lower in ('warranty expiry', 'warranty_expiry', 'warranty expiration', 'warranty'):
            column_map['warranty_expiry'] = col
        elif col_lower in ('supplier', 'vendor'):
            column_map['supplier'] = col
        elif col_lower in ('purchase cost', 'purchase_cost', 'cost', 'price', 'purchase cost (inr)'):
            column_map['purchase_cost'] = col
        elif col_lower in ('location', 'site', 'plant'):
            column_map['location'] = col
        elif col_lower in ('department', 'dept'):
            column_map['department'] = col
        elif col_lower in ('assigned technician', 'assigned_technician', 'technician', 'tech'):
            column_map['assigned_technician'] = col
        elif col_lower in ('capacity', 'capability'):
            column_map['capacity'] = col
        elif col_lower in ('power rating', 'power_rating', 'power', 'rating'):
            column_map['power_rating'] = col
        elif col_lower in ('current health', 'current_health', 'health', 'health score', 'health_score'):
            column_map['current_health'] = col
        elif col_lower in ('failure probability (%)', 'failure_probability', 'failure probability', 'failure %', 'failure_probability (%)'):
            column_map['failure_probability'] = col
        elif col_lower in ('status', 'machine status', 'machine_status'):
            column_map['status'] = col
    
    machines = []
    
    for idx, row in df.iterrows():
        try:
            machine_id = _parse_str(row.get(column_map.get('machine_id', 'Machine ID'), ''))
            if not machine_id:
                # Try to use the first column as ID if no match
                machine_id = _parse_str(row.iloc[0]) if len(row) > 0 else f"UNKNOWN-{idx+1:04d}"
            
            name = _parse_str(row.get(column_map.get('name', 'Machine Name'), ''))
            if not name:
                name = f"Machine {machine_id}"
            
            category = _parse_str(row.get(column_map.get('category', 'Category'), ''))
            machine_type = _get_machine_type(category)
            
            manufacturer = _parse_str(row.get(column_map.get('manufacturer', 'Manufacturer'), ''))
            model_number = _parse_str(row.get(column_map.get('model_number', 'Model Number'), ''))
            serial_number = _parse_str(row.get(column_map.get('serial_number', 'Serial Number'), ''))
            color = _parse_str(row.get(column_map.get('color', 'Color'), ''))
            
            purchase_date = _parse_date(row.get(column_map.get('purchase_date', 'Purchase Date')))
            installation_date = _parse_date(row.get(column_map.get('installation_date', 'Installation Date')))
            warranty_expiry = _parse_date(row.get(column_map.get('warranty_expiry', 'Warranty Expiry')))
            
            supplier = _parse_str(row.get(column_map.get('supplier', 'Supplier'), ''))
            purchase_cost = _parse_float(row.get(column_map.get('purchase_cost', 'Purchase Cost')))
            
            location = _parse_str(row.get(column_map.get('location', 'Location'), ''))
            department = _parse_str(row.get(column_map.get('department', 'Department'), ''))
            assigned_technician = _parse_str(row.get(column_map.get('assigned_technician', 'Assigned Technician'), ''))
            
            capacity = _parse_str(row.get(column_map.get('capacity', 'Capacity'), ''))
            power_rating = _parse_str(row.get(column_map.get('power_rating', 'Power Rating'), ''))
            
            current_health = _parse_float(row.get(column_map.get('current_health', 'Current Health'), 100.0))
            failure_probability = _parse_float(row.get(column_map.get('failure_probability', 'Failure Probability (%)'), 0.0))
            
            status_str = _parse_str(row.get(column_map.get('status', 'Status'), 'NORMAL'))
            status = _get_status(status_str)
            
            # Get supported sensors based on machine type
            supported_sensors = _get_supported_sensors(machine_type)
            
            # Use installation_date if available, otherwise use purchase_date
            effective_install_date = installation_date or purchase_date or datetime.now()
            
            machine = MachineInfo(
                machine_id=machine_id,
                name=name,
                machine_type=machine_type,
                production_line="",
                factory_id=category,
                manufacturer=manufacturer,
                model_number=model_number,
                installation_date=effective_install_date,
                operating_hours=0.0,
                status=status,
                health_score=current_health,
                failure_probability=failure_probability / 100.0 if failure_probability > 1 else failure_probability,
                last_maintenance_date=None,
                next_maintenance_date=None,
                supported_sensors=supported_sensors,
                # Extended fields
                serial_number=serial_number,
                color=color,
                purchase_date=purchase_date,
                warranty_expiry=warranty_expiry,
                supplier=supplier,
                purchase_cost=purchase_cost,
                location=location,
                department=department,
                assigned_technician=assigned_technician,
                capacity=capacity,
                power_rating=power_rating,
            )
            
            machines.append(machine)
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Could not parse row %d (Machine ID: %s): %s", idx+2, machine_id, e)
            continue
            continue
    
    if not machines:
        raise ValueError(
            "No valid machine records could be loaded from the Excel file.\n"
            "Please check the file format and ensure it contains valid machine data."
        )
    
    return machines


def get_machine_data() -> List[MachineInfo]:
    """
    Convenience function to load machine data with error handling.
    
    Returns a list of MachineInfo objects, or an empty list if loading fails.
    The error message is printed to stderr for the application to handle.
    """
    try:
        return load_machines_from_excel()
    except FileNotFoundError as e:
        import logging
        logging.getLogger(__name__).error("%s", e)
        return []
    except ValueError as e:
        import logging
        logging.getLogger(__name__).error("%s", e)
        return []
    except Exception as e:
        import logging, traceback
        logging.getLogger(__name__).exception("Unexpected error loading machine data: %s", e)
        traceback.print_exc()
        return []