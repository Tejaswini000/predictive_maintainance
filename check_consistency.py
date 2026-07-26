"""Check data consistency between machines and maintenance logs."""
import sys
sys.path.insert(0, 'enterprise')
from database import DatabaseManager
import sqlite3

db = DatabaseManager()
conn = sqlite3.connect(db.db_path)
conn.row_factory = sqlite3.Row

# Check Machines vs MaintenanceLogs
machines = conn.execute('SELECT machine_id, name, last_maintenance_date, health_score, status FROM Machines ORDER BY machine_id').fetchall()
print("=== MACHINE last_maintenance_date vs MAINTENANCE LOGS ===")
for m in machines:
    logs = conn.execute("SELECT COUNT(*) as cnt FROM MaintenanceLogs WHERE machine_id = ? AND status = 'Completed'", (m['machine_id'],)).fetchone()
    latest = conn.execute("SELECT MAX(maintenance_date) as latest FROM MaintenanceLogs WHERE machine_id = ? AND status = 'Completed'", (m['machine_id'],)).fetchone()
    print(f'{m["machine_id"]:12s} | db_last_maint={str(m["last_maintenance_date"]):25s} | completed_logs={logs["cnt"]:3d} | latest_log_date={str(latest["latest"]):25s} | health={m["health_score"]:5.1f} | status={m["status"]}')

# Check Alerts
print("\n=== ACTIVE ALERTS ===")
alerts = conn.execute('SELECT alert_id, machine_id, severity, timestamp, status FROM Alerts WHERE status = "Open" ORDER BY timestamp DESC').fetchall()
for a in alerts:
    print(f'{a["alert_id"]:40s} | machine={a["machine_id"]:10s} | severity={a["severity"]:8s} | timestamp={a["timestamp"]:25s} | status={a["status"]}')

# Check Work Orders
print("\n=== ACTIVE WORK ORDERS ===")
wos = conn.execute("SELECT work_order_id, machine_id, status, alert_id, created_date FROM WorkOrders WHERE status IN ('Open', 'In Progress') ORDER BY created_date DESC").fetchall()
for wo in wos:
    print(f'{wo["work_order_id"]:30s} | machine={wo["machine_id"]:10s} | status={wo["status"]:12s} | alert_id={str(wo["alert_id"]):15s} | created={wo["created_date"]}')

# Alert vs Work Order linkage
print("\n=== WORK ORDERS WITHOUT ALERT IDs ===")
orphan_wos = conn.execute("SELECT work_order_id, machine_id, status FROM WorkOrders WHERE alert_id IS NULL OR alert_id = ''").fetchall()
for wo in orphan_wos:
    print(f'{wo["work_order_id"]:30s} | machine={wo["machine_id"]:10s} | status={wo["status"]}')

print("\n=== MAINTENANCE LOGS WITHOUT WORK ORDER IDs ===")
orphan_logs = conn.execute("SELECT log_id, machine_id, status, work_order_id FROM MaintenanceLogs WHERE work_order_id IS NULL OR work_order_id = ''").fetchall()
for log in orphan_logs:
    print(f'{log["log_id"]:30s} | machine={log["machine_id"]:10s} | status={log["status"]:12s} | wo_id={str(log["work_order_id"])}')

conn.close()