import unittest
from datetime import datetime, timedelta

from enterprise.models import MachineStatus
from enterprise.services import get_data_store, get_sync_engine
from enterprise.simulation import EnterpriseSimulator


class MaintenanceHistoryRealismTests(unittest.TestCase):
    def test_warning_cause_generates_specific_work_order_and_maintenance_action(self):
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
        machine.cause = "Bearing wear"
        machine.maintenance_recommendation = ""
        # Ensure a clean DB state for this machine so the test creates a fresh work order
        from enterprise.database import DatabaseManager
        db = DatabaseManager()
        for wo in db.get_work_orders_by_machine(machine.machine_id):
            db.delete_work_order(wo.work_order_id)
        for alert in db.get_alerts_by_machine(machine.machine_id):
            db.delete_alert(alert.alert_id)
        for log in db.get_maintenance_logs_by_machine(machine.machine_id):
            db.delete_maintenance_log(log.log_id)

        sync_engine = get_sync_engine()
        sync_engine.synchronize_machine(machine)

        store = get_data_store()
        work_orders = store.work_order_service.get_work_orders_by_machine(machine.machine_id)
        self.assertTrue(work_orders)

        latest_wo = work_orders[-1]
        text = f"{latest_wo.title} {latest_wo.description}".lower()
        self.assertIn("bearing", text)
        self.assertIn("replacement", text)

        logs = store.maintenance_log_service.get_logs_by_machine(machine.machine_id)
        self.assertTrue(logs)
        self.assertTrue(
            any("bearing" in (log.description or "").lower() or "bearing" in (log.action_taken or "").lower()
            for log in logs)
        )

        open_alerts = [
            alert for alert in store.alert_service.get_alerts_by_machine(machine.machine_id)
            if alert.status == "Open"
        ]
        self.assertEqual(len(open_alerts), 1)
        linked_log = next(
            (log for log in logs if log.work_order_id == latest_wo.work_order_id),
            None
        )
        self.assertIsNotNone(linked_log)
        self.assertEqual(open_alerts[0].reason, linked_log.description)
        self.assertNotEqual(linked_log.issue, linked_log.description)

    def test_historical_logs_are_seeded_from_purchase_date_for_older_machines(self):
        simulator = EnterpriseSimulator()
        machine = simulator.get_machine("WM-008")
        if machine is None:
            self.skipTest("WM-008 machine not available")

        machine.purchase_date = datetime.now() - timedelta(days=1200)
        machine.last_maintenance_date = None

        store = get_data_store()
        store.maintenance_log_service.seed_historical_logs(machine)

        logs = store.maintenance_log_service.get_logs_by_machine(machine.machine_id)
        self.assertTrue(logs)
        self.assertTrue(any(log.maintenance_date for log in logs))


if __name__ == "__main__":
    unittest.main()
