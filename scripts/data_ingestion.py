"""
Data Ingestion Module for Predictive Maintenance System

This module handles loading and generating sensor data for multiple machines.
Supports both historical CSV datasets and simulated real-time data streams.
"""

import csv
import random
from typing import Dict, NamedTuple, Optional, List
from datetime import datetime, timedelta
from pathlib import Path


class SensorData(NamedTuple):
    """Represents sensor readings from a machine"""
    machine_id: str
    timestamp: datetime
    vibration: float
    temperature: float
    pressure: float
    noise_level: float


def generate_simulated_sensor_data(
    machine_id: str,
    num_readings: int = 10,
    anomaly_chance: float = 0.1
) -> List[SensorData]:
    """
    Generate simulated real-time sensor data for a machine.
    
    Args:
        machine_id: Unique machine identifier (e.g., 'M1', 'M2')
        num_readings: Number of sensor readings to generate
        anomaly_chance: Probability of generating anomalous readings (0.0-1.0)
    
    Returns:
        List of SensorData objects representing sensor readings
    """
    sensor_readings = []
    base_time = datetime.now()
    
    # Normal ranges for each sensor
    normal_ranges = {
        'vibration': (0.5, 3.0),
        'temperature': (60.0, 80.0),
        'pressure': (90.0, 110.0),
        'noise_level': (70.0, 85.0)
    }
    
    # Anomalous ranges (outside normal operation)
    anomaly_ranges = {
        'vibration': (4.0, 8.0),
        'temperature': (85.0, 120.0),
        'pressure': (115.0, 150.0),
        'noise_level': (90.0, 110.0)
    }
    
    for i in range(num_readings):
        timestamp = base_time - timedelta(minutes=num_readings - i)
        
        # Decide if this reading should be anomalous
        is_anomaly = random.random() < anomaly_chance
        
        if is_anomaly:
            ranges = anomaly_ranges
        else:
            ranges = normal_ranges
        
        # Generate sensor values within appropriate ranges
        vibration = random.uniform(*ranges['vibration'])
        temperature = random.uniform(*ranges['temperature'])
        pressure = random.uniform(*ranges['pressure'])
        noise_level = random.uniform(*ranges['noise_level'])
        
        sensor_readings.append(
            SensorData(
                machine_id=machine_id,
                timestamp=timestamp,
                vibration=round(vibration, 2),
                temperature=round(temperature, 2),
                pressure=round(pressure, 2),
                noise_level=round(noise_level, 2)
            )
        )
    
    return sensor_readings


