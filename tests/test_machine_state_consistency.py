import os
import sqlite3
import tempfile
import unittest

from enterprise.database import DatabaseManager
from enterprise.models import MachineStatus
from enterprise.services import get_sync_engine
from enterprise.simulation import EnterpriseSimulator


class MachineStateConsistencyTests(unittest.TestCase):
    def test_prediction_state_updates_condition_health_and_cause_consistently(self):
        simulator = EnterpriseSimulator()
        machine = simulator.get_machine("WM-008")
        if machine is None:
            self.skipTest("WM-008 machine not available")

        machine.health_score = 82.0
        machine.status = MachineStatus.WARNING
        ml_result = {
            "predicted_status": "WARNING",
            "confidence": 0.81,
            "probabilities": {"NORMAL": 0.1, "WARNING": 0.7, "CRITICAL": 0.2},
            "top_features": [{"feature": "temperature", "importance": 0.8, "value": 45.0}],
        }

        simulator._update_machine_prediction_state(
            machine,
            ml_result=ml_result,
            latest_readings={"temperature": {"sensor_value": 45.0}},
            persist=False,
        )

        self.assertEqual(machine.condition, "Warning")
        self.assertEqual(machine.status, MachineStatus.WARNING)
        self.assertLess(machine.health_score, 85.0)
        self.assertGreaterEqual(machine.health_score, 60)
        self.assertIn("temperature", machine.cause.lower())
        self.assertEqual(machine.maintenance_recommendation, "Within 7 Days")

    def test_ml_prediction_remains_authoritative_during_synchronization(self):
        simulator = EnterpriseSimulator()
        machine = simulator.get_machine("WM-008")
        if machine is None:
            self.skipTest("WM-008 machine not available")

        machine.health_score = 95.0
        machine.status = MachineStatus.NORMAL
        machine.ml_prediction = {
            "predicted_status": "WARNING",
            "confidence": 0.82,
            "probabilities": {"NORMAL": 0.1, "WARNING": 0.8, "CRITICAL": 0.1},
        }
        machine.cause = ""
        machine.maintenance_recommendation = ""

        sync_engine = get_sync_engine()
        sync_engine.synchronize_machine(machine)

        self.assertEqual(machine.status, MachineStatus.WARNING)
        self.assertEqual(machine.condition, "Warning")
        self.assertEqual(machine.maintenance_recommendation, "Within 7 Days")

    def test_purchase_date_is_loaded_from_excel_for_each_machine(self):
        from enterprise.data_loader import load_machines_from_excel

        machines = load_machines_from_excel()
        self.assertGreater(len(machines), 0)
        for machine in machines:
            self.assertIsNotNone(machine.purchase_date, msg=f"{machine.machine_id} is missing purchase_date")

    def test_warning_state_generates_alert_and_work_order_consistently(self):
        simulator = EnterpriseSimulator()
        machine = simulator.get_machine("WM-008")
        if machine is None:
            self.skipTest("WM-008 machine not available")

        machine.health_score = 72.0
        machine.status = MachineStatus.NORMAL
        machine.ml_prediction = {
            "predicted_status": "WARNING",
            "confidence": 0.9,
            "probabilities": {"NORMAL": 0.0, "WARNING": 0.9, "CRITICAL": 0.1},
        }
        machine.cause = ""
        machine.maintenance_recommendation = ""

        sync_engine = get_sync_engine()
        sync_engine.synchronize_machine(machine)

        from enterprise.services import get_data_store
        store = get_data_store()
        alerts = store.alert_service.get_alerts_by_machine(machine.machine_id)
        open_alerts = [a for a in alerts if a.status == "Open"]
        work_orders = store.work_order_service.get_work_orders_by_machine(machine.machine_id)

        self.assertEqual(machine.status, MachineStatus.WARNING)
        self.assertTrue(open_alerts)
        self.assertTrue(work_orders)
        self.assertLessEqual(len(open_alerts), 1)
        self.assertLessEqual(len(work_orders), 1)

    def test_database_manager_adds_missing_machine_columns_for_older_databases(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test_predictive_maintenance.db")
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("""
                    CREATE TABLE Machines (
                        machine_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        machine_type TEXT NOT NULL,
                        status TEXT DEFAULT 'NORMAL',
                        health_score REAL DEFAULT 100.0
                    )
                """)
                conn.commit()
            finally:
                conn.close()

            db = DatabaseManager(db_path=db_path)
            conn = sqlite3.connect(db_path)
            try:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(Machines)").fetchall()}
            finally:
                conn.close()

            self.assertIn("condition", columns)
            self.assertIn("cause", columns)
            self.assertIn("maintenance_recommendation", columns)


if __name__ == "__main__":
    unittest.main()
