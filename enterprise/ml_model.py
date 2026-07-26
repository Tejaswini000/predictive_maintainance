"""
Machine Learning Prediction Engine for Predictive Maintenance Platform

Generates realistic historical datasets, trains a Random Forest Classifier,
and provides live predictions for machine status.

Key Features:
- 50K realistic historical records across all machine types
- Random Forest Classifier with machine type as a feature
- Prediction confidence and class probabilities
- Model persistence (save/load)
- Evaluation metrics (accuracy, precision, recall, F1, confusion matrix)
"""

import os
import json
import pickle
import warnings
import random
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
for path in (str(PACKAGE_DIR), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)
from sklearn.preprocessing import LabelEncoder

from models import MachineType, MachineStatus, MACHINE_TYPE_SENSORS

warnings.filterwarnings('ignore')

# ==================== CONSTANTS ====================

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "random_forest_model.pkl")
ENCODER_PATH = os.path.join(MODEL_DIR, "label_encoders.pkl")
FEATURES_PATH = os.path.join(MODEL_DIR, "feature_config.pkl")
DATASET_PATH = os.path.join(MODEL_DIR, "training_dataset.csv")

# Status labels
STATUS_LABELS = ["NORMAL", "WARNING", "CRITICAL"]
STATUS_MAP = {0: "NORMAL", 1: "WARNING", 2: "CRITICAL"}

# Machine types used in training (the 5 active types)
ACTIVE_TRAINING_TYPES = [
    MachineType.REFRIGERATOR,
    MachineType.WASHING_MACHINE,
    MachineType.AIR_CONDITIONER,
    MachineType.GENERATOR,
    MachineType.CAR_ENGINE,
]

# ==================== OPERATING RANGES PER MACHINE TYPE ====================
# Each machine type has its own realistic operating ranges for all sensors
# These are used to generate realistic training data

