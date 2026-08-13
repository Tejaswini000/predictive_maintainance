"""Test script for synchronization engine."""
import sys
sys.path.insert(0, 'enterprise')

from services import get_data_store, get_sync_engine
from simulation import EnterpriseSimulator
from database import DatabaseManager

print("Imports OK")

# Initialize
sim = EnterpriseSimulator()
data_store = get_data_store()
sync_engine = get_sync_engine()

print(f"Initial machines: {len(sim.get_all_machines())}")

# Test 1: Validate initial consistency
validation = sync_engine.validate_consistency()
print(f"Initial consistency: {validation['consistent']}")
if validation['issues']:
    for issue in validation['issues'][:5]:
        print(f"  Issue: {issue}")

# Test 2: Run a simulation step
print("\nRunning simulation step...")
sim.simulate_health_degradation()

# Test 3: Validate consistency after simulation
validation = sync_engine.validate_consistency()
print(f"After simulation consistency: {validation['consistent']}")
if validation['issues']:
    for issue in validation['issues'][:5]:
        print(f"  Issue: {issue}")
else:
    print("  No issues found - all systems consistent!")

# Test 4: Show stats
stats = sim.get_stats()
print(f"\nStats: Total={stats['total_machines']}, Healthy={stats['healthy_count']}, Warning={stats['warning_count']}, Critical={stats['critical_count']}, Alerts={stats['open_alerts']}")

# Test 5: Verify counts match
all_machines = sim.get_all_machines()
open_alerts = data_store.alert_service.get_open_alerts()
critical_machines = [m for m in all_machines if m.status.value == 'CRITICAL']
warning_machines = [m for m in all_machines if m.status.value == 'WARNING']
normal_machines = [m for m in all_machines if m.status.value == 'NORMAL']

assert stats['critical_count'] == len(critical_machines), f"Critical mismatch: {stats['critical_count']} != {len(critical_machines)}"
assert stats['warning_count'] == len(warning_machines), f"Warning mismatch: {stats['warning_count']} != {len(warning_machines)}"
assert stats['healthy_count'] == len(normal_machines), f"Healthy mismatch: {stats['healthy_count']} != {len(normal_machines)}"
assert stats['open_alerts'] == len(open_alerts), f"Alert count mismatch: {stats['open_alerts']} != {len(open_alerts)}"
print("\nAll dashboard count assertions passed!")

# Test 6: Verify each machine's alert matches status
db = DatabaseManager()
for machine in all_machines:
    active_alert = data_store.alert_service.get_active_alert_by_machine(machine.machine_id)
    
    if machine.status.value == 'NORMAL':
        assert active_alert is None, f"{machine.machine_id}: NORMAL but has active alert"
    elif machine.status.value == 'WARNING':
        assert active_alert is not None, f"{machine.machine_id}: WARNING but no active alert"
        assert active_alert.severity.value == 'WARNING', f"{machine.machine_id}: WARNING but alert severity is {active_alert.severity.value}"
    elif machine.status.value == 'CRITICAL':
        assert active_alert is not None, f"{machine.machine_id}: CRITICAL but no active alert"
        assert active_alert.severity.value == 'CRITICAL', f"{machine.machine_id}: CRITICAL but alert severity is {active_alert.severity.value}"
    
    # Check no duplicate open alerts
    all_alerts = db.get_alerts_by_machine(machine.machine_id)
    open_count = sum(1 for a in all_alerts if a.status == 'Open')
    assert open_count <= 1, f"{machine.machine_id}: {open_count} open alerts (max 1)"
    
    # Check work orders
    if machine.status.value in ('WARNING', 'CRITICAL'):
        active_wos = [wo for wo in db.get_work_orders_by_machine(machine.machine_id) 
                     if wo.status.value in ('Open', 'In Progress')]
        assert len(active_wos) <= 1, f"{machine.machine_id}: {len(active_wos)} active work orders (max 1)"

print("All machine-level assertions passed!")

# Test 7: Auto-repair
repaired = sync_engine.auto_repair()
print(f"\nAuto-repair count: {repaired}")

validation = sync_engine.validate_consistency()
print(f"Final consistency: {validation['consistent']}")

print("\n=== ALL TESTS PASSED ===")