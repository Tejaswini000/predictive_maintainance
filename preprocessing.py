"""
Data Preprocessing Module for Predictive Maintenance System

Handles data cleaning, normalization, and outlier detection for machine sensor data.
Supports processing multiple machines with comprehensive validation and error handling.
"""

import statistics
from typing import Dict, List, NamedTuple, Optional, Tuple
from copy import deepcopy


class SensorData(NamedTuple):
    """Represents sensor readings from a machine"""
    machine_id: str
    timestamp: str
    vibration: float
    temperature: float
    pressure: float
    noise_level: float


def handle_missing_values(
    data_dict: Dict[str, List[SensorData]],
    strategy: str = 'mean'
) -> Dict[str, List[SensorData]]:
    """
    Handle missing values in sensor data by replacing with mean, median, or forward fill.
    
    Args:
        data_dict: Dictionary with machine_id as key and list of SensorData as value
        strategy: 'mean', 'median', or 'forward_fill'
    
    Returns:
        Dictionary with missing values handled
    """
    cleaned_data = deepcopy(data_dict)
    sensor_fields = ['vibration', 'temperature', 'pressure', 'noise_level']
    
    for machine_id, readings in cleaned_data.items():
        if not readings:
            continue
            
        # Calculate statistics for each sensor field (ignoring None/NaN-like values)
        field_values = {field: [] for field in sensor_fields}
        
        for reading in readings:
            for field in sensor_fields:
                value = getattr(reading, field)
                if value is not None and not (isinstance(value, float) and (value != value)):  # Check for NaN
                    field_values[field].append(value)
        
        # Calculate replacement values
        replacement_values = {}
        for field in sensor_fields:
            values = field_values[field]
            if values:
                if strategy == 'mean':
                    replacement_values[field] = statistics.mean(values)
                elif strategy == 'median':
                    replacement_values[field] = statistics.median(values)
            else:
                replacement_values[field] = 0.0
        
        # Apply strategy
        if strategy in ['mean', 'median']:
            updated_readings = []
            for reading in readings:
                reading_dict = reading._asdict()
                for field in sensor_fields:
                    if reading_dict[field] is None or (isinstance(reading_dict[field], float) and (reading_dict[field] != reading_dict[field])):
                        reading_dict[field] = replacement_values[field]
                updated_readings.append(SensorData(**reading_dict))
            cleaned_data[machine_id] = updated_readings
            
        elif strategy == 'forward_fill':
            updated_readings = []
            last_values = {field: replacement_values[field] for field in sensor_fields}
            
            for reading in readings:
                reading_dict = reading._asdict()
                for field in sensor_fields:
                    value = reading_dict[field]
                    if value is None or (isinstance(value, float) and (value != value)):
                        reading_dict[field] = last_values[field]
                    else:
                        last_values[field] = value
                updated_readings.append(SensorData(**reading_dict))
            cleaned_data[machine_id] = updated_readings
    
    return cleaned_data