MACHINE_OPERATING_RANGES = {
    MachineType.REFRIGERATOR: {
        "temperature": {"normal": (3, 7), "warning": (7, 10), "critical": (10, 12)},
        "vibration": {"normal": (0.1, 0.5), "warning": (0.5, 1.2), "critical": (1.2, 2.5)},
        "pressure": {"normal": (1.5, 3.0), "warning": (3.0, 4.5), "critical": (4.5, 6.0)},
        "rpm": {"normal": (800, 1200), "warning": (1200, 1500), "critical": (1500, 1800)},
        "voltage": {"normal": (215, 240), "warning": (240, 250), "critical": (250, 260)},
        "current": {"normal": (1.5, 4.0), "warning": (4.0, 6.0), "critical": (6.0, 8.0)},
        "humidity": {"normal": (40, 60), "warning": (60, 75), "critical": (75, 90)},
        "ambient_temperature": {"normal": (20, 28), "warning": (28, 34), "critical": (34, 40)},
        "power_consumption": {"normal": (0.3, 1.2), "warning": (1.2, 1.8), "critical": (1.8, 2.5)},
        "operating_hours": {"normal": (100, 5000), "warning": (5000, 12000), "critical": (12000, 20000)},
    },
    MachineType.WASHING_MACHINE: {
        "temperature": {"normal": (20, 40), "warning": (40, 55), "critical": (55, 70)},
        "vibration": {"normal": (0.2, 0.8), "warning": (0.8, 2.0), "critical": (2.0, 3.5)},
        "pressure": {"normal": (1.0, 2.5), "warning": (2.5, 4.0), "critical": (4.0, 5.5)},
        "rpm": {"normal": (500, 1000), "warning": (1000, 1400), "critical": (1400, 1800)},
        "voltage": {"normal": (215, 240), "warning": (240, 250), "critical": (250, 260)},
        "current": {"normal": (3.0, 8.0), "warning": (8.0, 12.0), "critical": (12.0, 15.0)},
        "humidity": {"normal": (50, 70), "warning": (70, 85), "critical": (85, 95)},
        "ambient_temperature": {"normal": (20, 30), "warning": (30, 36), "critical": (36, 42)},
        "power_consumption": {"normal": (0.5, 1.5), "warning": (1.5, 2.2), "critical": (2.2, 3.0)},
        "operating_hours": {"normal": (100, 4000), "warning": (4000, 10000), "critical": (10000, 18000)},
    },
    MachineType.AIR_CONDITIONER: {
        "temperature": {"normal": (18, 26), "warning": (26, 30), "critical": (30, 35)},
        "vibration": {"normal": (0.1, 0.4), "warning": (0.4, 1.0), "critical": (1.0, 2.0)},
        "pressure": {"normal": (2.0, 4.0), "warning": (4.0, 6.0), "critical": (6.0, 8.0)},
        "rpm": {"normal": (600, 1000), "warning": (1000, 1400), "critical": (1400, 1800)},
        "voltage": {"normal": (215, 240), "warning": (240, 250), "critical": (250, 260)},
        "current": {"normal": (3.0, 10.0), "warning": (10.0, 15.0), "critical": (15.0, 20.0)},
        "humidity": {"normal": (40, 60), "warning": (60, 75), "critical": (75, 90)},
        "ambient_temperature": {"normal": (25, 35), "warning": (35, 40), "critical": (40, 45)},
        "power_consumption": {"normal": (0.8, 2.0), "warning": (2.0, 3.0), "critical": (3.0, 4.0)},
        "operating_hours": {"normal": (100, 5000), "warning": (5000, 12000), "critical": (12000, 20000)},
    },
    MachineType.GENERATOR: {
        "temperature": {"normal": (50, 75), "warning": (75, 88), "critical": (88, 100)},
        "vibration": {"normal": (0.2, 0.6), "warning": (0.6, 1.5), "critical": (1.5, 3.0)},
        "pressure": {"normal": (3.0, 5.0), "warning": (5.0, 6.5), "critical": (6.5, 8.0)},
        "rpm": {"normal": (1300, 1600), "warning": (1600, 1750), "critical": (1750, 1900)},
        "voltage": {"normal": (220, 240), "warning": (240, 250), "critical": (250, 260)},
        "current": {"normal": (15, 40), "warning": (40, 60), "critical": (60, 80)},
        "humidity": {"normal": (30, 50), "warning": (50, 65), "critical": (65, 80)},
        "ambient_temperature": {"normal": (25, 35), "warning": (35, 42), "critical": (42, 50)},
        "power_consumption": {"normal": (5.0, 15.0), "warning": (15.0, 25.0), "critical": (25.0, 35.0)},
        "operating_hours": {"normal": (100, 3000), "warning": (3000, 8000), "critical": (8000, 15000)},
    },
    MachineType.CAR_ENGINE: {
        "temperature": {"normal": (85, 100), "warning": (100, 112), "critical": (112, 125)},
        "vibration": {"normal": (0.3, 0.8), "warning": (0.8, 1.8), "critical": (1.8, 3.2)},
        "pressure": {"normal": (3.0, 5.5), "warning": (5.5, 7.0), "critical": (7.0, 8.5)},
        "rpm": {"normal": (800, 3000), "warning": (3000, 4500), "critical": (4500, 6500)},
        "voltage": {"normal": (12.0, 13.5), "warning": (13.5, 14.2), "critical": (14.2, 15.0)},
        "current": {"normal": (10, 30), "warning": (30, 50), "critical": (50, 70)},
        "humidity": {"normal": (30, 50), "warning": (50, 65), "critical": (65, 80)},
        "ambient_temperature": {"normal": (20, 35), "warning": (35, 42), "critical": (42, 50)},
        "power_consumption": {"normal": (2.0, 8.0), "warning": (8.0, 14.0), "critical": (14.0, 20.0)},
        "operating_hours": {"normal": (100, 3000), "warning": (3000, 8000), "critical": (8000, 15000)},
    },
}

# Feature columns used for training (in order)
FEATURE_COLUMNS = [
    "machine_type_encoded",
    "temperature", "vibration", "pressure", "rpm",
    "voltage", "current", "humidity", "ambient_temperature",
    "power_consumption", "operating_hours",
    "days_since_last_maintenance", "maintenance_count",
]

# ==================== DATASET GENERATION ====================


