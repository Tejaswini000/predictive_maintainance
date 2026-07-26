"""Fix the last AC-004 mismatch."""
import sys
sys.path.insert(0, 'enterprise')
from database import DatabaseManager
import sqlite3

db = DatabaseManager()
conn = sqlite3.connect(db.db_path)
conn.row_factory = sqlite3.Row

latest = conn.execute(
    "SELECT MAX(maintenance_date) as latest FROM MaintenanceLogs WHERE machine_id = 'AC-004' AND status = 'Completed'"
).fetchone()['latest']
print(f'Latest completed log for AC-004: {latest}')

conn.execute("UPDATE Machines SET last_maintenance_date = ? WHERE machine_id = 'AC-004'", (latest,))
conn.commit()

row = conn.execute("SELECT last_maintenance_date FROM Machines WHERE machine_id = 'AC-004'").fetchone()
print(f'Updated: {row["last_maintenance_date"]}')
conn.close()