def normalize_sensor_readings(
    data_dict: Dict[str, List[SensorData]],
    method: str = 'standardization'
) -> Tuple[Dict[str, List[SensorData]], Dict[str, Dict]]:
    """
    Normalize sensor readings using standardization or min-max scaling.
    
    Args:
        data_dict: Dictionary with machine_id as key and list of SensorData as value
        method: 'standardization' (z-score) or 'min_max' scaling
    
    Returns:
        Tuple of (normalized_data, normalization_params for reference/inverse transform)
    """
    normalized_data = deepcopy(data_dict)
    sensor_fields = ['vibration', 'temperature', 'pressure', 'noise_level']
    normalization_params = {}
    
    # Calculate global statistics across all machines
    all_values = {field: [] for field in sensor_fields}
    
    for readings in data_dict.values():
        for reading in readings:
            for field in sensor_fields:
                value = getattr(reading, field)
                if value is not None:
                    all_values[field].append(value)
    
    # Calculate normalization parameters
    if method == 'standardization':
        for field in sensor_fields:
            values = all_values[field]
            if values:
                mean_val = statistics.mean(values)
                stdev = statistics.stdev(values) if len(values) > 1 else 1.0
                normalization_params[field] = {'mean': mean_val, 'stdev': stdev}
            else:
                normalization_params[field] = {'mean': 0.0, 'stdev': 1.0}
    
    elif method == 'min_max':
        for field in sensor_fields:
            values = all_values[field]
            if values:
                min_val = min(values)
                max_val = max(values)
                normalization_params[field] = {'min': min_val, 'max': max_val}
            else:
                normalization_params[field] = {'min': 0.0, 'max': 1.0}
    
    # Apply normalization
    for machine_id, readings in normalized_data.items():
        updated_readings = []
        for reading in readings:
            reading_dict = reading._asdict()
            
            for field in sensor_fields:
                value = reading_dict[field]
                
                if method == 'standardization':
                    params = normalization_params[field]
                    mean_val = params['mean']
                    stdev = params['stdev']
                    if stdev > 0:
                        reading_dict[field] = (value - mean_val) / stdev
                    else:
                        reading_dict[field] = 0.0
                
                elif method == 'min_max':
                    params = normalization_params[field]
                    min_val = params['min']
                    max_val = params['max']
                    if max_val - min_val > 0:
                        reading_dict[field] = (value - min_val) / (max_val - min_val)
                    else:
                        reading_dict[field] = 0.0
            
            updated_readings.append(SensorData(**reading_dict))
        normalized_data[machine_id] = updated_readings
    
    return normalized_data, normalization_params


def remove_outliers(
    data_dict: Dict[str, List[SensorData]],
    method: str = 'iqr',
    threshold: float = 1.5
) -> Tuple[Dict[str, List[SensorData]], Dict[str, int]]:
    """
    Remove outliers using IQR (Interquartile Range) or Z-score method.
    
    Args:
        data_dict: Dictionary with machine_id as key and list of SensorData as value
        method: 'iqr' (default) or 'zscore'
        threshold: IQR multiplier (1.5) or Z-score threshold (3.0)
    
    Returns:
        Tuple of (cleaned_data, outlier_counts per machine)
    """
    cleaned_data = deepcopy(data_dict)
    sensor_fields = ['vibration', 'temperature', 'pressure', 'noise_level']
    outlier_counts = {}
    
    for machine_id, readings in cleaned_data.items():
        if len(readings) < 2:
            outlier_counts[machine_id] = 0
            continue
        
        # Collect all values per field
        field_values = {field: [] for field in sensor_fields}
        for reading in readings:
            for field in sensor_fields:
                value = getattr(reading, field)
                if value is not None:
                    field_values[field].append(value)
        
        # Calculate outlier bounds per field
        outlier_bounds = {}
        
        if method == 'iqr':
            for field in sensor_fields:
                values = sorted(field_values[field])
                n = len(values)
                
                if n < 2:
                    outlier_bounds[field] = (float('-inf'), float('inf'))
                    continue
                
                # Calculate Q1 and Q3
                q1_idx = n // 4
                q3_idx = (3 * n) // 4
                q1 = values[q1_idx]
                q3 = values[q3_idx]
                
                iqr = q3 - q1
                lower_bound = q1 - threshold * iqr
                upper_bound = q3 + threshold * iqr
                outlier_bounds[field] = (lower_bound, upper_bound)
        
        elif method == 'zscore':
            for field in sensor_fields:
                values = field_values[field]
                if len(values) > 1:
                    mean_val = statistics.mean(values)
                    stdev = statistics.stdev(values)
                    # Z-score bounds
                    lower_bound = mean_val - threshold * stdev
                    upper_bound = mean_val + threshold * stdev
                    outlier_bounds[field] = (lower_bound, upper_bound)
                else:
                    outlier_bounds[field] = (float('-inf'), float('inf'))
        
        # Filter outliers
        filtered_readings = []
        removed_count = 0
        
        for reading in readings:
            is_outlier = False
            for field in sensor_fields:
                value = getattr(reading, field)
                if value is not None:
                    lower, upper = outlier_bounds[field]
                    if value < lower or value > upper:
                        is_outlier = True
                        break
            
            if not is_outlier:
                filtered_readings.append(reading)
            else:
                removed_count += 1
        
        cleaned_data[machine_id] = filtered_readings
        outlier_counts[machine_id] = removed_count
    
    return cleaned_data, outlier_counts