def _generate_sensor_value(ranges: Dict[str, Tuple[float, float]], status: str) -> float:
    """Generate a realistic sensor value for a given status level."""
    low, high = ranges.get(status, ranges["normal"])
    # Add realistic noise
    value = random.uniform(low, high)
    # Add small Gaussian noise
    noise = random.gauss(0, (high - low) * 0.05)
    return round(value + noise, 2)


def _simulate_degradation_cycle(
    machine_type: MachineType,
    machine_id: str,
    num_records: int,
    start_time: datetime,
    machine_index: int
) -> List[Dict]:
    """
    Simulate a realistic degradation-maintenance cycle for a machine.
    
    The cycle follows:
    Healthy → Small wear → Sensor values gradually increase → Warning → Critical → Maintenance → Healthy again
    
    Each machine gets a unique degradation profile based on its index.
    """
    ranges = MACHINE_OPERATING_RANGES.get(machine_type, MACHINE_OPERATING_RANGES[MachineType.REFRIGERATOR])
    records = []
    
    # Each machine has a unique "personality" based on its index
    # This creates realistic variation between machines of the same type
    personality_seed = hash(machine_id) % 1000
    rng = random.Random(personality_seed)
    
    # Machine-specific baseline offsets
    base_offset = {
        "temperature": rng.uniform(-2, 2),
        "vibration": rng.uniform(-0.1, 0.1),
        "pressure": rng.uniform(-0.3, 0.3),
        "rpm": rng.uniform(-50, 50),
        "voltage": rng.uniform(-2, 2),
        "current": rng.uniform(-1, 1),
        "humidity": rng.uniform(-3, 3),
        "ambient_temperature": rng.uniform(-2, 2),
        "power_consumption": rng.uniform(-0.2, 0.2),
    }
    
    # Simulate multiple degradation cycles
    cycle_length = rng.randint(80, 150)  # Records per cycle
    num_cycles = max(1, num_records // cycle_length)
    maintenance_count = 0
    days_since_maintenance = 0
    
    for cycle in range(num_cycles):
        # Each cycle: NORMAL → WARNING → CRITICAL → maintenance → NORMAL
        cycle_progress = 0
        
        # Phase 1: NORMAL (first 40-50% of cycle)
        normal_end = int(cycle_length * rng.uniform(0.40, 0.50))
        for i in range(normal_end):
            progress_ratio = i / normal_end  # 0 to 1
            # Gradual wear: values drift slightly from nominal
            wear_factor = progress_ratio * 0.3  # Up to 30% drift toward warning
            
            record = _build_record(
                machine_type, machine_id, ranges, base_offset,
                "NORMAL", wear_factor, start_time, days_since_maintenance,
                maintenance_count, rng
            )
            records.append(record)
            start_time += timedelta(hours=rng.uniform(0.5, 2.0))
            days_since_maintenance += rng.uniform(0.02, 0.08)
            cycle_progress += 1
        
        # Phase 2: WARNING (next 25-35% of cycle)
        warning_end = normal_end + int(cycle_length * rng.uniform(0.25, 0.35))
        for i in range(normal_end, warning_end):
            progress_ratio = (i - normal_end) / (warning_end - normal_end)
            wear_factor = 0.3 + progress_ratio * 0.4  # 30% to 70% drift
            
            record = _build_record(
                machine_type, machine_id, ranges, base_offset,
                "WARNING", wear_factor, start_time, days_since_maintenance,
                maintenance_count, rng
            )
            records.append(record)
            start_time += timedelta(hours=rng.uniform(0.5, 2.0))
            days_since_maintenance += rng.uniform(0.02, 0.08)
            cycle_progress += 1
        
        # Phase 3: CRITICAL (next 15-25% of cycle)
        critical_end = warning_end + int(cycle_length * rng.uniform(0.15, 0.25))
        for i in range(warning_end, critical_end):
            progress_ratio = (i - warning_end) / (critical_end - warning_end)
            wear_factor = 0.7 + progress_ratio * 0.3  # 70% to 100% drift
            
            record = _build_record(
                machine_type, machine_id, ranges, base_offset,
                "CRITICAL", wear_factor, start_time, days_since_maintenance,
                maintenance_count, rng
            )
            records.append(record)
            start_time += timedelta(hours=rng.uniform(0.5, 2.0))
            days_since_maintenance += rng.uniform(0.02, 0.08)
            cycle_progress += 1
        
        # Maintenance event: reset health
        maintenance_count += 1
        days_since_maintenance = 0
        
        # Phase 4: Post-maintenance NORMAL (remaining records)
        remaining = cycle_length - critical_end
        for i in range(remaining):
            wear_factor = rng.uniform(0, 0.15)  # Fresh after maintenance
            
            record = _build_record(
                machine_type, machine_id, ranges, base_offset,
                "NORMAL", wear_factor, start_time, days_since_maintenance,
                maintenance_count, rng
            )
            records.append(record)
            start_time += timedelta(hours=rng.uniform(0.5, 2.0))
            days_since_maintenance += rng.uniform(0.02, 0.08)
            cycle_progress += 1
    
    # Trim to exact number requested
    return records[:num_records]


def _build_record(
    machine_type: MachineType,
    machine_id: str,
    ranges: Dict,
    base_offset: Dict,
    status: str,
    wear_factor: float,
    timestamp: datetime,
    days_since_maintenance: float,
    maintenance_count: int,
    rng: random.Random
) -> Dict:
    """Build a single training record with realistic sensor values."""
    
    # Generate sensor values that drift based on wear factor
    sensors = {}
    for sensor_name in ["temperature", "vibration", "pressure", "rpm",
                        "voltage", "current", "humidity", "ambient_temperature",
                        "power_consumption"]:
        sensor_ranges = ranges.get(sensor_name, {"normal": (0, 100), "warning": (50, 80), "critical": (80, 100)})
        
        # Interpolate between normal and the target status range based on wear
        normal_low, normal_high = sensor_ranges["normal"]
        
        if status == "NORMAL":
            target_low, target_high = normal_low, normal_high
        elif status == "WARNING":
            warn_low, warn_high = sensor_ranges["warning"]
            # Blend between normal and warning based on wear
            target_low = normal_low + (warn_low - normal_low) * wear_factor
            target_high = normal_high + (warn_high - normal_high) * wear_factor
        else:  # CRITICAL
            crit_low, crit_high = sensor_ranges["critical"]
            # Blend between warning and critical
            warn_low, warn_high = sensor_ranges["warning"]
            target_low = warn_low + (crit_low - warn_low) * wear_factor
            target_high = warn_high + (crit_high - warn_high) * wear_factor
        
        # Add machine-specific offset
        offset = base_offset.get(sensor_name, 0)
        value = rng.uniform(target_low, target_high) + offset
        
        # Add small random noise
        value += rng.gauss(0, (target_high - target_low) * 0.03)
        
        sensors[sensor_name] = round(max(0, value), 2)
    
    # Operating hours correlate with wear
    base_hours = rng.uniform(100, 20000)
    operating_hours = round(base_hours * (1 + wear_factor * 0.5), 1)
    
    return {
        "machine_type": machine_type.value,
        "machine_id": machine_id,
        "timestamp": timestamp.isoformat(),
        "temperature": sensors["temperature"],
        "vibration": sensors["vibration"],
        "pressure": sensors["pressure"],
        "rpm": sensors["rpm"],
        "voltage": sensors["voltage"],
        "current": sensors["current"],
        "humidity": sensors["humidity"],
        "ambient_temperature": sensors["ambient_temperature"],
        "power_consumption": sensors["power_consumption"],
        "operating_hours": operating_hours,
        "days_since_last_maintenance": round(days_since_maintenance, 1),
        "maintenance_count": maintenance_count,
        "status": status,
    }


def generate_training_dataset(num_records: int = 50000) -> pd.DataFrame:
    """
    Generate a realistic historical dataset for training.
    
    Args:
        num_records: Number of records to generate (default 50000)
    
    Returns:
        DataFrame with realistic sensor data and status labels
    """
    import logging
    logging.getLogger(__name__).info("Generating %d realistic training records...", num_records)
    
    all_records = []
    machines_per_type = 10  # 10 machines per type = 50 machines total
    records_per_machine = num_records // (len(ACTIVE_TRAINING_TYPES) * machines_per_type)
    start_time = datetime.now() - timedelta(days=365)
    
    for machine_type in ACTIVE_TRAINING_TYPES:
        type_prefix = {
            MachineType.REFRIGERATOR: "REF",
            MachineType.WASHING_MACHINE: "WM",
            MachineType.AIR_CONDITIONER: "AC",
            MachineType.GENERATOR: "GEN",
            MachineType.CAR_ENGINE: "ENG",
        }.get(machine_type, "MCH")
        
        for i in range(1, machines_per_type + 1):
            machine_id = f"{type_prefix}-{i:03d}"
            machine_start = start_time + timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23)
            )
            
            records = _simulate_degradation_cycle(
                machine_type, machine_id, records_per_machine,
                machine_start, i
            )
            all_records.extend(records)
    
    # Trim to exact count
    if len(all_records) > num_records:
        all_records = all_records[:num_records]
    
    df = pd.DataFrame(all_records)
    
    # Ensure balanced-ish classes
    status_counts = df['status'].value_counts()
    logging.getLogger(__name__).info("Generated %d records", len(df))
    logging.getLogger(__name__).debug("Status distribution: %s", status_counts.to_dict())
    
    return df


