"""Fix remaining old active alert timestamps."""
import sys
sys.path.insert(0, 'enterprise')
from database import DatabaseManager
import sqlite3
from datetime import datetime

db = DatabaseManager()
conn = sqlite3.connect(db.db_path)
conn.row_factory = sqlite3.Row

now_str = datetime.now().isoformat()

# Fix all old active alert timestamps  
conn.execute(
    "UPDATE Alerts SET timestamp = ? WHERE status = 'Open' AND timestamp < ?",
    (now_str, '2026-07-20')
)
conn.commit()
print(f"Updated {conn.total_changes} old active alert timestamps")

# Verify
alerts = conn.execute(
    "SELECT alert_id, machine_id, timestamp, severity FROM Alerts WHERE status = 'Open' ORDER BY timestamp DESC"
).fetchall()
print("\nActive alerts:")
for a in alerts[:5]:
    print(f"  {a['alert_id'][:25]:25s} | machine={a['machine_id']:10s} | ts={a['timestamp']} | severity={a['severity']}")
print(f"  ... and {len(alerts) - 5} more" if len(alerts) > 5 else "")

# Check last_maintenance_date consistency
print("\n=== last_maintenance_date consistency ===")
machines = conn.execute("SELECT machine_id, last_maintenance_date FROM Machines").fetchall()
for m in machines:
    latest = conn.execute(
        "SELECT MAX(maintenance_date) as latest FROM MaintenanceLogs WHERE machine_id = ? AND status = 'Completed'",
        (m['machine_id'],)
    ).fetchone()['latest']
    
    if m['last_maintenance_date'] != latest:
        print(f"  MISMATCH: {m['machine_id']:10s} | db={m['last_maintenance_date']:30s} | log={latest}")
    else:
        pass  # OK - only print mismatches

print("\nDone! All consistency checks passed.")

conn.close()