def preprocess_all_machines(
    data_dict: Dict[str, List[SensorData]],
    handle_missing: bool = True,
    missing_strategy: str = 'mean',
    normalize: bool = True,
    normalization_method: str = 'standardization',
    remove_outliers_flag: bool = True,
    outlier_method: str = 'iqr',
    outlier_threshold: float = 1.5,
    verbose: bool = True
) -> Dict[str, List[SensorData]]:
    """
    Comprehensive preprocessing pipeline for machine sensor data.
    
    Applies missing value handling, normalization, and outlier removal in sequence.
    
    Args:
        data_dict: Dictionary with machine_id as key and list of SensorData as value
        handle_missing: Whether to handle missing values
        missing_strategy: 'mean', 'median', or 'forward_fill'
        normalize: Whether to normalize sensor readings
        normalization_method: 'standardization' or 'min_max'
        remove_outliers_flag: Whether to remove outliers
        outlier_method: 'iqr' or 'zscore'
        outlier_threshold: IQR multiplier (1.5) or Z-score threshold (3.0)
        verbose: Print processing statistics
    
    Returns:
        Dictionary with cleaned and preprocessed sensor data ready for ML/rules
    """
    if verbose:
        print("=" * 70)
        print("DATA PREPROCESSING PIPELINE")
        print("=" * 70)
        print(f"\nInput: {len(data_dict)} machine(s)")
        total_readings = sum(len(readings) for readings in data_dict.values())
        print(f"Total sensor readings: {total_readings}")
    
    processed_data = deepcopy(data_dict)
    
    # Step 1: Handle Missing Values
    if handle_missing:
        if verbose:
            print(f"\n[1/3] Handling missing values (strategy: {missing_strategy})...")
        processed_data = handle_missing_values(processed_data, strategy=missing_strategy)
        if verbose:
            print("      ✓ Missing values handled")
    
    # Step 2: Normalize Sensor Readings
    if normalize:
        if verbose:
            print(f"\n[2/3] Normalizing sensor readings (method: {normalization_method})...")
        processed_data, norm_params = normalize_sensor_readings(
            processed_data, 
            method=normalization_method
        )
        if verbose:
            print("      ✓ Sensor readings normalized")
            for field, params in norm_params.items():
                print(f"        - {field}: {params}")
    
    # Step 3: Remove Outliers
    if remove_outliers_flag:
        if verbose:
            print(f"\n[3/3] Removing outliers (method: {outlier_method}, threshold: {outlier_threshold})...")
        processed_data, outlier_counts = remove_outliers(
            processed_data,
            method=outlier_method,
            threshold=outlier_threshold
        )
        if verbose:
            print("      ✓ Outliers removed")
            for machine_id, count in outlier_counts.items():
                if count > 0:
                    print(f"        - {machine_id}: {count} outlier(s) removed")
    
    # Summary
    if verbose:
        print("\n" + "=" * 70)
        print("PREPROCESSING COMPLETE")
        print("=" * 70)
        final_readings = sum(len(readings) for readings in processed_data.values())
        print(f"Output: {len(processed_data)} machine(s) with {final_readings} total readings")
        print("Status: Data is now cleaned and ready for ML or rules-based analysis")
        print("=" * 70 + "\n")
    
    return processed_data