# ==================== MODEL TRAINING ====================


def train_model(df: Optional[pd.DataFrame] = None) -> Tuple[RandomForestClassifier, Dict]:
    """
    Train a Random Forest Classifier on the dataset.
    
    Args:
        df: Training data. If None, generates a new dataset.
    
    Returns:
        Tuple of (trained_model, evaluation_metrics)
    """
    if df is None:
        df = generate_training_dataset(50000)
    
    logging.getLogger(__name__).info("Preprocessing data for training")
    
    # Encode machine type
    le_machine_type = LabelEncoder()
    df['machine_type_encoded'] = le_machine_type.fit_transform(df['machine_type'])
    
    # Prepare features and target
    X = df[FEATURE_COLUMNS].copy()
    y = df['status'].values
    
    # Encode target
    le_status = LabelEncoder()
    y_encoded = le_status.fit_transform(y)
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
    )
    
    logging.getLogger(__name__).info("Training set: %d samples", len(X_train))
    logging.getLogger(__name__).info("Test set: %d samples", len(X_test))
    
    # Train Random Forest
    logging.getLogger(__name__).info("Training Random Forest Classifier...")
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=1,
        class_weight='balanced'
    )
    model.fit(X_train, y_train)
    
    # Evaluate
    logging.getLogger(__name__).info("Evaluating model...")
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)
    
    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, average='weighted'), 4),
        "recall": round(recall_score(y_test, y_pred, average='weighted'), 4),
        "f1_score": round(f1_score(y_test, y_pred, average='weighted'), 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "classification_report": classification_report(
            y_test, y_pred,
            target_names=STATUS_LABELS,
            output_dict=True
        ),
        "feature_importance": dict(zip(
            FEATURE_COLUMNS,
            [round(v, 4) for v in model.feature_importances_]
        )),
    }
    
    logging.getLogger(__name__).info("Model Performance: Accuracy=%.2f Precision=%.2f Recall=%.2f F1=%.2f", metrics['accuracy'], metrics['precision'], metrics['recall'], metrics['f1_score'])
    logging.getLogger(__name__).debug("Confusion Matrix: %s", metrics['confusion_matrix'].tolist() if hasattr(metrics['confusion_matrix'], 'tolist') else metrics['confusion_matrix'])
    logging.getLogger(__name__).info("Top 5 feature importances")
    sorted_features = sorted(
        metrics['feature_importance'].items(),
        key=lambda x: x[1],
        reverse=True
    )
    for name, importance in sorted_features[:5]:
        logging.getLogger(__name__).info("  %s: %.4f", name, importance)
    
    # Save artifacts
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    
    encoders = {
        'machine_type': le_machine_type,
        'status': le_status,
    }
    with open(ENCODER_PATH, 'wb') as f:
        pickle.dump(encoders, f)
    
    config = {
        'feature_columns': FEATURE_COLUMNS,
        'status_labels': STATUS_LABELS,
        'status_map': STATUS_MAP,
        'training_date': datetime.now().isoformat(),
        'num_samples': len(df),
        'metrics': metrics,
    }
    with open(FEATURES_PATH, 'wb') as f:
        pickle.dump(config, f)
    
    # Save dataset
    df.to_csv(DATASET_PATH, index=False)
    
    logging.getLogger(__name__).info("Model saved to: %s", MODEL_PATH)
    logging.getLogger(__name__).info("Encoders saved to: %s", ENCODER_PATH)
    logging.getLogger(__name__).info("Config saved to: %s", FEATURES_PATH)
    logging.getLogger(__name__).info("Dataset saved to: %s", DATASET_PATH)
    
    return model, metrics


