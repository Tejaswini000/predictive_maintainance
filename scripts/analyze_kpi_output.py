import re, sys

with open('enterprise/enterprise_dashboard.py', 'rb') as f:
    data = f.read()

output = []

output.append(f"File size: {len(data)} bytes")

# Full comprehensive scan for any corruption in the KPI card HTML section
user_reported = [
    b"ric-number'>5</",
    b"ric-label'>\n<div",
    b"ric-number"
]

for frag in user_reported:
    pos = data.find(frag)
    output.append(f"\nFragment {frag[:30]!r}")
    if pos >= 0:
        output.append(f"  FOUND at byte {pos}")
        output.append(f"  Context: {data[max(0,pos-20):pos+60]}")
        text = data.decode('utf-8', errors='replace')
        line = text[:pos].count('\n') + 1
        output.append(f"  Line ~{line}")
    else:
        output.append(f"  NOT found (good)")

# Also check for any null bytes or other binary corruption
null_pos = data.find(b'\x00')
output.append(f"\nNull bytes: {'FOUND at ' + str(null_pos) if null_pos >= 0 else 'NONE (good)'}")

# Check how many metric-card divs are in the file
cards = [m.start() for m in re.finditer(b"metric-card", data)]
output.append(f"\nNumber of 'metric-card' occurrences: {len(cards)}")
for i, pos in enumerate(cards):
    ctx = data[pos:pos+80]
    output.append(f"  Card {i+1} at byte {pos}: {ctx}")

# Check the exact line structure around KPI area
text = data.decode('utf-8', errors='replace')
lines = text.split('\n')
output.append(f"\n=== Total lines: {len(lines)} ===")

# Show lines around KPI section
kpi_comment_line = None
for i, line in enumerate(lines):
    if '# === KPI METRICS' in line:
        kpi_comment_line = i
        break

if kpi_comment_line:
    output.append(f"\nKPI section starts at line {kpi_comment_line+1}")
    for i in range(kpi_comment_line, min(kpi_comment_line + 80, len(lines))):
        line = lines[i]
        if any(x in line for x in ['st.markdown', 'st.button', 'metric', 'div', '<div', '</div>']):
            output.append(f"  L{i+1}: {line.rstrip()[:150]}")

# Check for other potential issues: escaped HTML being printed
output.append("\n\n=== Checking for st.write/st.text/st.code with HTML content ===")
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if ('st.write(' in stripped or 'st.text(' in stripped or 'st.code(' in stripped):
        if '<div' in stripped or 'metric' in stripped or '</div>' in stripped:
            output.append(f"  L{i}: {stripped[:150]}")

# Check for broken f-strings with nested quotes in the KPI area
output.append("\n\n=== Checking for f-string quote issues in KPI area ===")
if kpi_comment_line:
    for i in range(kpi_comment_line, min(kpi_comment_line + 80, len(lines))):
        line = lines[i]
        if 'f"""' in line or "f'''" in line:
            output.append(f"  L{i+1}: f-string start -> {line.strip()[:100]}")

output.append("\n\n=== DONE ===")

with open('analysis_result.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print("Analysis written to analysis_result.txt")
print(f"Total output lines: {len(output)}")