import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

from enterprise.simulation import EnterpriseSimulator
from enterprise.services import get_sync_engine
from enterprise.models import MachineStatus

sim = EnterpriseSimulator()
machine = sim.get_machine('WM-008')
print('before', machine.status.value, machine.condition, machine.health_score, machine.cause, machine.maintenance_recommendation, machine.purchase_date)

machine.health_score = 95.0
machine.status = MachineStatus.NORMAL
machine.ml_prediction = {
    'predicted_status': 'WARNING',
    'confidence': 0.82,
    'probabilities': {'NORMAL': 0.1, 'WARNING': 0.8, 'CRITICAL': 0.1},
}

sync_engine = get_sync_engine()
sync_engine.synchronize_machine(machine)
print('after', machine.status.value, machine.condition, machine.health_score, machine.cause, machine.maintenance_recommendation)

from enterprise.data_loader import load_machines_from_excel
machines = load_machines_from_excel()
print('purchase_date_count', len([m for m in machines if m.purchase_date is not None]))
print('sample_purchase_date', machines[0].purchase_date)