# ==================== MODEL LOADING ====================


def load_model() -> Optional[RandomForestClassifier]:
    """Load the trained model from disk."""
    if not os.path.exists(MODEL_PATH):
        logging.getLogger(__name__).warning("Model not found at %s. Training new model...", MODEL_PATH)
        model, _ = train_model()
        return model
    
    with open(MODEL_PATH, 'rb') as f:
        model = pickle.load(f)
    if hasattr(model, "n_jobs"):
        model.n_jobs = 1
    return model


def load_encoders() -> Optional[Dict]:
    """Load label encoders from disk."""
    if not os.path.exists(ENCODER_PATH):
        return None
    with open(ENCODER_PATH, 'rb') as f:
        return pickle.load(f)


def load_config() -> Optional[Dict]:
    """Load feature config from disk."""
    if not os.path.exists(FEATURES_PATH):
        return None
    with open(FEATURES_PATH, 'rb') as f:
        return pickle.load(f)


# ==================== PREDICTION ====================


class MLPredictor:
    """
    Machine Learning Predictor for live sensor data.
    
    Takes raw sensor readings and machine info, returns ML-based predictions
    with confidence scores and class probabilities.
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
        self.model = None
        self.encoders = None
        self.config = None
        self._load_artifacts()
    
    def _load_artifacts(self):
        """Load model, encoders, and config from disk."""
        try:
            self.model = load_model()
            self.encoders = load_encoders()
            self.config = load_config()
            if self.model is not None:
                logging.getLogger(__name__).info("ML Model loaded successfully")
                if self.config and 'metrics' in self.config:
                    m = self.config['metrics']
                    logging.getLogger(__name__).info("  Training accuracy: %s", m.get('accuracy', 'N/A'))
        except Exception as e:
            logging.getLogger(__name__).warning("Could not load ML model: %s", e)
            logging.getLogger(__name__).info("Will train a new model on first prediction.")
            self.model = None
    
    def _ensure_model_loaded(self):
        """Ensure model is loaded, training if necessary."""
        if self.model is None:
            logging.getLogger(__name__).info("Training new ML model...")
            self.model, metrics = train_model()
            self.encoders = load_encoders()
            self.config = load_config()
    
    def predict(
        self,
        machine_type: str,
        sensor_readings: Dict[str, float],
        operating_hours: float,
        days_since_last_maintenance: float,
        maintenance_count: int
    ) -> Dict[str, Any]:
        """
        Predict machine status from live sensor data.
        
        Args:
            machine_type: String value of MachineType (e.g., "Refrigerator")
            sensor_readings: Dict of sensor_name -> value
            operating_hours: Total operating hours
            days_since_last_maintenance: Days since last maintenance
            maintenance_count: Number of maintenance events
        
        Returns:
            Dict with:
                - predicted_status: "NORMAL", "WARNING", or "CRITICAL"
                - confidence: Prediction confidence (0-1)
                - probabilities: Dict of status -> probability
                - top_features: Top contributing features
        """
        self._ensure_model_loaded()
        
        if self.model is None or self.encoders is None or self.config is None:
            raise RuntimeError("Random Forest model artifacts are unavailable")
        
        try:
            # Encode machine type
            le_machine_type = self.encoders['machine_type']
            try:
                machine_type_encoded = le_machine_type.transform([machine_type])[0]
            except ValueError:
                # Unknown machine type - use the most common one
                machine_type_encoded = le_machine_type.transform(
                    [le_machine_type.classes_[0]]
                )[0]
            
            # Build feature vector
            feature_values = {
                "machine_type_encoded": machine_type_encoded,
                "temperature": sensor_readings.get("temperature", 25.0),
                "vibration": sensor_readings.get("vibration", 0.5),
                "pressure": sensor_readings.get("pressure", 2.0),
                "rpm": sensor_readings.get("rpm", 1000),
                "voltage": sensor_readings.get("voltage", 230.0),
                "current": sensor_readings.get("current", 5.0),
                "humidity": sensor_readings.get("humidity", 50.0),
                "ambient_temperature": sensor_readings.get("ambient_temperature", 25.0),
                "power_consumption": sensor_readings.get("power_consumption", 1.0),
                "operating_hours": operating_hours,
                "days_since_last_maintenance": days_since_last_maintenance,
                "maintenance_count": maintenance_count,
            }
            
            # Create feature array in correct order
            feature_array = np.array([[
                feature_values[col] for col in self.config['feature_columns']
            ]])
            
            # Predict
            prediction = self.model.predict(feature_array)[0]
            probabilities = self.model.predict_proba(feature_array)[0]
            
            # Map prediction to status label
            le_status = self.encoders['status']
            predicted_status = le_status.inverse_transform([prediction])[0]
            
            # Get confidence (max probability)
            confidence = float(max(probabilities))
            
            # Build probability dict
            prob_dict = {}
            for i, label in enumerate(le_status.classes_):
                prob_dict[label] = round(float(probabilities[i]), 4)
            
            # Get top contributing features
            feature_importance = self.model.feature_importances_
            feature_names = self.config['feature_columns']
            
            # Calculate feature contributions for this prediction
            contributions = []
            for i, (name, importance) in enumerate(
                sorted(zip(feature_names, feature_importance),
                       key=lambda x: x[1], reverse=True)
            ):
                contributions.append({
                    "feature": name,
                    "importance": round(float(importance), 4),
                    "value": round(float(feature_array[0][i]), 2)
                })
            
            return {
                "predicted_status": predicted_status,
                "confidence": round(confidence, 4),
                "probabilities": prob_dict,
                "top_features": contributions[:5],
                "all_features": contributions,
                "model_used": "random_forest",
            }
            
        except Exception as e:
            logging.getLogger(__name__).exception("ML prediction error: %s", e)
            raise
    
    def _rule_based_fallback(
        self,
        machine_type: str,
        sensor_readings: Dict[str, float],
        operating_hours: float
    ) -> Dict[str, Any]:
        """Fallback rule-based prediction when ML model is unavailable."""
        # Simple heuristic based on sensor deviations
        ranges = MACHINE_OPERATING_RANGES.get(
            next((mt for mt in ACTIVE_TRAINING_TYPES if mt.value == machine_type), None),
            MACHINE_OPERATING_RANGES[MachineType.REFRIGERATOR]
        )
        
        warning_count = 0
        critical_count = 0
        total_sensors = 0
        
        for sensor_name, value in sensor_readings.items():
            if sensor_name in ranges:
                sensor_ranges = ranges[sensor_name]
                total_sensors += 1
                
                if "critical" in sensor_ranges:
                    crit_low, crit_high = sensor_ranges["critical"]
                    if crit_low <= value <= crit_high:
                        critical_count += 1
                        continue
                
                if "warning" in sensor_ranges:
                    warn_low, warn_high = sensor_ranges["warning"]
                    if warn_low <= value <= warn_high:
                        warning_count += 1
        
        if total_sensors == 0:
            return {
                "predicted_status": "NORMAL",
                "confidence": 0.5,
                "probabilities": {"NORMAL": 0.5, "WARNING": 0.3, "CRITICAL": 0.2},
                "top_features": [],
                "all_features": [],
                "model_used": "rule_based_fallback",
            }
        
        if critical_count > 0:
            status = "CRITICAL"
            confidence = min(0.9, 0.5 + critical_count / total_sensors * 0.4)
        elif warning_count > 0:
            status = "WARNING"
            confidence = min(0.8, 0.4 + warning_count / total_sensors * 0.4)
        else:
            status = "NORMAL"
            confidence = 0.7
        
        return {
            "predicted_status": status,
            "confidence": round(confidence, 4),
            "probabilities": {
                "NORMAL": round(0.7 if status == "NORMAL" else 0.2, 4),
                "WARNING": round(0.2 if status == "NORMAL" else 0.5, 4),
                "CRITICAL": round(0.1 if status == "NORMAL" else 0.3, 4),
            },
            "top_features": [],
            "all_features": [],
            "model_used": "rule_based_fallback",
        }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the trained model."""
        self._ensure_model_loaded()
        
        if self.config:
            info = {
                "model_type": "Random Forest Classifier",
                "training_date": self.config.get('training_date', 'Unknown'),
                "num_samples": self.config.get('num_samples', 0),
                "num_features": len(self.config.get('feature_columns', [])),
                "feature_columns": self.config.get('feature_columns', []),
                "status_labels": self.config.get('status_labels', []),
                "metrics": self.config.get('metrics', {}),
            }
            if self.model is not None:
                info["n_estimators"] = self.model.n_estimators
                info["max_depth"] = self.model.max_depth
            return info
        
        return {
            "model_type": "Not trained",
            "message": "Model has not been trained yet."
        }


