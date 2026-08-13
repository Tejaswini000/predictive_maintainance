"""Stress test for synchronization engine - multiple simulation cycles."""
import sys
sys.path.insert(0, 'enterprise')

from services import get_data_store, get_sync_engine
from simulation import EnterpriseSimulator
from database import DatabaseManager

print("=== STRESS TEST: Multiple Simulation Cycles ===\n")

sim = EnterpriseSimulator()
data_store = get_data_store()
sync_engine = get_sync_engine()
db = DatabaseManager()

print(f"Initial machines: {len(sim.get_all_machines())}")

# Run 10 simulation cycles
for cycle in range(10):
    sim.simulate_health_degradation()
    
    # Validate consistency
    validation = sync_engine.validate_consistency()
    stats = sim.get_stats()
    
    if not validation['consistent']:
        print(f"Cycle {cycle+1}: INCONSISTENT! Issues: {len(validation['issues'])}")
        for issue in validation['issues'][:3]:
            print(f"  {issue}")
        # Auto-repair
        repaired = sync_engine.auto_repair()
        print(f"  Repaired: {repaired}")
    else:
        print(f"Cycle {cycle+1}: Consistent | H={stats['healthy_count']} W={stats['warning_count']} C={stats['critical_count']} A={stats['open_alerts']}")

# Final detailed validation
print("\n=== FINAL VALIDATION ===")
validation = sync_engine.validate_consistency()
print(f"Consistent: {validation['consistent']}")
print(f"Total machines: {validation['total_machines']}")
print(f"Critical machines: {validation['critical_machines']}")
print(f"Warning machines: {validation['warning_machines']}")
print(f"Healthy machines: {validation['healthy_machines']}")
print(f"Open alerts: {validation['open_alerts']}")
print(f"Critical alerts: {validation['critical_alerts']}")
print(f"Warning alerts: {validation['warning_alerts']}")

# Verify each machine
all_machines = sim.get_all_machines()
for machine in all_machines:
    active_alert = data_store.alert_service.get_active_alert_by_machine(machine.machine_id)
    
    # Check status matches health
    expected_status = 'NORMAL'
    if machine.health_score < 40:
        expected_status = 'CRITICAL'
    elif machine.health_score < 70:
        expected_status = 'WARNING'
    
    if machine.status.value != expected_status:
        print(f"  STATUS MISMATCH: {machine.machine_id} status={machine.status.value} health={machine.health_score}% expected={expected_status}")
    
    # Check alert matches status
    if machine.status.value == 'NORMAL':
        if active_alert is not None:
            print(f"  ALERT LEAK: {machine.machine_id} NORMAL but has {active_alert.severity.value} alert")
    elif machine.status.value == 'WARNING':
        if active_alert is None:
            print(f"  MISSING ALERT: {machine.machine_id} WARNING but no alert")
        elif active_alert.severity.value != 'WARNING':
            print(f"  WRONG ALERT: {machine.machine_id} WARNING but alert is {active_alert.severity.value}")
    elif machine.status.value == 'CRITICAL':
        if active_alert is None:
            print(f"  MISSING ALERT: {machine.machine_id} CRITICAL but no alert")
        elif active_alert.severity.value != 'CRITICAL':
            print(f"  WRONG ALERT: {machine.machine_id} CRITICAL but alert is {active_alert.severity.value}")
    
    # Check no duplicate alerts
    all_alerts = db.get_alerts_by_machine(machine.machine_id)
    open_count = sum(1 for a in all_alerts if a.status == 'Open')
    if open_count > 1:
        print(f"  DUPLICATE ALERTS: {machine.machine_id} has {open_count} open alerts")
    
    # Check work orders
    if machine.status.value in ('WARNING', 'CRITICAL'):
        active_wos = [wo for wo in db.get_work_orders_by_machine(machine.machine_id) 
                     if wo.status.value in ('Open', 'In Progress')]
        if len(active_wos) > 1:
            print(f"  DUPLICATE WORK ORDERS: {machine.machine_id} has {len(active_wos)} active work orders")

print("\n=== STRESS TEST COMPLETE ===")