def load_csv_dataset(csv_path: str) -> Dict[str, List[SensorData]]:
    """
    Load historical sensor data from a CSV file.
    
    Expected CSV columns: machine_id, timestamp, vibration, temperature, pressure, noise_level
    
    Args:
        csv_path: Path to the CSV file
    
    Returns:
        Dictionary with machine_id as key and list of SensorData as value
    
    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    data_by_machine = {}
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            if reader.fieldnames is None:
                raise ValueError("CSV file is empty or has no headers")
            
            required_fields = {'machine_id', 'timestamp', 'vibration', 'temperature', 'pressure', 'noise_level'}
            if not required_fields.issubset(set(reader.fieldnames)):
                raise ValueError(f"CSV missing required fields. Expected: {required_fields}")
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    machine_id = row['machine_id'].strip()
                    timestamp = datetime.fromisoformat(row['timestamp'].strip())
                    
                    sensor_data = SensorData(
                        machine_id=machine_id,
                        timestamp=timestamp,
                        vibration=float(row['vibration']),
                        temperature=float(row['temperature']),
                        pressure=float(row['pressure']),
                        noise_level=float(row['noise_level'])
                    )
                    
                    if machine_id not in data_by_machine:
                        data_by_machine[machine_id] = []
                    
                    data_by_machine[machine_id].append(sensor_data)
                
                except (ValueError, KeyError) as e:
                    raise ValueError(f"Invalid data in CSV row {row_num}: {str(e)}")
    
    except FileNotFoundError:
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    return data_by_machine


def generate_machine_data(
    machine_ids: Optional[List[str]] = None,
    data_source: str = "simulated",
    csv_path: Optional[str] = None,
    num_readings: int = 10
) -> Dict[str, List[SensorData]]:
    """
    Main function to generate or load sensor data for multiple machines.
    
    Args:
        machine_ids: List of machine identifiers (default: ['M1', 'M2', 'M3'])
        data_source: 'simulated' for real-time simulated data or 'csv' to load from file
        csv_path: Path to CSV file (required if data_source='csv')
        num_readings: Number of readings to generate per machine (for simulated data)
    
    Returns:
        Dictionary with machine_id as key and list of SensorData as value
        Format: {
            "M1": [SensorData(...), SensorData(...), ...],
            "M2": [SensorData(...), SensorData(...), ...],
            ...
        }
    
    Raises:
        ValueError: If invalid data_source or missing required parameters
        FileNotFoundError: If CSV file not found
    
    Example:
        >>> data = generate_machine_data(machine_ids=['M1', 'M2'])
        >>> print(data['M1'][0])
        SensorData(machine_id='M1', timestamp=..., vibration=2.5, ...)
    """
    if data_source not in ['simulated', 'csv']:
        raise ValueError("data_source must be 'simulated' or 'csv'")
    
    if machine_ids is None:
        machine_ids = ['M1', 'M2', 'M3']
    
    machine_data = {}
    
    if data_source == "simulated":
        # Generate simulated real-time data for each machine
        for machine_id in machine_ids:
            machine_data[machine_id] = generate_simulated_sensor_data(
                machine_id=machine_id,
                num_readings=num_readings
            )
    
    elif data_source == "csv":
        if csv_path is None:
            raise ValueError("csv_path is required when data_source='csv'")
        
        # Load historical data from CSV
        machine_data = load_csv_dataset(csv_path)
        
        # Filter to only requested machines if specified
        if machine_ids:
            machine_data = {
                mid: data for mid, data in machine_data.items()
                if mid in machine_ids
            }
    
    return machine_data


def create_sample_csv(output_path: str = "sample_sensor_data.csv", num_records: int = 100) -> None:
    """
    Create a sample CSV file with sensor data for testing and demonstration.
    
    Args:
        output_path: Path where the CSV file will be saved
        num_records: Number of records to generate
    """
    machine_ids = ['M1', 'M2', 'M3']
    base_time = datetime.now() - timedelta(days=30)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['machine_id', 'timestamp', 'vibration', 'temperature', 'pressure', 'noise_level']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        
        for i in range(num_records):
            machine_id = random.choice(machine_ids)
            timestamp = base_time + timedelta(minutes=i)
            
            # Generate realistic sensor values
            vibration = round(random.uniform(0.5, 3.5), 2)
            temperature = round(random.uniform(55.0, 90.0), 2)
            pressure = round(random.uniform(85.0, 120.0), 2)
            noise_level = round(random.uniform(65.0, 95.0), 2)
            
            writer.writerow({
                'machine_id': machine_id,
                'timestamp': timestamp.isoformat(),
                'vibration': vibration,
                'temperature': temperature,
                'pressure': pressure,
                'noise_level': noise_level
            })
    
    print(f"Sample CSV created: {output_path}")


# ==================== CSV UPLOAD & VALIDATION FOR DASHBOARD ====================

REQUIRED_COLUMNS = {'machine', 'time', 'temperature', 'vibration', 'pressure'}
ALTERNATIVE_COLUMNS = {
    'machine': ['machine_id', 'machine'],
    'time': ['timestamp', 'time', 'datetime'],
    'temperature': ['temperature', 'temp'],
    'vibration': ['vibration', 'vib'],
    'pressure': ['pressure', 'press']
}


def validate_csv_columns(columns: List[str]) -> tuple[bool, str, dict]:
    """
    Validate that CSV has required columns (with flexible naming).
    
    Args:
        columns: List of column names from CSV
        
    Returns:
        Tuple of (is_valid, error_message, column_mapping)
    """
    columns_lower = {col.lower().strip(): col for col in columns}
    
    # Try to map required columns to actual CSV columns
    column_mapping = {}
    missing_columns = []
    
    for required, alternatives in ALTERNATIVE_COLUMNS.items():
        found = False
        for alt in alternatives:
            if alt in columns_lower:
                column_mapping[required] = columns_lower[alt]
                found = True
                break
        if not found:
            missing_columns.append(required)
    
    if missing_columns:
        return False, f"Missing required columns: {', '.join(missing_columns)}", {}
    
    return True, "", column_mapping


def load_csv_from_upload(uploaded_file) -> Dict[str, List[SensorData]]:
    """
    Load and validate sensor data from an uploaded CSV file.
    
    🔹 1. FIX CSV PARSING - Normalize column names and accept flexible names
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        Dictionary with machine_id as key and list of SensorData as value
        
    Raises:
        ValueError: If CSV format is invalid
    """
    import pandas as pd
    from collections import defaultdict
    from io import StringIO
    
    try:
        # Read CSV content
        uploaded_file.seek(0)  # Reset file pointer
        df = pd.read_csv(uploaded_file)
        
        # 🔹 2. Normalize column names (lowercase, strip spaces)
        df.columns = df.columns.str.lower().str.strip()
        
        # 🔹 3. Accept flexible column names
        # If "timestamp" exists → rename to "time"
        if 'timestamp' in df.columns and 'time' not in df.columns:
            df = df.rename(columns={'timestamp': 'time'})
        elif 'datetime' in df.columns and 'time' not in df.columns:
            df = df.rename(columns={'datetime': 'time'})
        
        # Map alternative column names
        column_renames = {}
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ['machine_id'] and 'machine' not in df.columns:
                column_renames[col] = 'machine'
            elif col_lower in ['temp'] and 'temperature' not in df.columns:
                column_renames[col] = 'temperature'
            elif col_lower in ['vib'] and 'vibration' not in df.columns:
                column_renames[col] = 'vibration'
            elif col_lower in ['press'] and 'pressure' not in df.columns:
                column_renames[col] = 'pressure'
        
        if column_renames:
            df = df.rename(columns=column_renames)
        
        # 🔹 4. Validate required columns
        required_cols = {'machine', 'time', 'temperature', 'vibration', 'pressure'}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")
        
        # 🔹 5. Convert 'time' column to datetime
        df['time'] = pd.to_datetime(df['time'], errors='coerce')
        if df['time'].isna().any():
            raise ValueError("Invalid timestamp format in CSV")
        
        # Convert sensor values to numeric
        for col in ['temperature', 'vibration', 'pressure']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if df[col].isna().any():
                raise ValueError(f"Invalid numeric value in {col} column")
        
        # Add noise_level if not present (default value)
        if 'noise_level' not in df.columns:
            df['noise_level'] = 70  # Default value
        
        # 🔹 6. Sort data by machine and time
        df = df.sort_values(['machine', 'time'])
        
        # 🔹 7. Group data correctly using defaultdict(list) - prevents overwrite
        machine_data = defaultdict(list)
        
        for _, row in df.iterrows():
            # Normalize machine_id (strip whitespace)
            machine_id = str(row['machine']).strip()
            
            sensor_data = SensorData(
                machine_id=machine_id,
                timestamp=row['time'],
                vibration=float(row['vibration']),
                temperature=float(row['temperature']),
                pressure=float(row['pressure']),
                noise_level=float(row.get('noise_level', 70))
            )
            
            # Append to list (defaultdict ensures list exists)
            machine_data[machine_id].append(sensor_data)
        
        # 🔹 9. Add debugging line
        print(list(machine_data.keys()))
        
        return dict(machine_data)
        
    except ValueError:
        raise  # Re-raise ValueError as-is for proper error handling
    except Exception as e:
        raise ValueError(f"Failed to parse CSV: {str(e)}")


if __name__ == "__main__":
    # Example usage
    print("=== Simulated Real-Time Data ===")
    simulated_data = generate_machine_data(
        machine_ids=['M1', 'M2', 'M3'],
        data_source='simulated',
        num_readings=5
    )
    
    for machine_id, sensor_readings in simulated_data.items():
        print(f"\n{machine_id}:")
        for reading in sensor_readings[-2:]:  # Print last 2 readings
            print(f"  {reading}")
    
    # Generate sample CSV
    print("\n=== Creating Sample CSV ===")
    create_sample_csv(num_records=50)
    
    # Load from CSV
    print("\n=== Loading from CSV ===")
    try:
        csv_data = generate_machine_data(
            data_source='csv',
            csv_path='sample_sensor_data.csv'
        )
        
        for machine_id, readings in csv_data.items():
            print(f"{machine_id}: {len(readings)} readings")
    except FileNotFoundError as e:
        print(f"Note: {e}")
