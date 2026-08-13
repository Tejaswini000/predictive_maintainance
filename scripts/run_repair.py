"""Run auto-repair to fix data consistency issues."""
import sys
sys.path.insert(0, 'enterprise')

from services import get_sync_engine, EnterpriseDataStore

store = EnterpriseDataStore()
engine = get_sync_engine()

result = engine.validate_consistency()
print("=== BEFORE REPAIR ===")
print("Consistent:", result["consistent"])
issues = result.get("issues", [])
if issues:
    for issue in issues[:5]:
        print("  Issue:", issue)

repaired = engine.auto_repair()
print("\nRepaired:", repaired, "machines")

result = engine.validate_consistency()
print("\n=== AFTER REPAIR ===")
print("Consistent:", result["consistent"])
issues = result.get("issues", [])
if issues:
    for issue in issues:
        print("  Issue:", issue)
else:
    print("  No issues! All data consistent.")