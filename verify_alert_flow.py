import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

from enterprise.simulation import EnterpriseSimulator
from enterprise.services import get_data_store, get_sync_engine
from enterprise.models import MachineStatus

sim = EnterpriseSimulator()
machine = sim.get_machine('WM-008')
machine.health_score = 70.0
machine.status = MachineStatus.NORMAL
machine.ml_prediction = {
    'predicted_status': 'WARNING',
    'confidence': 0.9,
    'probabilities': {'NORMAL': 0.0, 'WARNING': 0.9, 'CRITICAL': 0.1}
}
machine.cause = ''
machine.maintenance_recommendation = ''

engine = get_sync_engine()
engine.synchronize_machine(machine)
store = get_data_store()
alerts = store.alert_service.get_alerts_by_machine(machine.machine_id)
open_alerts = [a for a in alerts if a.status == 'Open']
work_orders = store.work_order_service.get_work_orders_by_machine(machine.machine_id)
print('status', machine.status.value)
print('alert_count', len(open_alerts))
print('alert_severity', [a.severity.value for a in open_alerts])
print('work_order_count', len(work_orders))
print('work_order_status', [wo.status.value for wo in work_orders])
