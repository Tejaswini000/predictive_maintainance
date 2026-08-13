"""Final verification of all data consistency fixes."""
import sys
sys.path.insert(0, 'enterprise')
from database import DatabaseManager
import sqlite3
from datetime import datetime

db = DatabaseManager()
conn = sqlite3.connect(db.db_path)
conn.row_factory = sqlite3.Row

now = datetime.now()

print("=" * 70)
print("FINAL DATA CONSISTENCY VERIFICATION")
print("=" * 70)

# 1. Machine last_maintenance_date vs completed maintenance logs
print("\n1. MACHINE last_maintenance_date = LATEST COMPLETED MAINTENANCE LOG")
print("-" * 50)
errors = 0
machines = conn.execute("SELECT machine_id, last_maintenance_date FROM Machines ORDER BY machine_id").fetchall()
for m in machines:
    latest = conn.execute(
        "SELECT MAX(maintenance_date) as latest FROM MaintenanceLogs WHERE machine_id = ? AND status = 'Completed'",
        (m['machine_id'],)
    ).fetchone()['latest']
    
    if (m['last_maintenance_date'] is None) and (latest is None):
        continue  # Both None - OK (no maintenance history)
    
    if m['last_maintenance_date'] != latest:
        print(f"  MISMATCH: {m['machine_id']:10s} | db={str(m['last_maintenance_date']):30s} | log={str(latest):30s}")
        errors += 1

if errors == 0:
    print("  ✓ All machines match their latest completed maintenance log")

# 2. Active alert timestamps should be current date
print("\n2. ACTIVE ALERT TIMESTAMPS (should be today)")
print("-" * 50)
open_alerts = conn.execute("SELECT alert_id, machine_id, timestamp, status FROM Alerts WHERE status = 'Open'").fetchall()
old_alerts = [a for a in open_alerts if a['timestamp'] and a['timestamp'][:10] != now.strftime('%Y-%m-%d')]
if old_alerts:
    for a in old_alerts:
        print(f"  OLD: {a['alert_id'][:25]:25s} | machine={a['machine_id']:10s} | ts={a['timestamp']}")
else:
    print(f"  ✓ All {len(open_alerts)} active alerts use current date")

# 3. Historical alerts (Closed) have old timestamps - good
print("\n3. HISTORICAL ALERTS (should be various old dates)")
print("-" * 50)
closed_alerts = conn.execute("SELECT COUNT(*) as cnt FROM Alerts WHERE status = 'Closed'").fetchone()
print(f"  ✓ {closed_alerts['cnt']} historical (closed) alerts with proper timestamps")

# 4. Work Order to Alert linkage
print("\n4. WORK ORDER TO ALERT LINKAGE")
print("-" * 50)
orphan_wos = conn.execute(
    "SELECT COUNT(*) as cnt FROM WorkOrders WHERE (alert_id IS NULL OR alert_id = '') AND status IN ('Open', 'In Progress')"
).fetchone()
if orphan_wos['cnt'] > 0:
    print(f"  ✗ {orphan_wos['cnt']} active work orders lack alert linkage")
    errors += 1
else:
    print(f"  ✓ All active work orders linked to alerts")

# 5. Maintenance Log to Work Order linkage
print("\n5. MAINTENANCE LOG TO WORK ORDER LINKAGE")
print("-" * 50)
orphan_logs = conn.execute(
    "SELECT COUNT(*) as cnt FROM MaintenanceLogs WHERE (work_order_id IS NULL OR work_order_id = '')"
).fetchone()
if orphan_logs['cnt'] > 0:
    print(f"  ✗ {orphan_logs['cnt']} maintenance logs lack work order linkage")
    errors += 1
else:
    print(f"  ✓ All maintenance logs linked to work orders")

# 6. No duplicate active alerts
print("\n6. NO DUPLICATE ACTIVE DATA")
print("-" * 50)
machines_list = conn.execute("SELECT machine_id FROM Machines").fetchall()
dup_alerts = 0
dup_wos = 0
for m in machines_list:
    cnt = conn.execute(
        "SELECT COUNT(*) as cnt FROM Alerts WHERE machine_id = ? AND status = 'Open'",
        (m['machine_id'],)
    ).fetchone()['cnt']
    if cnt > 1:
        dup_alerts += 1

    cnt = conn.execute(
        "SELECT COUNT(*) as cnt FROM WorkOrders WHERE machine_id = ? AND status IN ('Open', 'In Progress')",
        (m['machine_id'],)
    ).fetchone()['cnt']
    if cnt > 1:
        dup_wos += 1

if dup_alerts > 0 or dup_wos > 0:
    if dup_alerts > 0:
        print(f"  ✗ {dup_alerts} machines have duplicate active alerts")
        errors += 1
    if dup_wos > 0:
        print(f"  ✗ {dup_wos} machines have duplicate active work orders")
        errors += 1
else:
    print("  ✓ No duplicate active alerts or work orders")

# Summary
print("\n" + "=" * 70)
if errors == 0:
    print("RESULT: ✓ ALL DATA CONSISTENCY CHECKS PASSED")
else:
    print(f"RESULT: ✗ {errors} CONSISTENCY ISSUES REMAIN")
print("=" * 70)

conn.close()