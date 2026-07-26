import re

with open('enterprise/enterprise_dashboard.py', 'rb') as f:
    data = f.read()

print(f"File size: {len(data)} bytes")

# Full comprehensive scan for any corruption in the KPI card HTML section
# Check for the specific patterns the user reported seeing
user_reported = [
    b"ric-number'>5</",
    b"ric-label'>\n<div",
    b"ric-number"
]

for frag in user_reported:
    pos = data.find(frag)
    print(f"\nFragment {frag[:30]!r}")
    if pos >= 0:
        print(f"  FOUND at byte {pos}")
        print(f"  Context: {data[max(0,pos-20):pos+60]}")
        text = data.decode('utf-8', errors='replace')
        line = text[:pos].count('\n') + 1
        print(f"  Line ~{line}")
    else:
        print(f"  NOT found (good)")

# Also check for any null bytes or other binary corruption
null_pos = data.find(b'\x00')
print(f"\nNull bytes: {'FOUND at ' + str(null_pos) if null_pos >= 0 else 'NONE (good)'}")

# Check how many metric-card divs are in the file (should be 6 for the 6 KPI cards)
cards = [m.start() for m in re.finditer(b"metric-card", data)]
print(f"\nNumber of 'metric-card' occurrences: {len(cards)}")
for i, pos in enumerate(cards):
    ctx = data[pos:pos+80]
    print(f"  Card {i+1} at byte {pos}: {ctx}")

# Check the exact line structure around KPI area (lines 586-661)
text = data.decode('utf-8', errors='replace')
lines = text.split('\n')
print(f"\n=== Total lines: {len(lines)} ===")

# Show lines around KPI section
kpi_comment_line = None
for i, line in enumerate(lines):
    if '# === KPI METRICS' in line:
        kpi_comment_line = i
        break

if kpi_comment_line:
    print(f"\nKPI section starts at line {kpi_comment_line+1}")
    for i in range(kpi_comment_line, min(kpi_comment_line + 80, len(lines))):
        line = lines[i]
        if any(x in line for x in ['st.markdown', 'st.button', 'metric', 'div', '<div', '</div>']):
            print(f"  L{i+1}: {line.rstrip()[:150]}")