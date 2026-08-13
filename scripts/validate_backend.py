"""
Backend validation script to verify all three data issues are fixed.
Run: python validate_backend.py
"""
import sys
sys.path.insert(0, 'enterprise')

from services import get_sync_engine
from database import DatabaseManager
from datetime import datetime
from collections import Counter

se = get_sync_engine()
db = DatabaseManager()

print("=" * 60)
print("BACKEND VALIDATION REPORT")
print("=" * 60)

# 1. Backfill maintenance dates
print("\n1. BACKFILL MAINTENANCE DATES")
count = se._backfill_maintenance_dates()
print(f"   Machines corrected: {count}")

# 2. Validate consistency
print("\n2. CONSISTENCY VALIDATION")
validation = se.validate_consistency()
print(f"   Consistent: {validation['consistent']}")
if validation['issues']:
    for issue in validation['issues']:
        print(f"   ISSUE: {issue}")
else:
    print("   No issues found!")
print(f"   Total machines: {validation['total_machines']}")
print(f"   Critical: {validation['critical_machines']}")
print(f"   Warning: {validation['warning_machines']}")
print(f"   Healthy: {validation['healthy_machines']}")

# 3. Check Last Maintenance == Latest Completed Maintenance Log
print("\n3. LAST MAINTENANCE VERIFICATION")
mismatches = 0
for m in db.get_all_machines():
    logs = db.get_maintenance_logs_by_machine(m.machine_id)
    completed = [l for l in logs if l.status == 'Completed']
    latest_log_date = completed[0].maintenance_date if completed else None
    last_maint = m.last_maintenance_date
    match = (last_maint == latest_log_date)
    if not match:
        print(f"   MISMATCH: {m.machine_id}: machine.last_maintenance={last_maint} vs latest completed log={latest_log_date}")
        mismatches += 1

if mismatches == 0:
    print("   ALL MATCH: Every machine's last_maintenance_date equals its latest completed maintenance log.")
else:
    print(f"   {mismatches} mismatches found (auto-repair recommended)")

# 4. Check maintenance dates occur after purchase date
print("\n4. MAINTENANCE AFTER PURCHASE CHECK")
violations = 0
for m in db.get_all_machines():
    if not m.purchase_date:
        continue
    logs = db.get_maintenance_logs_by_machine(m.machine_id)
    for log in logs:
        if log.maintenance_date and log.maintenance_date < m.purchase_date:
            print(f"   VIOLATION: {m.machine_id}: maintenance {log.maintenance_date} before purchase {m.purchase_date}")
            violations += 1
            break

if violations == 0:
    print("   ALL PASS: No maintenance dates occur before purchase dates.")
else:
    print(f"   {violations} violations found")

# 5. Check no clustered timestamps in Scheduled logs
print("\n5. CLUSTERED TIMESTAMPS CHECK")
all_logs = db.get_all_maintenance_logs()
scheduled = [l for l in all_logs if l.status == 'Scheduled']
minutes = Counter()
for l in scheduled:
    if l.maintenance_date:
        m = l.maintenance_date.strftime('%Y-%m-%d %H:%M')
        minutes[m] += 1
clustered = {k: v for k, v in minutes.items() if v > 3}
if clustered:
    print(f"   WARNING: {len(clustered)} clustered minute slots found (>3 machines):")
    for d, c in sorted(clustered.items()):
        print(f"     {d}: {c} machines")
else:
    print("   NO CLUSTERING: No more than 3 Scheduled logs share the same minute.")

# Also check completed logs
completed = [l for l in all_logs if l.status == 'Completed']
completed_minutes = Counter()
for l in completed:
    if l.maintenance_date:
        m = l.maintenance_date.strftime('%Y-%m-%d %H:%M')
        completed_minutes[m] += 1
completed_clustered = {k: v for k, v in completed_minutes.items() if v > 3}
if completed_clustered:
    print(f"   WARNING for Completed logs: {len(completed_clustered)} clustered minute slots (>3):")
    for d, c in sorted(completed_clustered.items()):
        print(f"     {d}: {c} machines")
else:
    print("   NO CLUSTERING for Completed logs either.")

# 6. Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"✓ Last Maintenance from completed logs: {'PASS' if mismatches == 0 else 'FAIL'}")
print(f"✓ Maintenance after Purchase Date: {'PASS' if violations == 0 else 'FAIL'}")
print(f"✓ No clustered timestamps: {'PASS' if len(clustered) == 0 else 'WARNING'}")
print(f"✓ No completed log clustering: {'PASS' if len(completed_clustered) == 0 else 'WARNING'}")
print(f"✓ Data consistency: {'PASS' if validation['consistent'] else 'FAIL'}")