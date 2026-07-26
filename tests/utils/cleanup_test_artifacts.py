"""
Development/test helper: cleanup_test_artifacts.py

This script is a development/testing utility only. It is not part of the
production application and should not be imported or executed by production
code. Use it to remove temporary test artifacts (e.g., maintenance logs,
work orders, alerts) during development or automated tests.
"""

import sqlite3, os


def cleanup(machine_id: str = "WM-008"):
    p = os.path.join(os.path.dirname(r'C:\Users\TS6201_TEJASWINI\Documents\predictive_maintainance\enterprise\database.py'), 'predictive_maintenance.db')
    conn = sqlite3.connect(p)
    cur = conn.cursor()
    for table, col in [('MaintenanceLogs', 'machine_id'), ('WorkOrders', 'machine_id'), ('Alerts', 'machine_id')]:
        cur.execute(f"DELETE FROM {table} WHERE {col} = ?", (machine_id,))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    cleanup()
