# Find the duplicate section by analyzing the analytics page's 'Top 10 High-Risk Machines'
import subprocess

# Get HEAD version
result = subprocess.run(['git', 'show', 'HEAD:enterprise/enterprise_dashboard.py'], capture_output=True)
head = result.stdout.decode('utf-8', errors='replace')

with open('enterprise/enterprise_dashboard.py', 'r', encoding='utf-8') as f:
    current = f.read()

head_lines = head.split('\n')
current_lines = current.split('\n')

print(f"Current: {len(current_lines)} lines, Head: {len(head_lines)} lines")

# Find all lines unique to current (not in head)
# Look at the analytics section more carefully
print("\n=== Analytics section in CURRENT ===")
in_section = False
for i, line in enumerate(current_lines):
    if 'def render_analytics()' in line:
        in_section = True
    if in_section and line.strip().startswith('# ===') and 'ANALYTICS' not in line:
        break
    if in_section and line.strip():
        if line.strip() not in [h.strip() for h in head_lines]:
            if len(line.strip()) > 10:  # skip trivial lines
                print(f"  NEW L{i+1}: {line.strip()[:200]}")

print("\n=== Analytics section in HEAD (for comparison) ===")
in_section = False
for i, line in enumerate(head_lines):
    if 'def render_analytics()' in line:
        in_section = True
    if in_section and line.strip().startswith('# ===') and 'ANALYTICS' not in line:
        break
    if in_section and line.strip():
        print(f"  L{i+1}: {line.strip()[:200]}")