# ==================== CONVENIENCE FUNCTIONS ====================


def get_predictor() -> MLPredictor:
    """Get the ML predictor singleton."""
    return MLPredictor()


def predict_machine_status(
    machine_type: str,
    sensor_readings: Dict[str, float],
    operating_hours: float,
    days_since_last_maintenance: float = 0,
    maintenance_count: int = 0
) -> Dict[str, Any]:
    """
    Convenience function to predict machine status.
    
    Args:
        machine_type: e.g., "Refrigerator", "Generator"
        sensor_readings: Dict of sensor_name -> value
        operating_hours: Total operating hours
        days_since_last_maintenance: Days since last maintenance
        maintenance_count: Number of maintenance events
    
    Returns:
        Prediction result dict
    """
    predictor = get_predictor()
    return predictor.predict(
        machine_type, sensor_readings, operating_hours,
        days_since_last_maintenance, maintenance_count
    )


def retrain_model() -> Tuple[RandomForestClassifier, Dict]:
    """Retrain the model from scratch."""
    model, metrics = train_model()
    # Reset predictor singleton so it reloads
    MLPredictor._instance = None
    return model, metrics


# ==================== MAIN ====================

if __name__ == "__main__":
    logging.getLogger(__name__).info("%s", "=" * 60)
    logging.getLogger(__name__).info("Predictive Maintenance ML Model Training")
    logging.getLogger(__name__).info("%s", "=" * 60)
    
    # Generate dataset and train model
    model, metrics = train_model()
    
    logging.getLogger(__name__).info("%s\nTraining Complete!\n%s", "=" * 60, "=" * 60)
    
    # Test prediction
    logging.getLogger(__name__).info("Testing prediction with sample data...")
    predictor = get_predictor()
    
    # Test with a healthy refrigerator
    result = predictor.predict(
        machine_type="Refrigerator",
        sensor_readings={
            "temperature": 4.5,
            "vibration": 0.3,
            "pressure": 2.0,
            "rpm": 1000,
            "voltage": 230,
            "current": 3.0,
            "humidity": 45,
            "ambient_temperature": 25,
            "power_consumption": 0.8,
        },
        operating_hours=500,
        days_since_last_maintenance=5,
        maintenance_count=3
    )
    logging.getLogger(__name__).info("Healthy Refrigerator Prediction: Status=%s Confidence=%.2f", result['predicted_status'], result['confidence'])
    logging.getLogger(__name__).debug("Probabilities: %s", result['probabilities'])
    
    # Test with a failing generator
    result = predictor.predict(
        machine_type="Generator",
        sensor_readings={
            "temperature": 92,
            "vibration": 2.5,
            "pressure": 7.0,
            "rpm": 1800,
            "voltage": 255,
            "current": 70,
            "humidity": 70,
            "ambient_temperature": 45,
            "power_consumption": 30,
        },
        operating_hours=12000,
        days_since_last_maintenance=90,
        maintenance_count=1
    )
    logging.getLogger(__name__).info("Failing Generator Prediction: Status=%s Confidence=%.2f", result['predicted_status'], result['confidence'])
    logging.getLogger(__name__).debug("Probabilities: %s", result['probabilities'])
